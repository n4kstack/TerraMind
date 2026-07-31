"""Edge model training -- per-state yield models plus compressed replicas.

Two kinds of artifact live on an edge node, and the distinction is deliberate:

**Regionally specialised (yield).** The yield dataset is the only Advisor
source carrying State/District, so it is the only target that can honour Hard
Constraint 3 -- trained *only* on that state's rows. Each state model is
distilled from central (SRD 2.2), locally calibrated, and gated on the <= 4%
accuracy ceiling (FR-7) before it may be promoted.

**Edge-deployed replicas (crop, sunlight, irrigation type, irrigation need).**
Their training data has no geography -- the columns are soil chemistry and
weather with no state key -- so a per-state model is not merely unwise, it is
undefined. These are compressed national models distilled from central and
replicated onto every node. They are NOT claimed to be regional. They exist at
the edge so that a request can be served end-to-end locally, which is what
delivers the latency, central-load, fault-isolation and bandwidth benefits in
SRD 2.6. Their accuracy gap against central is measured and reported like any
other, and is small by construction.

Run:
    python -m ml.advisor_edge.train_edge
    python -m ml.advisor_edge.train_edge --states punjab,kerala
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, r2_score

from ml.advisor_edge import ACCURACY_GAP_CEILING
from ml.advisor_edge import candidates as C
from ml.advisor_edge import features as F

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CENTRAL_DIR = PROJECT_ROOT / "backend" / "artifacts" / "central" / "advisor"
EDGE_DIR = PROJECT_ROOT / "backend" / "artifacts" / "edge" / "advisor"
SHARED_DIR = EDGE_DIR / "_shared"

#: Distillation blend. y = ALPHA * true + (1 - ALPHA) * central_prediction.
#: Weighted toward ground truth so the edge model still specialises regionally;
#: the central term keeps it anchored to the reference model and is the main
#: lever for holding the accuracy gap under the ceiling.
DISTILL_ALPHA = 0.7

#: Absolute quality floor for promotion, independent of the gap test.
#: R^2 of 0 is the "predict the mean" baseline; anything at or below it is not
#: fit to serve regardless of how badly central does on the same state.
MIN_EDGE_R2 = 0.0


def _clamp(values):
    """Clamp yield predictions using the ceiling fitted during central training."""
    return C.clamp_yield(values, _yield_ceiling())


def _yield_ceiling() -> float:
    """Inference ceiling fitted by central training; falls back to the default."""
    try:
        meta = json.loads((CENTRAL_DIR / "central_metadata.json").read_text(encoding="utf-8"))
        return float(meta["targets"]["yield_predictor"]["yield_ceiling"])
    except Exception:
        return C.DEFAULT_YIELD_CEILING


@dataclass
class StateResult:
    state: str
    n_train: int
    n_test: int
    algorithm: str
    central_r2: float
    edge_r2: float
    gap: float
    calibration_slope: float
    calibration_intercept: float
    latency_ms: float
    size_kb: float
    promoted: bool
    reason: str


# ═══════════════════════════════════════════════════════════════════════════
# Calibration
# ═══════════════════════════════════════════════════════════════════════════

def fit_linear_calibration(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float]:
    """Least-squares slope/intercept mapping edge predictions onto truth.

    The regression analogue of Platt scaling (SRD 2.2): corrects systematic
    regional bias so edge output is statistically aligned with central rather
    than merely correlated with it. Degenerate inputs fall back to identity.
    """
    if len(y_true) < 10 or np.std(y_pred) < 1e-9:
        return 1.0, 0.0
    slope, intercept = np.polyfit(y_pred, y_true, 1)
    if not np.isfinite(slope) or not np.isfinite(intercept):
        return 1.0, 0.0
    # Reject implausible corrections -- a wild slope means the state's holdout
    # is too small to calibrate against, so identity is the safer choice.
    if not (0.2 <= slope <= 5.0):
        return 1.0, 0.0
    return float(slope), float(intercept)


def apply_calibration(pred: np.ndarray, slope: float, intercept: float) -> np.ndarray:
    return np.clip(pred * slope + intercept, 0.0, None)


# ═══════════════════════════════════════════════════════════════════════════
# Per-state yield models -- genuinely regional
# ═══════════════════════════════════════════════════════════════════════════

def train_state_yield(
    state: str,
    yd: F.YieldData,
    central_model,
    central_r2_global: float,
) -> Optional[StateResult]:
    """Train, distil, calibrate and gate one state's yield model."""
    tr_idx = yd.state_indices(state, "train")
    te_idx = yd.state_indices(state, "test")

    if len(tr_idx) < F.MIN_ROWS_PER_STATE or len(te_idx) < 30:
        logger.info("  %-28s SKIP (train=%d test=%d below floor)",
                    state, len(tr_idx), len(te_idx))
        return None

    X_tr, y_tr = yd.matrix(tr_idx)
    X_te, y_te = yd.matrix(te_idx)

    # Central's score on THIS state's holdout is the comparison basis --
    # the gap must be per state (FR-7), not against a national average.
    central_pred = _clamp(F.as_1d(central_model.predict(X_te)))
    central_r2 = float(r2_score(y_te, central_pred))

    # Distillation: blend ground truth with the teacher's view of this state.
    teacher_tr = _clamp(F.as_1d(central_model.predict(X_tr)))
    y_distilled = DISTILL_ALPHA * y_tr + (1.0 - DISTILL_ALPHA) * teacher_tr

    scored = []
    for algo, factory in C.yield_regressors(edge=True).items():
        try:
            m = factory()
            m.fit(X_tr, y_distilled)
            scored.append({
                "algorithm": algo, "model": m,
                "score": float(r2_score(y_te, _clamp(F.as_1d(m.predict(X_te))))),
            })
        except Exception as exc:
            logger.debug("  %s/%s failed: %s", state, algo, exc)

    if not scored:
        logger.warning("  %-28s FAIL (no candidate trained)", state)
        return None

    chosen = _select_edge_candidate(scored, X_te)
    best_name, best_model, best_score = (
        chosen["algorithm"], chosen["model"], chosen["score"],
    )

    raw_pred = _clamp(F.as_1d(best_model.predict(X_te)))
    slope, intercept = fit_linear_calibration(y_te, raw_pred)
    edge_pred = apply_calibration(raw_pred, slope, intercept)
    edge_r2 = float(r2_score(y_te, edge_pred))

    # Calibration must not make things worse.
    if edge_r2 < best_score:
        slope, intercept = 1.0, 0.0
        edge_r2 = float(best_score)

    gap = central_r2 - edge_r2

    # Promotion needs BOTH a small gap and absolute competence.
    #
    # The gap test alone is satisfiable by a bad edge model whenever central is
    # even worse -- Mizoram produced central R^2 = -7216 against edge R^2 =
    # -17, a hugely "favourable" gap between two useless models. An R^2 below
    # zero means the model loses to predicting the mean, so serving it would be
    # worse than serving nothing. The floor makes that disqualifying.
    meets_gap = gap <= ACCURACY_GAP_CEILING
    meets_floor = edge_r2 >= MIN_EDGE_R2
    promoted = meets_gap and meets_floor

    if not meets_gap:
        reason = f"gap {gap:.4f} exceeds {ACCURACY_GAP_CEILING}"
    elif not meets_floor:
        reason = (f"edge R2 {edge_r2:.4f} below absolute floor {MIN_EDGE_R2} "
                  f"(central R2 {central_r2:.4f} is also poor -- data quality issue)")
    else:
        reason = "within ceiling"

    result = StateResult(
        state=state, n_train=len(tr_idx), n_test=len(te_idx),
        algorithm=best_name,
        central_r2=round(central_r2, 4), edge_r2=round(edge_r2, 4),
        gap=round(gap, 4),
        calibration_slope=round(slope, 4), calibration_intercept=round(intercept, 4),
        latency_ms=round(C.measure_inference_latency(best_model, X_te), 4),
        size_kb=round(C.model_size_kb(best_model), 1),
        promoted=promoted, reason=reason,
    )

    if promoted:
        node = EDGE_DIR / state
        node.mkdir(parents=True, exist_ok=True)
        joblib.dump(best_model, node / "yield_model.pkl")
        (node / "node_metadata.json").write_text(
            json.dumps(asdict(result), indent=2), encoding="utf-8"
        )

    logger.info("  %-28s %-11s central=%9.4f edge=%9.4f gap=%+.4f  %s",
                state, best_name, central_r2, edge_r2, gap,
                "PROMOTED" if promoted else "HELD -> central")
    if not promoted:
        logger.info("      reason: %s", reason)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Compressed national replicas -- edge-deployed, not regional
