"""One shared feature-engineering pipeline for central and edge training.

SRD section 2.3 requires a single pipeline used by both modes so that the
accuracy-gap comparison is fair and the output contract stays stable. Edge
training differs from central training only in *which rows* it receives --
never in how those rows are transformed.

The Advisor's five targets group onto three source datasets:

    crop_dataset_rebuilt.csv     -> crop recommendation          (1 target)
    irrigation_prediction.csv    -> sunlight, irr type, irr need (3 targets)
    crop_production + India Agri -> yield                        (1 target)

Feature engineering below is byte-for-byte identical to the pre-refactor
implementations in ``ml/pre_sowing_advisor/*/preprocessing.py``. Changing it
would change model inputs and therefore the prediction contract.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import (
    LabelEncoder,
    OrdinalEncoder,
    StandardScaler,
)

from ml import data_sources

logger = logging.getLogger(__name__)

RANDOM_STATE = 42
TEST_SIZE = 0.20
VAL_SIZE = 0.10


# ═══════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════

def as_1d(values) -> np.ndarray:
    """Flatten a predictor's output to shape (n,).

    Estimators disagree on output shape for classification: scikit-learn and
    XGBoost return (n,) while CatBoost returns (n, 1). Mixing the two inside a
    NumPy expression broadcasts (n,) against (n, 1) into an (n, n) matrix --
    silently, and catastrophically for memory. Every teacher prediction is
    normalised through here before it is combined with anything.
    """
    arr = np.asarray(values)
    return arr.reshape(-1) if arr.ndim > 1 else arr


def scalar(value) -> float:
    """First element of a prediction, regardless of 1-D or 2-D output shape."""
    return float(as_1d(value)[0])


def normalise_string(value: str) -> str:
    """Lowercase, strip, collapse internal whitespace to underscores."""
    return "_".join(str(value).strip().lower().split())


def normalise_state(value: str) -> str:
    """Canonical state key used for partitioning and edge-node lookup."""
    return normalise_string(value)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Crop Recommendation features
# ═══════════════════════════════════════════════════════════════════════════

CROP_RAW_FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
CROP_ENGINEERED = ["NP_ratio", "KP_ratio", "rainfall_humidity"]
CROP_ALL_FEATURES = CROP_RAW_FEATURES + CROP_ENGINEERED
CROP_TARGET = "label"
CROP_LABEL_MERGE = {"paddy": "rice"}


def load_crop_frame() -> pd.DataFrame:
    path = data_sources.crop_dataset()
    if path is None:
        raise FileNotFoundError("crop_dataset_rebuilt.csv not found")
    df = pd.read_csv(path)
    logger.info("crop: loaded %d rows x %d cols", *df.shape)
    return df


def clean_crop_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Drop nulls/dupes, lowercase labels, merge regional synonyms."""
    missing = set(CROP_RAW_FEATURES + [CROP_TARGET]) - set(df.columns)
    if missing:
        raise ValueError(f"crop dataset missing columns: {missing}")

    initial = len(df)
    df = df.dropna(subset=CROP_RAW_FEATURES + [CROP_TARGET]).drop_duplicates()
    df[CROP_TARGET] = df[CROP_TARGET].astype(str).str.strip().str.lower()
    df[CROP_TARGET] = df[CROP_TARGET].replace(CROP_LABEL_MERGE)

    logger.info("crop: cleaned %d -> %d rows, %d classes",
                initial, len(df), df[CROP_TARGET].nunique())
    return df.reset_index(drop=True)


def engineer_crop_features(df: pd.DataFrame) -> pd.DataFrame:
    """NP_ratio, KP_ratio, rainfall_humidity -- unchanged from baseline."""
    df = df.copy()
    df["NP_ratio"] = df["N"] / (df["P"] + 1)
    df["KP_ratio"] = df["K"] / (df["P"] + 1)
    df["rainfall_humidity"] = df["rainfall"] * df["humidity"] / 100.0
    return df


@dataclass
class CropData:
    X_train: np.ndarray
    X_val: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_val: np.ndarray
    y_test: np.ndarray
    scaler: StandardScaler
    label_encoder: LabelEncoder
    feature_names: list = field(default_factory=lambda: list(CROP_ALL_FEATURES))


