"""Candidate algorithm registry for central and edge training.

SRD FR-5 requires benchmarking at minimum Random Forest, XGBoost, LightGBM and
CatBoost for both modes, selecting per mode/state on cross-validated
performance, with the comparison logged and reproducible.

Edge configurations are deliberately smaller and shallower than central ones:
the point of edge is latency and footprint (NFR-1), so a candidate that wins on
raw score but loses badly on inference latency is not a good edge choice. The
central configurations carry no such constraint -- central must remain the most
accurate reference model (Hard Constraint 4).
"""

from __future__ import annotations

import logging
from typing import Callable, Dict

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

logger = logging.getLogger(__name__)

RANDOM_STATE = 42

# Optional dependencies -- absent libraries are skipped, never fatal.
try:
    from xgboost import XGBClassifier, XGBRegressor
    HAS_XGB = True
except ImportError:  # pragma: no cover
    HAS_XGB = False

try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    HAS_LGBM = True
except ImportError:  # pragma: no cover
    HAS_LGBM = False

try:
    from catboost import CatBoostClassifier, CatBoostRegressor
    HAS_CATBOOST = True
except ImportError:  # pragma: no cover
    HAS_CATBOOST = False


def available() -> Dict[str, bool]:
    return {
        "RandomForest": True,
        "XGBoost": HAS_XGB,
        "LightGBM": HAS_LGBM,
        "CatBoost": HAS_CATBOOST,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Central candidates -- accuracy first
# ═══════════════════════════════════════════════════════════════════════════

def central_classifiers(n_classes: int) -> Dict[str, Callable]:
    c: Dict[str, Callable] = {
        "RandomForest": lambda: RandomForestClassifier(
            n_estimators=300, max_depth=20, min_samples_split=5,
            min_samples_leaf=2, n_jobs=-1, random_state=RANDOM_STATE,
        ),
    }
    if HAS_XGB:
        c["XGBoost"] = lambda: XGBClassifier(
            n_estimators=400, max_depth=8, learning_rate=0.08,
            subsample=0.85, colsample_bytree=0.85, tree_method="hist",
            objective="multi:softprob" if n_classes > 2 else "binary:logistic",
            num_class=n_classes if n_classes > 2 else None,
            n_jobs=-1, random_state=RANDOM_STATE, verbosity=0,
        )
    if HAS_LGBM:
        c["LightGBM"] = lambda: LGBMClassifier(
            n_estimators=400, max_depth=10, learning_rate=0.08,
            subsample=0.85, colsample_bytree=0.85, num_leaves=63,
            n_jobs=-1, random_state=RANDOM_STATE, verbose=-1,
        )
    if HAS_CATBOOST:
        c["CatBoost"] = lambda: CatBoostClassifier(
            iterations=400, depth=8, learning_rate=0.08,
            random_seed=RANDOM_STATE, verbose=0, allow_writing_files=False,
        )
    return c


def central_regressors() -> Dict[str, Callable]:
    r: Dict[str, Callable] = {
        "RandomForest": lambda: RandomForestRegressor(
            n_estimators=200, max_depth=24, min_samples_leaf=2,
            n_jobs=-1, random_state=RANDOM_STATE,
        ),
    }
    if HAS_XGB:
        r["XGBoost"] = lambda: XGBRegressor(
            n_estimators=500, max_depth=10, learning_rate=0.08,
            subsample=0.85, colsample_bytree=0.85, tree_method="hist",
            n_jobs=-1, random_state=RANDOM_STATE, verbosity=0,
        )
    if HAS_LGBM:
        r["LightGBM"] = lambda: LGBMRegressor(
            n_estimators=500, max_depth=12, learning_rate=0.08,
            subsample=0.85, colsample_bytree=0.85, num_leaves=127,
            n_jobs=-1, random_state=RANDOM_STATE, verbose=-1,
        )
    if HAS_CATBOOST:
        r["CatBoost"] = lambda: CatBoostRegressor(
            iterations=500, depth=10, learning_rate=0.08,
            random_seed=RANDOM_STATE, verbose=0, allow_writing_files=False,
        )
    return r


# ═══════════════════════════════════════════════════════════════════════════
# Edge candidates -- latency and footprint first (NFR-1)
# ═══════════════════════════════════════════════════════════════════════════

def edge_classifiers(n_classes: int) -> Dict[str, Callable]:
    c: Dict[str, Callable] = {
        "RandomForest": lambda: RandomForestClassifier(
            n_estimators=80, max_depth=12, min_samples_leaf=2,
            n_jobs=-1, random_state=RANDOM_STATE,
        ),
    }
    if HAS_XGB:
        c["XGBoost"] = lambda: XGBClassifier(
            n_estimators=150, max_depth=6, learning_rate=0.12,
            subsample=0.85, colsample_bytree=0.85, tree_method="hist",
            n_jobs=-1, random_state=RANDOM_STATE, verbosity=0,
        )
    if HAS_LGBM:
        c["LightGBM"] = lambda: LGBMClassifier(
            n_estimators=150, max_depth=7, learning_rate=0.12,
            num_leaves=31, n_jobs=-1, random_state=RANDOM_STATE, verbose=-1,
        )
    if HAS_CATBOOST:
        c["CatBoost"] = lambda: CatBoostClassifier(
            iterations=150, depth=6, learning_rate=0.12,
            random_seed=RANDOM_STATE, verbose=0, allow_writing_files=False,
        )
    return c


def edge_regressors() -> Dict[str, Callable]:
    r: Dict[str, Callable] = {
        "RandomForest": lambda: RandomForestRegressor(
            n_estimators=60, max_depth=14, min_samples_leaf=3,
            n_jobs=-1, random_state=RANDOM_STATE,
        ),
    }
    if HAS_XGB:
        r["XGBoost"] = lambda: XGBRegressor(
            n_estimators=200, max_depth=7, learning_rate=0.12,
            subsample=0.85, colsample_bytree=0.85, tree_method="hist",
            n_jobs=-1, random_state=RANDOM_STATE, verbosity=0,
        )
    if HAS_LGBM:
        r["LightGBM"] = lambda: LGBMRegressor(
            n_estimators=200, max_depth=8, learning_rate=0.12,
            num_leaves=31, n_jobs=-1, random_state=RANDOM_STATE, verbose=-1,
        )
    if HAS_CATBOOST:
        r["CatBoost"] = lambda: CatBoostRegressor(
            iterations=200, depth=7, learning_rate=0.12,
            random_seed=RANDOM_STATE, verbose=0, allow_writing_files=False,
        )
    return r


# ═══════════════════════════════════════════════════════════════════════════
# Yield candidates -- all four features are nominal categoricals
# ═══════════════════════════════════════════════════════════════════════════
# crop / state / district / season have no ordering. Every candidate here is
# configured for native categorical handling so splits are on set membership,
# not on integer codes. RandomForest has no categorical support in
# scikit-learn, so it is trained on the codes as-is and simply tends to lose
# the bake-off -- which is the correct outcome rather than a special case.

def _yield_rf(edge: bool):
    return (RandomForestRegressor(n_estimators=60, max_depth=14, min_samples_leaf=3,
                                  n_jobs=-1, random_state=RANDOM_STATE)
            if edge else
            RandomForestRegressor(n_estimators=200, max_depth=24, min_samples_leaf=2,
                                  n_jobs=-1, random_state=RANDOM_STATE))


def yield_regressors(edge: bool = False) -> Dict[str, Callable]:
    r: Dict[str, Callable] = {"RandomForest": lambda: _yield_rf(edge)}

    if HAS_XGB:
        r["XGBoost"] = lambda: XGBRegressor(
            n_estimators=200 if edge else 500,
            max_depth=7 if edge else 10,
            learning_rate=0.12 if edge else 0.08,
            subsample=0.85, colsample_bytree=0.85,
            tree_method="hist", enable_categorical=True, max_cat_to_onehot=1,
            n_jobs=-1, random_state=RANDOM_STATE, verbosity=0,
        )
    if HAS_LGBM:
        r["LightGBM"] = lambda: LGBMRegressor(
            n_estimators=200 if edge else 500,
            max_depth=8 if edge else 12,
            learning_rate=0.12 if edge else 0.08,
            num_leaves=31 if edge else 127,
            n_jobs=-1, random_state=RANDOM_STATE, verbose=-1,
        )
    if HAS_CATBOOST:
        r["CatBoost"] = lambda: CatBoostRegressor(
            iterations=200 if edge else 500,
            depth=7 if edge else 10,
            learning_rate=0.12 if edge else 0.08,
            cat_features=["crop", "state", "district", "season"],
            random_seed=RANDOM_STATE, verbose=0, allow_writing_files=False,
        )
    return r


#: Negative yield is physically impossible, so the floor is a hard 0.
YIELD_FLOOR = 0.0

#: The ceiling CANNOT be a single agronomic constant. Production is denominated
#: in mixed units across these sources -- Tonnes for most crops, Nuts for
#: coconut, Bales for cotton -- so observed "yield" legitimately spans four
#: orders of magnitude (rice ~2, sugarcane ~54, coconut ~20,000). A tight
#: global cap silently destroys the high-unit crops: capping at 200 dropped
#: measured test R^2 from 0.73 to 0.03.
#:
#: The ceiling is therefore derived from the training distribution with
#: headroom, and persisted alongside the model. This default is only a
#: fallback for when that metadata is unavailable.
DEFAULT_YIELD_CEILING = 25_000.0


def fit_yield_ceiling(y_train) -> float:
    """Derive an inference ceiling from the training targets, with headroom."""
    top = float(np.max(y_train)) if len(y_train) else DEFAULT_YIELD_CEILING
    return round(top * 1.1, 4)


def clamp_yield(values, ceiling: float = DEFAULT_YIELD_CEILING):
    """Constrain predictions to a physically plausible range.

    Guards against unbounded extrapolation on unseen crop/district
    combinations without truncating legitimate high-unit crops.
    """
    return np.clip(values, YIELD_FLOOR, ceiling)


# ═══════════════════════════════════════════════════════════════════════════
# Measurement helpers used by the model-comparison log
# ═══════════════════════════════════════════════════════════════════════════

def measure_inference_latency(model, X: np.ndarray, repeats: int = 5) -> float:
    """Median single-row predict latency in milliseconds.

    Single-row is the shape that matters: the Advisor serves one farm at a
    time, so batch throughput would misrepresent the edge latency claim.
    """
    import time

    row = X[:1]
    model.predict(row)  # warm caches / lazy init

    timings = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        model.predict(row)
        timings.append((time.perf_counter() - t0) * 1000.0)
    return float(np.median(timings))


def model_size_kb(model) -> float:
    """Serialized size in KB -- the edge footprint number."""
    import io

    import joblib

    buf = io.BytesIO()
    joblib.dump(model, buf)
    return buf.tell() / 1024.0