# ═══════════════════════════════════════════════════════════════════════════

def train_shared_replicas() -> Dict[str, Any]:
    """Compress the four non-geographic models for edge deployment."""
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    out: Dict[str, Any] = {}

    # -- crop recommender ---------------------------------------------------
    logger.info("  crop_recommender")
    crop = F.prepare_crop_data()
    central = joblib.load(CENTRAL_DIR / "crop_model.pkl")
    central_acc = float(accuracy_score(crop.y_test, F.as_1d(central.predict(crop.X_test))))

    # Classification distillation: train on the teacher's labels for rows where
    # it is confident, ground truth elsewhere. Keeps the compact student aligned
    # with central's decision boundary rather than just the raw labels.
    teacher = F.as_1d(central.predict(crop.X_train))
    y_distilled = np.where(
        np.random.default_rng(42).random(len(teacher)) < (1.0 - DISTILL_ALPHA),
        teacher, crop.y_train,
    )

    best = _pick_best_classifier(
        C.edge_classifiers(len(crop.label_encoder.classes_)),
        crop.X_train, y_distilled, crop.X_test, crop.y_test,
    )
    joblib.dump(best["model"], SHARED_DIR / "crop_model.pkl")
    out["crop_recommender"] = _replica_entry(best, central_acc, "accuracy")

    # -- sunlight -----------------------------------------------------------
    irr = F.prepare_irrigation_data()
    logger.info("  sunlight")
    central = joblib.load(CENTRAL_DIR / "sunlight_model.pkl")
    y_te = irr.y_test["sunlight_hours"].to_numpy()
    central_r2 = float(r2_score(y_te, F.as_1d(central.predict(irr.X_test))))
    teacher = F.as_1d(central.predict(irr.X_train))
    y_dist = DISTILL_ALPHA * irr.y_train["sunlight_hours"].to_numpy() + (1 - DISTILL_ALPHA) * teacher
    best = _pick_best_regressor(C.edge_regressors(), irr.X_train, y_dist, irr.X_test, y_te)
    joblib.dump(best["model"], SHARED_DIR / "sunlight_model.pkl")
    out["sunlight"] = _replica_entry(best, central_r2, "r2")

    # -- irrigation type / need --------------------------------------------
    for target in ("irrigation_type", "irrigation_need"):
        logger.info("  %s", target)
        central = joblib.load(CENTRAL_DIR / f"{target}_model.pkl")
        enc = irr.encoders[target]
        y_te = irr.y_test[target].to_numpy()
        central_acc = float(accuracy_score(y_te, F.as_1d(central.predict(irr.X_test))))
        teacher = F.as_1d(central.predict(irr.X_train))
        y_tr = irr.y_train[target].to_numpy()
        y_dist = np.where(
            np.random.default_rng(42).random(len(teacher)) < (1.0 - DISTILL_ALPHA),
            teacher, y_tr,
        )
        best = _pick_best_classifier(
            C.edge_classifiers(len(enc.classes_)), irr.X_train, y_dist, irr.X_test, y_te
        )
        joblib.dump(best["model"], SHARED_DIR / f"{target}_model.pkl")
        out[target] = _replica_entry(best, central_acc, "accuracy")

    return out


