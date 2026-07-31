"""
TerraMind - Benchmark Service

Compares Centralized vs Edge vs Local-Only systems on:
  - Top-1 / Top-3 accuracy
  - Macro precision / recall / F1
  - Latency
  - Artifact size
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import (
    CROP_REC_FEATURES, CENTRAL_ARTIFACTS, EDGE_ARTIFACTS, LOCAL_ARTIFACTS,
    TEST_SIZE, RANDOM_SEED,
)
from backend.core.logging_config import log
from backend.utils.data_loader import load_crop_dataset
from backend.utils.metrics import classification_metrics
from backend.models.model_registry import ModelRegistry
import joblib


def _dir_size_kb(path: Path) -> float:
    total = 0
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return round(total / 1024, 1)


def benchmark_all() -> dict:
    """Run full benchmark across all three systems."""
    log.info("============================================")
    log.info("  Running Benchmark: Central vs Edge vs Local")
    log.info("============================================")

    # Prepare test data
    df = load_crop_dataset()
    X = df[CROP_REC_FEATURES].values
    le = LabelEncoder()
    y = le.fit_transform(df["label"].values)
    labels = list(range(len(le.classes_)))

    _, X_test, _, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=y
    )

    results = {}

    # ── System A: Centralized ─────────────────────────────────────────
    try:
        reg = ModelRegistry()
        reg.clear_cache()
        cr = reg.crop_recommender("central")

        X_test_s = cr["scaler"].transform(X_test)
        t0 = time.time()
        y_pred = cr["model"].predict(X_test_s)
        y_proba = cr["model"].predict_proba(X_test_s)
        latency = (time.time() - t0) * 1000 / len(X_test)

        m = classification_metrics(y_test, y_pred, y_proba, labels)
        m["avg_latency_ms"] = round(latency, 3)
        m["artifact_size_kb"] = _dir_size_kb(CENTRAL_ARTIFACTS / "crop_recommender")
        results["central"] = m
        log.info("Central: acc=%.4f F1=%.4f top3=%.4f latency=%.3fms",
                 m["accuracy"], m["macro_f1"], m.get("top3_accuracy", 0), latency)
    except Exception as exc:
        log.error("Central benchmark failed: %s", exc)
        results["central"] = {"error": str(exc)}

    # ── System B: Edge ────────────────────────────────────────────────
    try:
        reg.clear_cache()
        cr_edge = reg.crop_recommender("edge")

        X_test_s = cr_edge["scaler"].transform(X_test)
        t0 = time.time()
        y_pred = cr_edge["model"].predict(X_test_s)
        y_proba = cr_edge["model"].predict_proba(X_test_s)
        latency = (time.time() - t0) * 1000 / len(X_test)

        m = classification_metrics(y_test, y_pred, y_proba, labels)
        m["avg_latency_ms"] = round(latency, 3)
        m["artifact_size_kb"] = _dir_size_kb(EDGE_ARTIFACTS / "crop_recommender")
        results["edge"] = m

        # Gap analysis
        if "central" in results and "accuracy" in results["central"]:
            gap = results["central"]["accuracy"] - m["accuracy"]
            m["accuracy_gap_vs_central"] = round(gap * 100, 2)
            log.info("Edge: acc=%.4f F1=%.4f gap=%.2fpp",
                     m["accuracy"], m["macro_f1"], gap * 100)
    except Exception as exc:
        log.error("Edge benchmark failed: %s", exc)
        results["edge"] = {"error": str(exc)}

    # ── System C: Local-Only ──────────────────────────────────────────
    try:
        summary_path = LOCAL_ARTIFACTS / "crop_recommender" / "local_benchmark_summary.json"
        if summary_path.exists():
            with open(summary_path) as f:
                local_summary = json.load(f)
            avg_acc = np.mean([v["accuracy"] for v in local_summary.values()])
            avg_f1  = np.mean([v["macro_f1"] for v in local_summary.values()])
            results["local_only"] = {
                "avg_accuracy": round(float(avg_acc), 4),
                "avg_macro_f1": round(float(avg_f1), 4),
                "n_states": len(local_summary),
                "per_state": local_summary,
                "artifact_size_kb": _dir_size_kb(LOCAL_ARTIFACTS / "crop_recommender"),
            }
            if "central" in results and "accuracy" in results["central"]:
                gap = results["central"]["accuracy"] - avg_acc
                results["local_only"]["accuracy_gap_vs_central"] = round(gap * 100, 2)
            log.info("Local-only: avg_acc=%.4f avg_F1=%.4f (%d states)",
                     avg_acc, avg_f1, len(local_summary))
        else:
            results["local_only"] = {"error": "Local models not trained yet"}
    except Exception as exc:
        log.error("Local benchmark failed: %s", exc)
        results["local_only"] = {"error": str(exc)}

    # ── Summary table ─────────────────────────────────────────────────
    summary = {
        "systems": results,
        "target_gap_pp": 5.0,
        "edge_within_target": (
            results.get("edge", {}).get("accuracy_gap_vs_central", 99) <= 5.0
            if "accuracy_gap_vs_central" in results.get("edge", {}) else None
        ),
    }

    # Save report
    report_path = CENTRAL_ARTIFACTS / "benchmark_report.json"
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    log.info("Benchmark report saved to %s", report_path)

    return summary


if __name__ == "__main__":
    benchmark_all()
