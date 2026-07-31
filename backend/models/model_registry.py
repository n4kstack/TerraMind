"""
TerraMind - Model Registry

Manages loading and versioning of trained model artifacts
for central, edge, and local modes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import joblib

from backend.core.config import CENTRAL_ARTIFACTS, EDGE_ARTIFACTS, LOCAL_ARTIFACTS
from backend.core.logging_config import log


class ModelRegistry:
    """Singleton-style registry caching loaded models in memory."""

    _instance: Optional["ModelRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
        return cls._instance

    def _artifact_dir(self, mode: str) -> Path:
        return {
            "central":    CENTRAL_ARTIFACTS,
            "edge":       EDGE_ARTIFACTS,
            "local_only": LOCAL_ARTIFACTS,
        }.get(mode, CENTRAL_ARTIFACTS)

    def _load(self, path: Path) -> Any:
        """Load a joblib artifact with caching."""
        key = str(path)
        if key not in self._cache:
            if not path.exists():
                raise FileNotFoundError(f"Artifact not found: {path}")
            self._cache[key] = joblib.load(path)
            log.info("Loaded artifact: %s", path.name)
        return self._cache[key]

    def _load_json(self, path: Path) -> dict:
        key = str(path)
        if key not in self._cache:
            if not path.exists():
                return {}
            with open(path) as f:
                self._cache[key] = json.load(f)
        return self._cache[key]

    # ── Crop Recommender ─────────────────────────────────────────────
    def crop_recommender(self, mode: str = "central"):
        d = self._artifact_dir(mode) / "crop_recommender"
        return {
            "model":         self._load(d / "model.joblib"),
            "scaler":        self._load(d / "scaler.joblib"),
            "label_encoder": self._load(d / "label_encoder.joblib"),
            "metadata":      self._load_json(d / "metadata.json"),
        }

    # ── Yield Predictor ──────────────────────────────────────────────
    def yield_predictor(self, mode: str = "central"):
        d = self._artifact_dir(mode) / "yield_predictor"
        return {
            "model":       self._load(d / "model.joblib"),
            "scaler":      self._load(d / "scaler.joblib"),
            "le_crop":     self._load(d / "le_crop.joblib"),
            "le_state":    self._load(d / "le_state.joblib"),
            "le_district": self._load(d / "le_district.joblib"),
            "le_season":   self._load(d / "le_season.joblib"),
            "metadata":    self._load_json(d / "metadata.json"),
        }

    # ── Agri Advisor ─────────────────────────────────────────────────
    def agri_advisor(self, mode: str = "central"):
        d = self._artifact_dir(mode) / "agri_advisor"
        return {
            "sunlight_model":       self._load(d / "sunlight_model.joblib"),
            "irrigation_type_model": self._load(d / "irrigation_type_model.joblib"),
            "irrigation_need_model": self._load(d / "irrigation_need_model.joblib"),
            "scaler":               self._load(d / "scaler.joblib"),
            "le_crop":              self._load(d / "le_crop.joblib"),
            "le_soil_type":         self._load(d / "le_soil_type.joblib"),
            "le_season":            self._load(d / "le_season.joblib"),
            "le_irrigation_type":   self._load(d / "le_irrigation_type.joblib"),
            "le_irrigation_need":   self._load(d / "le_irrigation_need.joblib"),
            "metadata":             self._load_json(d / "metadata.json"),
        }

    # ── Edge caches ──────────────────────────────────────────────────
    def edge_cache(self, name: str) -> dict:
        path = EDGE_ARTIFACTS / f"{name}.json"
        return self._load_json(path)

    # ── Metadata / version ───────────────────────────────────────────
    def model_version(self, mode: str = "central") -> str:
        d = self._artifact_dir(mode) / "crop_recommender" / "metadata.json"
        meta = self._load_json(d)
        return meta.get("version", "unknown")

    def clear_cache(self):
        self._cache.clear()
        log.info("Model registry cache cleared")


# Module-level convenience instance
registry = ModelRegistry()