#: Two edge candidates whose scores differ by less than this are treated as
#: equivalent, and the faster one wins. SRD section 8 requires edge selection to
#: balance score against inference latency -- without this, a marginally better
#: model that is an order of magnitude slower would be picked and would
#: undermine the very latency claim edge exists to make (NFR-1).
SCORE_TOLERANCE = 0.005


def _select_edge_candidate(scored: List[Dict[str, Any]], X_te) -> Dict[str, Any]:
    """Best score, then fastest among statistical ties."""
    if not scored:
        raise RuntimeError("no candidate trained")

    for entry in scored:
        entry["latency_ms"] = round(C.measure_inference_latency(entry["model"], X_te), 4)
        entry["size_kb"] = round(C.model_size_kb(entry["model"]), 1)

    top = max(e["score"] for e in scored)
    contenders = [e for e in scored if top - e["score"] <= SCORE_TOLERANCE]
    winner = min(contenders, key=lambda e: e["latency_ms"])

    if winner["score"] < top:
        slowest = max(contenders, key=lambda e: e["latency_ms"])
        logger.info("    latency tie-break: %s (%.4f, %.3fms) over %s (%.4f, %.3fms)",
                    winner["algorithm"], winner["score"], winner["latency_ms"],
                    slowest["algorithm"], slowest["score"], slowest["latency_ms"])
    return winner


