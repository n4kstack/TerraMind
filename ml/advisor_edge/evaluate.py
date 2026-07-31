"""Accuracy-gap governance harness (SRD FR-7 / 2.5).

Recomputes ``central_metric - edge_metric`` per state on the shared held-out
set and enforces the <= 4% promotion ceiling. This runs independently of
training so the guarantee can be re-checked on a schedule and drift cannot
silently break it: a node that has drifted past the ceiling is demoted in the
registry and its state reverts to central fallback.

Metric choice follows the Advisor's actual task types (SRD section 13 risk row):
R^2 for the regression targets, accuracy for the classification targets. The
same metric is used on both sides of every comparison.

Run:
    python -m ml.advisor_edge.evaluate
    python -m ml.advisor_edge.evaluate --demote     # apply demotions
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score

from ml.advisor_edge import ACCURACY_GAP_CEILING
from ml.advisor_edge import features as F
from ml.advisor_edge.registry import CENTRAL_DIR, EDGE_DIR, SHARED_DIR, registry
from ml.advisor_edge.train_edge import apply_calibration

logger = logging.getLogger(__name__)

REPORT_PATH = EDGE_DIR / "accuracy_gap_report.json"


def evaluate_replicas() -> Dict[str, Any]:
    """Gap for the four compressed national replicas."""
    out: Dict[str, Any] = {}

    crop = F.prepare_crop_data()
    c_model = joblib.load(CENTRAL_DIR / "crop_model.pkl")
    e_model = joblib.load(SHARED_DIR / "crop_model.pkl")
    c_acc = float(accuracy_score(crop.y_test, F.as_1d(c_model.predict(crop.X_test))))
    e_acc = float(accuracy_score(crop.y_test, F.as_1d(e_model.predict(crop.X_test))))
    out["crop_recommender"] = _entry("accuracy", c_acc, e_acc, len(crop.X_test))

    irr = F.prepare_irrigation_data()

    y_te = irr.y_test["sunlight_hours"].to_numpy()
    c_r2 = float(r2_score(y_te, F.as_1d(joblib.load(CENTRAL_DIR / "sunlight_model.pkl").predict(irr.X_test))))
    e_r2 = float(r2_score(y_te, F.as_1d(joblib.load(SHARED_DIR / "sunlight_model.pkl").predict(irr.X_test))))
    out["sunlight"] = _entry("r2", c_r2, e_r2, len(irr.X_test))

    for target in ("irrigation_type", "irrigation_need"):
        y_te = irr.y_test[target].to_numpy()
        c = float(accuracy_score(y_te, F.as_1d(joblib.load(CENTRAL_DIR / f"{target}_model.pkl").predict(irr.X_test))))
        e = float(accuracy_score(y_te, F.as_1d(joblib.load(SHARED_DIR / f"{target}_model.pkl").predict(irr.X_test))))
        out[target] = _entry("accuracy", c, e, len(irr.X_test))

    return out


def _entry(metric: str, central: float, edge: float, n: int) -> Dict[str, Any]:
    gap = central - edge
    return {
        "metric": metric,
        "central": round(central, 4),
        "edge": round(edge, 4),
        "gap": round(gap, 4),
        "within_ceiling": bool(gap <= ACCURACY_GAP_CEILING),
        "n_eval": int(n),
    }


def evaluate_states() -> List[Dict[str, Any]]:
    """Per-state yield gap on each state's own slice of the shared holdout."""
    yd = F.prepare_yield_data()
    central = joblib.load(CENTRAL_DIR / "yield_model.pkl")
    rows: List[Dict[str, Any]] = []

    for state, node in sorted(registry.all_nodes().items()):
        if not node.exists():
            continue
        te_idx = yd.state_indices(state, "test")
        if len(te_idx) < 30:
            continue

        X_te, y_te = yd.matrix(te_idx)
        c_pred = F.as_1d(central.predict(X_te))
        e_pred = apply_calibration(
            F.as_1d(joblib.load(node.artifact_path()).predict(X_te)),
            node.calibration_slope, node.calibration_intercept,
        )

        c_r2 = float(r2_score(y_te, c_pred))
        e_r2 = float(r2_score(y_te, e_pred))
        gap = c_r2 - e_r2

        rows.append({
            "state": state,
            "metric": "r2",
            "central_r2": round(c_r2, 4),
            "edge_r2": round(e_r2, 4),
            "gap": round(gap, 4),
            "central_mae": round(float(mean_absolute_error(y_te, c_pred)), 4),
            "edge_mae": round(float(mean_absolute_error(y_te, e_pred)), 4),
            "within_ceiling": bool(gap <= ACCURACY_GAP_CEILING),
            "n_eval": int(len(te_idx)),
            "currently_promoted": bool(node.promoted and node.enabled),
        })

    return rows


def run(demote: bool = False) -> Dict[str, Any]:
    report = {
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ceiling": ACCURACY_GAP_CEILING,
        "replicas": evaluate_replicas(),
        "states": evaluate_states(),
    }

    breaches = [r for r in report["states"] if not r["within_ceiling"]]
    report["states_evaluated"] = len(report["states"])
    report["states_within_ceiling"] = len(report["states"]) - len(breaches)
    report["states_breaching"] = len(breaches)

    if demote and breaches:
        for row in breaches:
            registry.set_enabled(row["state"], False)
            logger.warning("DEMOTED %s (gap %.4f > %.2f) -> central fallback",
                           row["state"], row["gap"], ACCURACY_GAP_CEILING)
        report["demoted"] = [r["state"] for r in breaches]

    EDGE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import warnings

    warnings.filterwarnings("ignore")

    ap = argparse.ArgumentParser()
    ap.add_argument("--demote", action="store_true",
                    help="disable nodes that breach the ceiling")
    args = ap.parse_args()

    rep = run(demote=args.demote)

    print("\n" + "=" * 78)
    print(f"ACCURACY-GAP REPORT   (ceiling = {ACCURACY_GAP_CEILING:.0%})")
    print("=" * 78)
    print("\nCompressed national replicas (edge-deployed, not regional):")
    print(f"  {'target':22s} {'metric':8s} {'central':>9s} {'edge':>9s} {'gap':>9s}  ok")
    for name, r in rep["replicas"].items():
        print(f"  {name:22s} {r['metric']:8s} {r['central']:9.4f} {r['edge']:9.4f} "
              f"{r['gap']:+9.4f}  {'Y' if r['within_ceiling'] else 'N'}")

    print(f"\nPer-state yield models (regionally specialised):")
    print(f"  {'state':28s} {'central':>9s} {'edge':>9s} {'gap':>9s}  {'n':>6s}  ok")
    for r in rep["states"]:
        print(f"  {r['state']:28s} {r['central_r2']:9.4f} {r['edge_r2']:9.4f} "
              f"{r['gap']:+9.4f}  {r['n_eval']:6d}  {'Y' if r['within_ceiling'] else 'N'}")

    print(f"\n  within ceiling : {rep['states_within_ceiling']}/{rep['states_evaluated']}")
    print(f"  breaching      : {rep['states_breaching']}")
    print(f"\nreport -> {REPORT_PATH}")