def prepare_crop_data() -> CropData:
    """Full crop pipeline: load -> clean -> engineer -> encode -> split -> scale."""
    df = engineer_crop_features(clean_crop_frame(load_crop_frame()))

    X = df[CROP_ALL_FEATURES].values.astype(np.float64)
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(df[CROP_TARGET].values)

    X_tv, X_test, y_tv, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_tv, y_tv, test_size=VAL_SIZE / (1 - TEST_SIZE),
        random_state=RANDOM_STATE, stratify=y_tv
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)

    logger.info("crop: train=%d val=%d test=%d classes=%d",
                len(X_train), len(X_val), len(X_test), len(label_encoder.classes_))
    return CropData(X_train, X_val, X_test, y_train, y_val, y_test,
                    scaler, label_encoder)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Irrigation / Sunlight features  (3 targets, one preprocessor)
# ═══════════════════════════════════════════════════════════════════════════

IRR_NUMERIC = ["ph", "temperature", "humidity", "rainfall"]
IRR_ENGINEERED = [
    "temp_rainfall_ratio",
    "humidity_rainfall",
    "rainfall_log",
    "temp_humidity_interaction",
]
IRR_CATEGORICAL = ["crop", "soil_type", "season"]
IRR_ALL_FEATURES = IRR_NUMERIC + IRR_ENGINEERED + IRR_CATEGORICAL
IRR_TARGETS = ["sunlight_hours", "irrigation_type", "irrigation_need"]


def load_irrigation_frame() -> pd.DataFrame:
    path = data_sources.irrigation_dataset()
    if path is None:
        raise FileNotFoundError("irrigation_prediction.csv not found")
    df = pd.read_csv(path)
    logger.info("irrigation: loaded %d rows x %d cols", *df.shape)
    return df


def clean_irrigation_frame(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if col.lower().replace("_", "").replace(" ", "") == "sunlighthours":
            df = df.rename(columns={col: "sunlight_hours"})
            break

    missing = set(IRR_NUMERIC + IRR_CATEGORICAL + IRR_TARGETS) - set(df.columns)
    if missing:
        raise ValueError(f"irrigation dataset missing columns: {missing}")

    initial = len(df)
    df = df.dropna(subset=IRR_NUMERIC + IRR_CATEGORICAL + IRR_TARGETS).drop_duplicates()
    for col in IRR_CATEGORICAL + ["irrigation_type", "irrigation_need"]:
        df[col] = df[col].astype(str).apply(normalise_string)

    logger.info("irrigation: cleaned %d -> %d rows", initial, len(df))
    return df.reset_index(drop=True)


def engineer_irrigation_features(df: pd.DataFrame) -> pd.DataFrame:
    """4 derived numerics -- unchanged from baseline."""
    df = df.copy()
    df["temp_rainfall_ratio"] = df["temperature"] / (df["rainfall"] + 1)
    df["humidity_rainfall"] = df["humidity"] * df["rainfall"] / 100.0
    df["rainfall_log"] = np.log1p(df["rainfall"])
    df["temp_humidity_interaction"] = df["temperature"] * df["humidity"] / 100.0
    return df


def build_irrigation_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), IRR_NUMERIC + IRR_ENGINEERED),
            ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
             IRR_CATEGORICAL),
        ],
        remainder="drop",
    )


@dataclass
class IrrigationData:
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: pd.DataFrame
    y_test: pd.DataFrame
    preprocessor: ColumnTransformer
    encoders: dict
    feature_names: list = field(default_factory=lambda: list(IRR_ALL_FEATURES))


def prepare_irrigation_data() -> IrrigationData:
    """Full irrigation pipeline. Type and need are CLASSIFICATION targets."""
    df = engineer_irrigation_features(clean_irrigation_frame(load_irrigation_frame()))

    X = df[IRR_ALL_FEATURES]
    y = df[IRR_TARGETS].copy()

    encoders = {}
    for col in ["irrigation_type", "irrigation_need"]:
        enc = LabelEncoder()
        y[col] = enc.fit_transform(y[col])
        encoders[col] = enc

    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )

    preprocessor = build_irrigation_preprocessor()
    X_train = preprocessor.fit_transform(X_train_raw)
    X_test = preprocessor.transform(X_test_raw)

    logger.info("irrigation: train=%d test=%d types=%d needs=%d",
                len(X_train), len(X_test),
                len(encoders["irrigation_type"].classes_),
                len(encoders["irrigation_need"].classes_))
    return IrrigationData(X_train, X_test, y_train, y_test, preprocessor, encoders)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Yield features  -- THE ONLY STATE-AWARE PIPELINE