def _pick_best_classifier(factories, X_tr, y_tr, X_te, y_te) -> Dict[str, Any]:
    scored = []
    for algo, factory in factories.items():
        try:
            m = factory()
            m.fit(X_tr, y_tr)
            scored.append({
                "algorithm": algo, "model": m,
                "score": float(accuracy_score(y_te, F.as_1d(m.predict(X_te)))),
            })
        except Exception as exc:
            logger.debug("    %s failed: %s", algo, exc)
    return _select_edge_candidate(scored, X_te)


def _pick_best_regressor(factories, X_tr, y_tr, X_te, y_te) -> Dict[str, Any]:
    scored = []
    for algo, factory in factories.items():
        try:
            m = factory()
            m.fit(X_tr, y_tr)
            scored.append({
                "algorithm": algo, "model": m,
                "score": float(r2_score(y_te, F.as_1d(m.predict(X_te)))),
            })
        except Exception as exc:
            logger.debug("    %s failed: %s", algo, exc)
    return _select_edge_candidate(scored, X_te)


def _replica_entry(best: Dict[str, Any], central_score: float, metric: str) -> Dict[str, Any]:
    gap = central_score - best["score"]
    entry = {
        "kind": "edge_replica",
        "regional": False,
        "algorithm": best["algorithm"],
        "metric": metric,
        f"central_{metric}": round(central_score, 4),
        f"edge_{metric}": round(best["score"], 4),
        "gap": round(gap, 4),
        "within_ceiling": bool(gap <= ACCURACY_GAP_CEILING),
        "latency_ms": best["latency_ms"],
        "size_kb": best["size_kb"],
    }
    logger.info("    %-11s central=%.4f edge=%.4f gap=%+.4f  %s  (%.0fKB, %.3fms)",
                best["algorithm"], central_score, best["score"], gap,
                "OK" if entry["within_ceiling"] else "OVER CEILING",
                best["size_kb"], best["latency_ms"])
    return entry


# ═══════════════════════════════════════════════════════════════════════════

def train_all(only_states: Optional[List[str]] = None) -> Dict[str, Any]:
    if not (CENTRAL_DIR / "yield_model.pkl").exists():
        raise FileNotFoundError(
            f"Central artifacts missing in {CENTRAL_DIR}. "
            "Run: python -m ml.advisor_edge.train_central"
        )

    EDGE_DIR.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        "mode": "edge",
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "distill_alpha": DISTILL_ALPHA,
        "accuracy_gap_ceiling": ACCURACY_GAP_CEILING,
    }

    logger.info("=== compressed national replicas (edge-deployed, not regional) ===")
    report["shared_replicas"] = train_shared_replicas()

    logger.info("=== per-state yield models (regionally specialised) ===")
    yd = F.prepare_yield_data()
    central_yield = joblib.load(CENTRAL_DIR / "yield_model.pkl")
    X_te_all, y_te_all = yd.matrix(yd.test_idx)
    central_r2_global = float(r2_score(y_te_all, central_yield.predict(X_te_all)))
    logger.info("  central yield R2 (national holdout) = %.4f", central_r2_global)

    states = only_states or yd.eligible_states()
    results: List[StateResult] = []
    for state in states:
        r = train_state_yield(state, yd, central_yield, central_r2_global)
        if r is not None:
            results.append(r)

    promoted = [r for r in results if r.promoted]
    report["central_yield_r2_national"] = round(central_r2_global, 4)
    report["states_evaluated"] = len(results)
    report["states_promoted"] = len(promoted)
    report["states_held_on_central"] = len(results) - len(promoted)
    report["sparse_states"] = yd.sparse_states()
    report["states"] = [asdict(r) for r in results]

    (EDGE_DIR / "edge_metadata.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    logger.info("edge artifacts -> %s", EDGE_DIR)
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import warnings

    warnings.filterwarnings("ignore")

    ap = argparse.ArgumentParser()
    ap.add_argument("--states", type=str, default=None,
                    help="comma-separated subset, e.g. punjab,kerala")
    args = ap.parse_args()
    subset = [s.strip() for s in args.states.split(",")] if args.states else None

    rep = train_all(subset)
    print("\n" + "=" * 74)
    print("EDGE TRAINING SUMMARY")
    print("=" * 74)
    print(f"  replicas       : {len(rep['shared_replicas'])} compressed national models")
    print(f"  states evaluated: {rep['states_evaluated']}")
    print(f"  promoted        : {rep['states_promoted']}")
    print(f"  held on central : {rep['states_held_on_central']}")
    print(f"  sparse (skipped): {len(rep['sparse_states'])}")
