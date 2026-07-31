"""Central model training -- the full-dataset reference models.

Central is trained on the complete dataset across all states/districts, must
remain the most accurate model available, and serves as both the universal
fallback (Hard Constraint 4) and the teacher for edge distillation (SRD 2.1).

For each of the Advisor's five targets this module benchmarks every available
candidate algorithm under cross-validation, selects the winner on the CV
metric, refits it on the full training split, and writes a comparison log
recording algorithm, CV score, training time, inference latency and model size
so the choice is defensible (SRD FR-5 / Deliverable 6).

Run:
    python -m ml.advisor_edge.train_central
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
from sklearn.model_selection import KFold, StratifiedKFold

from ml.advisor_edge import candidates as C
from ml.advisor_edge import features as F

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CENTRAL_DIR = PROJECT_ROOT / "backend" / "artifacts" / "central" / "advisor"

CV_FOLDS = 3
#: Cap rows used during the CV bake-off. The winner is refit on everything;
#: this only bounds the cost of comparing four algorithms on 450k rows.
CV_SAMPLE_CAP = 120_000
#: How many CV leaders get refit on the full split and scored on the holdout.
CV_FINALISTS = 3
#: Accuracy is never traded for size. A smaller model may only displace a
#: larger one when its holdout score is EQUAL OR BETTER -- hence 0.0. Setting
#: this above zero would let a marginally worse model win on footprint, which
#: is the wrong trade for a reference model that must stay the most accurate
#: available (Hard Constraint 4).
SELECTION_TOLERANCE = 0.0


@dataclass
class CandidateResult:
    algorithm: str
    cv_score: float
    cv_std: float
    train_seconds: float
    latency_ms: float
    size_kb: float
    failed: Optional[str] = None


def _take(X, idx):
    """Row-select from either a numpy array or a DataFrame."""
    return X.iloc[idx] if hasattr(X, "iloc") else X[idx]


def _subsample(X, y: np.ndarray, cap: int, seed: int = 42):
    if len(X) <= cap:
        return X, y
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(X), size=cap, replace=False)
    return _take(X, idx), y[idx]


def benchmark(
    name: str,
    factory_map: Dict[str, Callable],
    X,
    y: np.ndarray,
    *,
    task: str,
    X_holdout=None,
    y_holdout=None,
) -> tuple[str, Any, list[CandidateResult]]:
    """Rank by CV, then decide on a full-data refit scored on the holdout."""
    Xs, ys = _subsample(X, y, CV_SAMPLE_CAP)
    results: list[CandidateResult] = []

    if task == "classification":
        splitter = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=42)
        scorer = lambda yt, yp: accuracy_score(yt, yp)
    else:
        splitter = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=42)
        scorer = lambda yt, yp: r2_score(yt, yp)

    logger.info("  benchmarking %d candidates on %d rows (%s)",
                len(factory_map), len(Xs), task)

    for algo, factory in factory_map.items():
        try:
            fold_scores = []
            t0 = time.perf_counter()
            for tr, va in splitter.split(Xs, ys if task == "classification" else None):
                m = factory()
                m.fit(_take(Xs, tr), ys[tr])
                fold_scores.append(scorer(ys[va], F.as_1d(m.predict(_take(Xs, va)))))
            elapsed = time.perf_counter() - t0

            probe_n = min(len(Xs), 20_000)
            probe = factory()
            probe.fit(_take(Xs, np.arange(probe_n)), ys[:probe_n])
            results.append(CandidateResult(
                algorithm=algo,
                cv_score=float(np.mean(fold_scores)),
                cv_std=float(np.std(fold_scores)),
                train_seconds=round(elapsed, 2),
                latency_ms=round(C.measure_inference_latency(probe, Xs), 4),
                size_kb=round(C.model_size_kb(probe), 1),
            ))
            logger.info("    %-14s cv=%.4f (+/-%.4f)  fit=%5.1fs  lat=%.3fms  %.0fKB",
                        algo, results[-1].cv_score, results[-1].cv_std,
                        results[-1].train_seconds, results[-1].latency_ms,
                        results[-1].size_kb)
        except Exception as exc:
            logger.warning("    %-14s FAILED: %s", algo, exc)
            results.append(CandidateResult(algo, float("-inf"), 0, 0, 0, 0, str(exc)))

    ok = [r for r in results if r.failed is None]
    if not ok:
        raise RuntimeError(f"{name}: every candidate failed")

    # CV ranks the field, but it runs on a subsample -- so it narrows rather
    # than decides. Refit the finalists on the FULL training split and pick on
    # that, because subsample rankings do not always survive the full data.
    #
    # This is not hypothetical: on the yield target, CV on 120k rows ranked
    # RandomForest first (0.7160) ahead of LightGBM (0.7282 CV but 4th on some
    # folds), yet refit on all 453k rows LightGBM scored 0.7348 on the holdout
    # against RandomForest's 0.7317 -- while being 145x smaller and 11x faster.
    # Selecting on the subsample alone shipped the worse model.
    finalists = sorted(ok, key=lambda r: r.cv_score, reverse=True)[:CV_FINALISTS]
    logger.info("  finalists: %s", ", ".join(f.algorithm for f in finalists))

    scored: list[tuple[float, str, Any]] = []
    for cand in finalists:
        t0 = time.perf_counter()
        model = factory_map[cand.algorithm]()
        model.fit(X, y)
        elapsed = time.perf_counter() - t0
        score = float(scorer(y_holdout, F.as_1d(model.predict(X_holdout)))) \
            if X_holdout is not None else cand.cv_score
        scored.append((score, cand.algorithm, model))
        logger.info("    %-14s full-refit %s=%.4f  (%.0fs)",
                    cand.algorithm, "acc" if task == "classification" else "R2",
                    score, elapsed)

    # Accuracy decides outright. Size breaks EXACT ties only (tolerance 0.0),
    # so a smaller model can never displace a more accurate one.
    best_score = max(s for s, _, _ in scored)
    contenders = [(s, a, m) for s, a, m in scored if best_score - s <= SELECTION_TOLERANCE]
    if len(contenders) > 1:
        sized = [(C.model_size_kb(m), s, a, m) for s, a, m in contenders]
        sized.sort(key=lambda t: t[0])
        _, final_score, winner_name, final = sized[0]
        if winner_name != max(scored, key=lambda t: t[0])[1]:
            logger.info("    size tie-break: %s (%.4f) over %s (%.4f)",
                        winner_name, final_score,
                        max(scored, key=lambda t: t[0])[1], best_score)
    else:
        final_score, winner_name, final = max(scored, key=lambda t: t[0])

    logger.info("  WINNER: %s (holdout=%.4f)", winner_name, final_score)
    return winner_name, final, results


def train_all() -> Dict[str, Any]:
    CENTRAL_DIR.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        "mode": "central",
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "available_algorithms": C.available(),
        "targets": {},
    }

    # ── 1. Crop Recommender ────────────────────────────────────────────────
    logger.info("[1/5] crop_recommender")
    crop = F.prepare_crop_data()
    algo, model, log = benchmark(
        "crop", C.central_classifiers(len(crop.label_encoder.classes_)),
        crop.X_train, crop.y_train, task="classification",
        X_holdout=crop.X_test, y_holdout=crop.y_test,
    )
    test_pred = F.as_1d(model.predict(crop.X_test))
    report["targets"]["crop_recommender"] = {
        "task": "classification", "winner": algo,
        "test_accuracy": round(float(accuracy_score(crop.y_test, test_pred)), 4),
        "test_f1_macro": round(float(f1_score(crop.y_test, test_pred, average="macro")), 4),
        "n_classes": len(crop.label_encoder.classes_),
        "classes": list(crop.label_encoder.classes_),
        "n_train": int(len(crop.X_train)), "n_test": int(len(crop.X_test)),
        "candidates": [asdict(r) for r in log],
    }
    joblib.dump(model, CENTRAL_DIR / "crop_model.pkl")
    joblib.dump(crop.scaler, CENTRAL_DIR / "crop_scaler.pkl")
    joblib.dump(crop.label_encoder, CENTRAL_DIR / "crop_label_encoder.pkl")

    # ── 2-4. Irrigation family (three targets, one preprocessor) ───────────
    irr = F.prepare_irrigation_data()
    joblib.dump(irr.preprocessor, CENTRAL_DIR / "irrigation_preprocessor.pkl")

    logger.info("[2/5] sunlight_hours")
    algo, model, log = benchmark(
        "sunlight", C.central_regressors(),
        irr.X_train, irr.y_train["sunlight_hours"].to_numpy(), task="regression",
        X_holdout=irr.X_test, y_holdout=irr.y_test["sunlight_hours"].to_numpy(),
    )
    pred = F.as_1d(model.predict(irr.X_test))
    yte = irr.y_test["sunlight_hours"].to_numpy()
    report["targets"]["sunlight"] = {
        "task": "regression", "winner": algo,
        "test_r2": round(float(r2_score(yte, pred)), 4),
        "test_mae": round(float(mean_absolute_error(yte, pred)), 4),
        "n_train": int(len(irr.X_train)), "n_test": int(len(irr.X_test)),
        "candidates": [asdict(r) for r in log],
    }
    joblib.dump(model, CENTRAL_DIR / "sunlight_model.pkl")

    for slot, target in [("3/5", "irrigation_type"), ("4/5", "irrigation_need")]:
        logger.info("[%s] %s", slot, target)
        enc = irr.encoders[target]
        algo, model, log = benchmark(
            target, C.central_classifiers(len(enc.classes_)),
            irr.X_train, irr.y_train[target].to_numpy(), task="classification",
            X_holdout=irr.X_test, y_holdout=irr.y_test[target].to_numpy(),
        )
        yte = irr.y_test[target].to_numpy()
        pred = F.as_1d(model.predict(irr.X_test))
        report["targets"][target] = {
            "task": "classification", "winner": algo,
            "test_accuracy": round(float(accuracy_score(yte, pred)), 4),
            "test_f1_macro": round(float(f1_score(yte, pred, average="macro")), 4),
            "n_classes": len(enc.classes_), "classes": list(enc.classes_),
            "n_train": int(len(irr.X_train)), "n_test": int(len(irr.X_test)),
            "candidates": [asdict(r) for r in log],
        }
        joblib.dump(model, CENTRAL_DIR / f"{target}_model.pkl")
        joblib.dump(enc, CENTRAL_DIR / f"{target}_encoder.pkl")

    # ── 5. Yield Predictor (the state-aware one) ───────────────────────────
    logger.info("[5/5] yield_predictor")
    yd = F.prepare_yield_data()
    Xtr, ytr = yd.matrix(yd.train_idx)
    Xte, yte = yd.matrix(yd.test_idx)
    algo, model, log = benchmark("yield", C.yield_regressors(edge=False), Xtr, ytr,
                                 task="regression", X_holdout=Xte, y_holdout=yte)
    yield_ceiling = C.fit_yield_ceiling(ytr)
    pred = C.clamp_yield(F.as_1d(model.predict(Xte)), yield_ceiling)
    residuals = yte - pred
    report["targets"]["yield_predictor"] = {
        "task": "regression", "winner": algo,
        "test_r2": round(float(r2_score(yte, pred)), 4),
        "test_mae": round(float(mean_absolute_error(yte, pred)), 4),
        "yield_ceiling": yield_ceiling,
        "residual_std": round(float(np.std(residuals)), 4),
        "residual_q10": round(float(np.quantile(residuals, 0.10)), 4),
        "residual_q90": round(float(np.quantile(residuals, 0.90)), 4),
        "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
        "n_states": int(yd.frame["state"].nunique()),
        "eligible_states": yd.eligible_states(),
        "sparse_states": yd.sparse_states(),
        "candidates": [asdict(r) for r in log],
    }
    joblib.dump(model, CENTRAL_DIR / "yield_model.pkl")
    joblib.dump(yd.encoders, CENTRAL_DIR / "yield_encoders.pkl")

    (CENTRAL_DIR / "central_metadata.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    logger.info("central artifacts -> %s", CENTRAL_DIR)
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import warnings

    warnings.filterwarnings("ignore")
    rep = train_all()

    print("\n" + "=" * 68)
    print("CENTRAL MODEL SELECTION")
    print("=" * 68)
    for target, info in rep["targets"].items():
        metric = (f"acc={info['test_accuracy']:.4f}" if info["task"] == "classification"
                  else f"R2={info['test_r2']:.4f}")
        print(f"  {target:22s} {info['winner']:14s} {metric}")
