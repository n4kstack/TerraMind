"""
TerraMind - Local-Only Benchmark Model Training

Trains per-state partition models for crop recommendation
using only local data. Used exclusively for benchmarking -
NOT for production.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import (
    CROP_REC_FEATURES, LOCAL_ARTIFACTS, TEST_SIZE, RANDOM_SEED,
)
from backend.core.logging_config import log
from backend.utils.data_loader import load_crop_dataset, load_combined_yield_data
from backend.utils.partitioning import partition_by_state
from backend.utils.metrics import classification_metrics, log_metrics


def train_local_only_crop_models():
    """
    Train separate crop recommender per state partition.
    Uses yield data to determine state-level crop presence,
    then trains on the crop_dataset with only those labels present.
    """
    log.info("============================================")
    log.info("  Training Local-Only Benchmark Models")
    log.info("============================================")

    crop_df = load_crop_dataset()
    yield_df = load_combined_yield_data()

    # Get state -> crop mapping from yield data
    state_crops = yield_df.groupby("State", observed=True)["Crop"].apply(set).to_dict()

    # For benchmark: train a model per state using only crops found in that state
    out_dir = LOCAL_ARTIFACTS / "crop_recommender"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results = {}

    for state, crops_in_state in state_crops.items():
        # Filter crop dataset for crops present in this state
        mask = crop_df["label"].isin(crops_in_state)
        df_local = crop_df[mask].copy()

        if len(df_local) < 50 or df_local["label"].nunique() < 2:
            log.info("Skipping state '%s' - insufficient data (%d rows, %d classes)",
                     state, len(df_local), df_local["label"].nunique())
            continue

        X = df_local[CROP_REC_FEATURES].values
        le = LabelEncoder()
        y = le.fit_transform(df_local["label"].values)

        if len(np.unique(y)) < 2:
            continue

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED,
            stratify=y if len(np.unique(y)) >= 2 else None,
        )

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s  = scaler.transform(X_test)

        model = RandomForestClassifier(
            n_estimators=100, max_depth=15, random_state=RANDOM_SEED, n_jobs=-1
        )
        model.fit(X_train_s, y_train)

        y_pred = model.predict(X_test_s)
        y_proba = model.predict_proba(X_test_s)
        metrics = classification_metrics(
            y_test, y_pred, y_proba,
            labels=list(range(len(le.classes_)))
        )

        # Save per-state model
        state_dir = out_dir / state.replace(" ", "_")
        state_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model,  state_dir / "model.joblib")
        joblib.dump(scaler, state_dir / "scaler.joblib")
        joblib.dump(le,     state_dir / "label_encoder.joblib")

        all_results[state] = {
            "accuracy": metrics["accuracy"],
            "macro_f1": metrics["macro_f1"],
            "n_samples": len(df_local),
            "n_classes": len(le.classes_),
        }
        log.info("State %-20s -> acc=%.3f  F1=%.3f  (%d samples, %d classes)",
                 state, metrics["accuracy"], metrics["macro_f1"],
                 len(df_local), len(le.classes_))

    # Save summary
    with open(out_dir / "local_benchmark_summary.json", "w") as f:
        json.dump(all_results, f, indent=2)

    log.info("Local-only benchmark training complete: %d states", len(all_results))
    return all_results


if __name__ == "__main__":
    train_local_only_crop_models()