# ═══════════════════════════════════════════════════════════════════════════
# This is the one Advisor dataset carrying State/District, so it is the only
# target that supports genuinely regional (per-state) edge models.

YIELD_FEATURES = ["crop", "state", "district", "season"]
YIELD_TARGET = "yield"

#: A state needs at least this many usable rows to get its own edge model.
#: States below the floor are flagged sparse and stay on central fallback
#: (SRD section 7, and the sparse-data risk row in section 13).
MIN_ROWS_PER_STATE = 500


def load_yield_frame() -> pd.DataFrame:
    """Merge both yield sources into one canonical frame.

    Canonical columns: state, district, crop, season, year, area, production, yield
    """
    frames = []

    sec = data_sources.india_agri_csv()
    if sec is not None:
        df = pd.read_csv(sec)
        df = df.rename(columns={
            "State": "state", "District": "district", "Crop": "crop",
            "Season": "season", "Year": "year", "Area": "area",
            "Production": "production", "Yield": "yield",
        })
        frames.append(df[["state", "district", "crop", "season", "year",
                          "area", "production", "yield"]])
        logger.info("yield: India Agri -> %d rows", len(df))

    pri = data_sources.crop_production_xlsx()
    if pri is not None:
        df = pd.read_excel(pri)
        df = df.rename(columns={
            "State_Name": "state", "District_Name": "district", "label": "crop",
            "Season": "season", "Crop_Year": "year", "Area": "area",
            "Production": "production",
        })
        keep = ["state", "district", "crop", "season", "year", "area", "production"]
        df = df[[c for c in keep if c in df.columns]].copy()
        # Primary source has no yield column; derive it.
        df["yield"] = df["production"] / df["area"].replace(0, np.nan)
        frames.append(df)
        logger.info("yield: crop_production -> %d rows", len(df))

    if not frames:
        raise FileNotFoundError("No yield datasets found")

    combined = pd.concat(frames, ignore_index=True)
    logger.info("yield: combined -> %d rows", len(combined))
    return combined


