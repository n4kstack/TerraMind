"""Hyperparameter search for the central Advisor models.

The first-pass configurations in ``candidates.py`` were hand-set to give four
algorithms a fair bake-off, not to extract the best score from any one of
them. This module runs a randomized search per target and reports the honest
gain, so tuned parameters are adopted only when they actually beat what is
already deployed on the same holdout.

Every score here is measured on the held-out split. Nothing is adopted on a
cross-validation number alone.

Run:
    python -m ml.advisor_edge.tune                 # all targets
    python -m ml.advisor_edge.tune --target irrigation_type
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, r2_score
from sklearn.model_selection import RandomizedSearchCV

from ml.advisor_edge import candidates as C
from ml.advisor_edge import features as F

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CENTRAL_DIR = PROJECT_ROOT / "backend" / "artifacts" / "central" / "advisor"
REPORT_PATH = CENTRAL_DIR / "tuning_report.json"

N_ITER = 25
CV_FOLDS = 3
SEED = 42


# ═══════════════════════════════════════════════════════════════════════════
# Search spaces
# ═══════════════════════════════════════════════════════════════════════════

def _catboost_space() -> Dict[str, list]:
    return {
        "iterations": [300, 500, 800, 1200],
        "depth": [4, 6, 8, 10],
        "learning_rate": [0.02, 0.05, 0.08, 0.12],
        "l2_leaf_reg": [1.0, 3.0, 5.0, 9.0],
        "random_strength": [0.5, 1.0, 2.0],
        "bagging_temperature": [0.0, 0.5, 1.0],
    }


def _lgbm_space() -> Dict[str, list]:
    return {
        "n_estimators": [300, 600, 1000, 1500],
        "num_leaves": [31, 63, 127, 255],
        "learning_rate": [0.02, 0.05, 0.08, 0.12],
        "min_child_samples": [5, 10, 20, 40],
        "subsample": [0.7, 0.85, 1.0],
        "colsample_bytree": [0.7, 0.85, 1.0],
        "reg_lambda": [0.0, 1.0, 5.0],
    }


def _rf_space() -> Dict[str, list]:
    return {
        "n_estimators": [200, 400, 700],
        "max_depth": [8, 14, 20, None],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
        "max_features": ["sqrt", "log2", None],
    }


# ═══════════════════════════════════════════════════════════════════════════

def _search(estimator, space, X, y, scoring: str) -> tuple[Any, Dict[str, Any], float]:
    rs = RandomizedSearchCV(
        estimator, space, n_iter=N_ITER, cv=CV_FOLDS, scoring=scoring,
        n_jobs=1, random_state=SEED, refit=True, error_score="raise",
    )
    t0 = time.perf_counter()
    rs.fit(X, y)
    return rs.best_estimator_, rs.best_params_, time.perf_counter() - t0


def tune_target(
    name: str,
    X_tr, y_tr, X_te, y_te,
    task: str,
    incumbent_path: Path,
    builders: Dict[str, tuple],
) -> Dict[str, Any]:
    """Search each family, keep the best holdout score, compare to incumbent."""
    scorer = accuracy_score if task == "classification" else r2_score
    scoring = "accuracy" if task == "classification" else "r2"

    incumbent_score = None
    if incumbent_path.exists():
        try:
            model = joblib.load(incumbent_path)
            incumbent_score = float(scorer(y_te, F.as_1d(model.predict(X_te))))
        except Exception as exc:
            logger.warning("  could not score incumbent: %s", exc)

    logger.info("[%s] incumbent holdout %s = %s", name, scoring,
                f"{incumbent_score:.4f}" if incumbent_score is not None else "n/a")

    results = []
    for family, (factory, space) in builders.items():
        try:
            best, params, secs = _search(factory(), space, X_tr, y_tr, scoring)
            score = float(scorer(y_te, F.as_1d(best.predict(X_te))))
            results.append({
                "family": family, "holdout": round(score, 4),
                "params": {k: (v if not isinstance(v, np.generic) else v.item())
                           for k, v in params.items()},
                "search_seconds": round(secs, 1),
                "model": best,
            })
            logger.info("  %-12s tuned holdout=%.4f  (%.0fs)", family, score, secs)
        except Exception as exc:
            logger.warning("  %-12s search failed: %s", family, exc)

    if not results:
        return {"target": name, "status": "no_search_succeeded",
                "incumbent": incumbent_score}

    best = max(results, key=lambda r: r["holdout"])
    improved = incumbent_score is None or best["holdout"] > incumbent_score

    if improved:
        joblib.dump(best["model"], incumbent_path)
        logger.info("  ADOPTED %s: %.4f -> %.4f", best["family"],
                    incumbent_score if incumbent_score is not None else float("nan"),
                    best["holdout"])
    else:
        logger.info("  KEPT incumbent (%.4f >= tuned %.4f)",
                    incumbent_score, best["holdout"])

    return {
        "target": name,
        "task": task,
        "metric": scoring,
        "incumbent_holdout": incumbent_score,
        "best_family": best["family"],
        "tuned_holdout": best["holdout"],
        "adopted": bool(improved),
        "best_params": best["params"],
        "all": [{k: v for k, v in r.items() if k != "model"} for r in results],
    }


def run(only: Optional[str] = None) -> Dict[str, Any]:
    report: Dict[str, Any] = {"tuned_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                              "n_iter": N_ITER, "cv_folds": CV_FOLDS, "targets": {}}

    def want(t: str) -> bool:
        return only is None or only == t

    clf_builders: Dict[str, tuple] = {}
    reg_builders: Dict[str, tuple] = {}
    if C.HAS_CATBOOST:
        from catboost import CatBoostClassifier, CatBoostRegressor
        clf_builders["CatBoost"] = (
            lambda: CatBoostClassifier(random_seed=SEED, verbose=0, allow_writing_files=False),
            _catboost_space())
        reg_builders["CatBoost"] = (
            lambda: CatBoostRegressor(random_seed=SEED, verbose=0, allow_writing_files=False),
            _catboost_space())
    if C.HAS_LGBM:
        from lightgbm import LGBMClassifier, LGBMRegressor
        clf_builders["LightGBM"] = (
            lambda: LGBMClassifier(random_state=SEED, verbose=-1, n_jobs=-1), _lgbm_space())
        reg_builders["LightGBM"] = (
            lambda: LGBMRegressor(random_state=SEED, verbose=-1, n_jobs=-1), _lgbm_space())
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    clf_builders["RandomForest"] = (
        lambda: RandomForestClassifier(random_state=SEED, n_jobs=-1), _rf_space())
    reg_builders["RandomForest"] = (
        lambda: RandomForestRegressor(random_state=SEED, n_jobs=-1), _rf_space())

    # ── crop ───────────────────────────────────────────────────────────────
    if want("crop"):
        crop = F.prepare_crop_data()
        report["targets"]["crop"] = tune_target(
            "crop", crop.X_train, crop.y_train, crop.X_test, crop.y_test,
            "classification", CENTRAL_DIR / "crop_model.pkl", clf_builders)

    # ── irrigation family ──────────────────────────────────────────────────
    if any(want(t) for t in ("sunlight", "irrigation_type", "irrigation_need")):
        irr = F.prepare_irrigation_data()
        if want("sunlight"):
            report["targets"]["sunlight"] = tune_target(
                "sunlight", irr.X_train, irr.y_train["sunlight_hours"].to_numpy(),
                irr.X_test, irr.y_test["sunlight_hours"].to_numpy(),
                "regression", CENTRAL_DIR / "sunlight_model.pkl", reg_builders)
        for tgt in ("irrigation_type", "irrigation_need"):
            if want(tgt):
                report["targets"][tgt] = tune_target(
                    tgt, irr.X_train, irr.y_train[tgt].to_numpy(),
                    irr.X_test, irr.y_test[tgt].to_numpy(),
                    "classification", CENTRAL_DIR / f"{tgt}_model.pkl", clf_builders)

    CENTRAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import warnings

    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=None)
    args = ap.parse_args()

    rep = run(args.target)
    print("\n" + "=" * 70)
    print("HYPERPARAMETER TUNING")
    print("=" * 70)
    print(f"  {'target':20s} {'incumbent':>11s} {'tuned':>9s} {'family':13s} adopted")
    for t, r in rep["targets"].items():
        inc = r.get("incumbent_holdout")
        print(f"  {t:20s} {inc if inc is None else f'{inc:11.4f}'} "
              f"{r.get('tuned_holdout', float('nan')):9.4f} "
              f"{r.get('best_family',''):13s} {r.get('adopted')}")
