"""Head-to-head test-set comparison for the central yield model.

The CV bake-off in ``train_central`` ranks candidates on a 120k-row subsample,
and only the winner is refit on the full training split and scored on the
holdout. That is enough to pick a winner but not enough to decide whether a
smaller model *matches* the winner's accuracy -- which is the only condition
under which swapping it in is worthwhile.

This module refits every candidate on the FULL training split, scores each on
the same holdout, and reports accuracy alongside size and latency. Accuracy is
the deciding criterion; size only breaks ties.

Run:
    python -m ml.advisor_edge.yield_shootout
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

import numpy as np
from sklearn.metrics import mean_absolute_error, r2_score

from ml.advisor_edge import candidates as C
from ml.advisor_edge import features as F

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CENTRAL_DIR = PROJECT_ROOT / "backend" / "artifacts" / "central" / "advisor"
REPORT_PATH = CENTRAL_DIR / "yield_shootout.json"

RANDOM_STATE = 42


def _high_capacity_variants() -> Dict[str, Callable]:
    """Stronger booster configs than the default central set.

    The stock configurations were tuned for a balanced bake-off across five
    targets. Yield is the hardest target and the one whose artifact dominates
    the footprint, so it is worth asking whether a booster given more capacity
    closes the gap to RandomForest.
    """
    out: Dict[str, Callable] = {}
    if C.HAS_LGBM:
        from lightgbm import LGBMRegressor

        out["LightGBM-XL"] = lambda: LGBMRegressor(
            n_estimators=2000, learning_rate=0.05, num_leaves=511,
            max_depth=-1, min_child_samples=10,
            subsample=0.9, subsample_freq=1, colsample_bytree=0.9,
            n_jobs=-1, random_state=RANDOM_STATE, verbose=-1,
        )
    if C.HAS_CATBOOST:
        from catboost import CatBoostRegressor

        out["CatBoost-XL"] = lambda: CatBoostRegressor(
            iterations=2000, depth=12, learning_rate=0.05,
            cat_features=["crop", "state", "district", "season"],
            random_seed=RANDOM_STATE, verbose=0, allow_writing_files=False,
        )
    if C.HAS_XGB:
        from xgboost import XGBRegressor

        out["XGBoost-XL"] = lambda: XGBRegressor(
            n_estimators=1500, max_depth=12, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9,
            tree_method="hist", enable_categorical=True, max_cat_to_onehot=1,
            n_jobs=-1, random_state=RANDOM_STATE, verbosity=0,
        )
    return out


def run() -> Dict[str, Any]:
    yd = F.prepare_yield_data()
    X_tr, y_tr = yd.matrix(yd.train_idx)
    X_te, y_te = yd.matrix(yd.test_idx)
    ceiling = C.fit_yield_ceiling(y_tr)

    factories: Dict[str, Callable] = dict(C.yield_regressors(edge=False))
    factories.update(_high_capacity_variants())

    logger.info("refitting %d candidates on full %d rows, scoring on %d holdout rows",
                len(factories), len(X_tr), len(X_te))

    rows: List[Dict[str, Any]] = []
    for name, factory in factories.items():
        try:
            t0 = time.perf_counter()
            model = factory()
            model.fit(X_tr, y_tr)
            fit_s = time.perf_counter() - t0

            pred = C.clamp_yield(F.as_1d(model.predict(X_te)), ceiling)
            rows.append({
                "algorithm": name,
                "test_r2": round(float(r2_score(y_te, pred)), 4),
                "test_mae": round(float(mean_absolute_error(y_te, pred)), 4),
                "fit_seconds": round(fit_s, 1),
                "latency_ms": round(C.measure_inference_latency(model, X_te), 4),
                "size_mb": round(C.model_size_kb(model) / 1024.0, 1),
            })
            logger.info("  %-14s R2=%.4f  MAE=%8.3f  %6.1fMB  %6.2fms  (fit %.0fs)",
                        name, rows[-1]["test_r2"], rows[-1]["test_mae"],
                        rows[-1]["size_mb"], rows[-1]["latency_ms"], fit_s)
        except Exception as exc:
            logger.warning("  %-14s FAILED: %s", name, exc)

    rows.sort(key=lambda r: r["test_r2"], reverse=True)
    best = rows[0]

    # A challenger only wins if it matches the incumbent's accuracy (within
    # noise) AND is materially smaller. Accuracy is never traded away.
    TOLERANCE = 0.002
    smaller_equal = [
        r for r in rows
        if r["test_r2"] >= best["test_r2"] - TOLERANCE and r["size_mb"] < best["size_mb"]
    ]
    recommendation = min(smaller_equal, key=lambda r: r["size_mb"]) if smaller_equal else best

    report = {
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_train": int(len(X_tr)),
        "n_test": int(len(X_te)),
        "yield_ceiling": ceiling,
        "accuracy_tolerance": TOLERANCE,
        "candidates": rows,
        "most_accurate": best["algorithm"],
        "recommended": recommendation["algorithm"],
        "recommendation_basis": (
            "matches best accuracy within tolerance at smaller size"
            if recommendation is not best else
            "most accurate; no smaller candidate matches it"
        ),
    }
    CENTRAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import warnings

    warnings.filterwarnings("ignore")
    rep = run()

    print("\n" + "=" * 74)
    print("CENTRAL YIELD MODEL -- FULL TEST-SET SHOOTOUT")
    print("=" * 74)
    print(f"  {'algorithm':16s} {'test R2':>9s} {'test MAE':>10s} {'size MB':>9s} {'ms':>8s}")
    for r in rep["candidates"]:
        mark = ""
        if r["algorithm"] == rep["most_accurate"]:
            mark = "  <- most accurate"
        if r["algorithm"] == rep["recommended"] and rep["recommended"] != rep["most_accurate"]:
            mark = "  <- RECOMMENDED"
        print(f"  {r['algorithm']:16s} {r['test_r2']:9.4f} {r['test_mae']:10.3f} "
              f"{r['size_mb']:9.1f} {r['latency_ms']:8.2f}{mark}")
    print(f"\n  recommended: {rep['recommended']}  ({rep['recommendation_basis']})")
    print(f"  report -> {REPORT_PATH}")