def clean_yield_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise keys, drop unusable rows, clip extreme yields."""
    initial = len(df)
    df = df.dropna(subset=["state", "district", "crop", "season", "yield"]).copy()

    for col in ["state", "district", "crop", "season"]:
        df[col] = df[col].astype(str).apply(normalise_string)

    df = df[np.isfinite(df["yield"])]
    df = df[df["yield"] > 0]

    # Outlier removal must be PER CROP, not global.
    #
    # Production is denominated in mixed units across these sources -- Tonnes
    # for most crops, Nuts for coconut, Bales for cotton -- so the yield scale
    # is crop-dependent by construction. Sugarcane at ~53 and banana at ~22 are
    # real agronomic values, not errors. A single global quantile would delete
    # every high-yield crop while leaving each crop's own bad rows untouched.
    # Clipping within each crop removes true data errors and preserves the
    # legitimate scale differences that `crop` (a model feature) encodes.
    before = len(df)
    lo = df.groupby("crop")["yield"].transform(lambda s: s.quantile(0.01))
    hi = df.groupby("crop")["yield"].transform(lambda s: s.quantile(0.99))
    df = df[(df["yield"] >= lo) & (df["yield"] <= hi)]
    logger.info("yield: per-crop 1-99pct clip dropped %d rows", before - len(df))

    df = df.drop_duplicates(subset=["state", "district", "crop", "season", "year"])

    logger.info("yield: cleaned %d -> %d rows | %d states, %d districts, %d crops",
                initial, len(df), df.state.nunique(),
                df.district.nunique(), df.crop.nunique())
    return df.reset_index(drop=True)


@dataclass
class YieldEncoders:
    crop: LabelEncoder
    state: LabelEncoder
    district: LabelEncoder
    season: LabelEncoder

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Encode to integer codes as a DataFrame of CATEGORICAL columns.

        These four features are nominal -- district 47 and district 300 have no
        ordering relationship. Handing raw integer codes to a gradient booster
        as numeric invites it to split on "district < 173", which is
        meaningless, and to extrapolate without bound on rare combinations.
        In practice that produced yield predictions of 2493 t/ha and negative
        values for small states.

        Returning pandas ``category`` dtype lets every booster use its native
        categorical handling (LightGBM ``categorical_feature``, CatBoost
        ``cat_features``, XGBoost ``enable_categorical``) so splits are on set
        membership rather than a fabricated order. Unseen keys map to -1, which
        is a legitimate category in its own right.
        """
        def enc(le: LabelEncoder, values: pd.Series) -> np.ndarray:
            lookup = {c: i for i, c in enumerate(le.classes_)}
            return values.astype(str).map(lambda v: lookup.get(v, -1)).to_numpy()

        out = pd.DataFrame({
            "crop": enc(self.crop, df["crop"]),
            "state": enc(self.state, df["state"]),
            "district": enc(self.district, df["district"]),
            "season": enc(self.season, df["season"]),
        })
        return self.as_categorical(out)

    def as_categorical(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply a stable category dtype so train and predict agree on levels."""
        for col, le in (("crop", self.crop), ("state", self.state),
                        ("district", self.district), ("season", self.season)):
            levels = list(range(-1, len(le.classes_)))
            frame[col] = pd.Categorical(frame[col], categories=levels)
        return frame


def fit_yield_encoders(df: pd.DataFrame) -> YieldEncoders:
    """Fit encoders on the FULL national frame.

    Fitting globally (not per state) is deliberate: edge and central then share
    an identical feature space, which is what makes the accuracy-gap comparison
    meaningful and lets a compressed model be swapped in without retranslation.
    """
    def fit(col: str) -> LabelEncoder:
        le = LabelEncoder()
        le.fit(df[col].astype(str))
        return le

    return YieldEncoders(fit("crop"), fit("state"), fit("district"), fit("season"))


@dataclass
class YieldData:
    frame: pd.DataFrame           # cleaned, canonical, still row-addressable
    encoders: YieldEncoders
    train_idx: np.ndarray
    test_idx: np.ndarray

    def matrix(self, idx: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        sub = self.frame.iloc[idx]
        return self.encoders.transform(sub), sub[YIELD_TARGET].to_numpy()

    def state_indices(self, state: str, which: str = "train") -> np.ndarray:
        """Row positions for one state within the train or test split."""
        idx = self.train_idx if which == "train" else self.test_idx
        mask = self.frame.iloc[idx]["state"].to_numpy() == normalise_state(state)
        return idx[mask]

    def state_row_counts(self) -> pd.Series:
        return self.frame["state"].value_counts()

    def sparse_states(self, floor: int = MIN_ROWS_PER_STATE) -> list:
        counts = self.state_row_counts()
        return sorted(counts[counts < floor].index.tolist())

    def eligible_states(self, floor: int = MIN_ROWS_PER_STATE) -> list:
        counts = self.state_row_counts()
        return sorted(counts[counts >= floor].index.tolist())


def prepare_yield_data() -> YieldData:
    """Full yield pipeline with a stratified-by-state holdout.

    The test split is stratified on state so that every state has a
    representative held-out set for its own accuracy-gap evaluation (SRD
    section 7: 'a shared, representative held-out set per state').
    """
    df = clean_yield_frame(load_yield_frame())
    encoders = fit_yield_encoders(df)

    positions = np.arange(len(df))
    counts = df["state"].value_counts()

    # A state needs >= 2 rows to appear on both sides of a stratified split.
    # Single-row states (e.g. Laddakh) cannot be stratified at all, so their
    # rows go straight to train -- they are sparse-flagged and will fall back
    # to central regardless.
    splittable = df["state"].map(counts) >= 2
    strat_positions = positions[splittable.to_numpy()]
    leftover_positions = positions[~splittable.to_numpy()]

    train_idx, test_idx = train_test_split(
        strat_positions,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df["state"].to_numpy()[strat_positions],
    )
    if len(leftover_positions):
        train_idx = np.concatenate([train_idx, leftover_positions])
        logger.info("yield: %d row(s) from single-row states added to train",
                    len(leftover_positions))

    logger.info("yield: train=%d test=%d | eligible states=%d sparse=%d",
                len(train_idx), len(test_idx),
                len(df["state"].value_counts()[lambda s: s >= MIN_ROWS_PER_STATE]),
                len(df["state"].value_counts()[lambda s: s < MIN_ROWS_PER_STATE]))
    return YieldData(df, encoders, train_idx, test_idx)
