"""
TerraMind - Unified Inference Pipeline

Orchestrates the full prediction flow:
  Step 1: Validate & normalise input
  Step 2: Select execution mode (central / edge / local_only)
  Step 3: Run Crop Recommender
  Step 4: Apply bounded local adaptation (edge mode)
  Step 5: Run Yield Predictor for selected crop
  Step 6: Run Agri-Condition Advisor
  Step 7: Apply district irrigation prior
  Step 8: Run District Intelligence Engine
  Step 9: Return unified JSON response
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np

from backend.core.config import MODEL_VERSION
from backend.core.logging_config import log
from backend.models.model_registry import registry
from backend.services.preprocessing_service import PreprocessingService
from backend.services.local_adaptation_service import LocalAdaptationService
from backend.services.district_intelligence import DistrictIntelligenceEngine
from backend.services.irrigation_prior import IrrigationPriorService
from backend.services.sync_service import get_sync_status
from backend.utils.normalizers import normalise_input


class InferencePipeline:
    """Stateless orchestrator; loads models from registry on first call."""

    def __init__(self):
        self.preprocessor = PreprocessingService()
        self.adaptation   = LocalAdaptationService()
        self.intelligence = DistrictIntelligenceEngine()
        self.irr_prior    = IrrigationPriorService()
        log.info("InferencePipeline initialised")

    def predict(self, raw_input: dict) -> dict:
        """
        Run full inference pipeline and return unified response.
        """
        t_start = time.time()
        system_notes: list[str] = []

        # ── Step 1: Validate & normalise ───────────────────────────────
        inputs = normalise_input(raw_input)
        mode = inputs["mode"]
        artifact_mode = "edge" if mode == "edge" else "central"

        # ── Step 2: Load models ────────────────────────────────────────
        try:
            cr = registry.crop_recommender(artifact_mode)
        except FileNotFoundError:
            # Fall back to central if edge not available
            cr = registry.crop_recommender("central")
            system_notes.append("Edge crop recommender unavailable; fell back to central")
            if mode == "edge":
                artifact_mode = "central"

        try:
            yp = registry.yield_predictor(artifact_mode)
        except FileNotFoundError:
            yp = registry.yield_predictor("central")
            system_notes.append("Edge yield predictor unavailable; fell back to central")

        try:
            aa = registry.agri_advisor(artifact_mode)
        except FileNotFoundError:
            aa = registry.agri_advisor("central")
            system_notes.append("Edge agri advisor unavailable; fell back to central")

        # ── Step 3: Crop Recommender ───────────────────────────────────
        X_crop = self.preprocessor.for_crop_recommender(inputs, cr["scaler"])
        proba = cr["model"].predict_proba(X_crop)[0]
        classes = cr["label_encoder"].classes_

        crop_prob_map = {cls: float(p) for cls, p in zip(classes, proba)}

        # ── Step 4: Local adaptation (edge mode) ──────────────────────
        adaptation_result = {"adaptation_applied": False}
        if mode == "edge":
            adaptation_result = self.adaptation.adapt(
                state=inputs["state"],
                district=inputs["district"],
                season=inputs["season"],
                crop_probabilities=crop_prob_map,
            )
            if adaptation_result["adaptation_applied"]:
                crop_prob_map = adaptation_result["adapted_probs"]

        # Build top-3
        sorted_crops = sorted(crop_prob_map.items(), key=lambda x: x[1], reverse=True)
        top3 = []
        for crop_name, final_conf in sorted_crops[:3]:
            base_conf = adaptation_result.get("original_probs", crop_prob_map).get(crop_name, final_conf)
            adj = adaptation_result.get("adjustments", {}).get(crop_name, 0.0)
            top3.append({
                "crop": crop_name,
                "base_confidence": round(float(base_conf), 4),
                "local_adjustment": round(float(adj), 4),
                "final_confidence": round(float(final_conf), 4),
            })
        selected_crop = top3[0]["crop"]

        # ── Step 5: Yield Predictor ────────────────────────────────────
        yield_result = self._predict_yield(inputs, selected_crop, yp)

        # ── Step 6: Agri-Condition Advisor ─────────────────────────────
        agri_result = self._predict_agri(inputs, selected_crop, aa)

        # ── Step 7: Irrigation prior ───────────────────────────────────
        irr_prior_result = self.irr_prior.apply_prior(
            state=inputs["state"],
            district=inputs["district"],
            crop=selected_crop,
            predicted_type=agri_result["irrigation_type"],
            type_probabilities=agri_result.get("type_probabilities"),
        )
        agri_result["irrigation_type"] = irr_prior_result["adjusted_type"]
        agri_result["district_prior_used"] = irr_prior_result["prior_used"]
        agri_result["irrigation_reasoning"] = irr_prior_result["reasoning"]
        agri_result["district_irrigation_summary"] = irr_prior_result["district_irrigation_summary"]
        agri_result["crop_irrigated_pct"] = irr_prior_result["crop_irrigated_pct"]

        # ── Step 8: District Intelligence ──────────────────────────────
        district_intel = self.intelligence.query(
            state=inputs["state"],
            district=inputs["district"],
            crop=selected_crop,
        )

        # ── Step 9: Assemble response ─────────────────────────────────
        latency_ms = round((time.time() - t_start) * 1000, 1)

        sync_status = get_sync_status()

        response = {
            "input_summary": {
                k: v for k, v in inputs.items()
                if k not in ("mode",)
            },
            "execution_mode": mode,
            "model_version": MODEL_VERSION,
            "adaptation_applied": adaptation_result.get("adaptation_applied", False),
            "sync_status": {
                "edge_version":   sync_status.get("edge_version", "n/a"),
                "central_version": sync_status.get("central_version", "n/a"),
                "last_sync":      sync_status.get("last_sync"),
                "stale":          sync_status.get("stale", False),
            },
            "crop_recommender": {
                "top_3": top3,
                "selected_crop": selected_crop,
                "adaptation_factors": adaptation_result.get("top_factors", []),
            },
            "yield_predictor": yield_result,
            "agri_condition_advisor": {
                "sunlight_hours":              agri_result["sunlight_hours"],
                "irrigation_type":             agri_result["irrigation_type"],
                "irrigation_need":             agri_result["irrigation_need"],
                "explanation":                 agri_result.get("irrigation_reasoning", ""),
                "district_prior_used":         agri_result.get("district_prior_used", False),
                "district_irrigation_summary": agri_result.get("district_irrigation_summary", ""),
                "crop_irrigated_pct":          agri_result.get("crop_irrigated_pct"),
            },
            "district_intelligence": district_intel,
            "system_notes": system_notes,
            "latency_ms": latency_ms,
        }

        log.info("Inference complete: mode=%s crop=%s latency=%.0fms",
                 mode, selected_crop, latency_ms)
        return response

    # ── Private helpers ────────────────────────────────────────────────

    def _predict_yield(self, inputs: dict, crop: str, yp: dict) -> dict:
        """Run yield predictor and return result dict."""
        try:
            X = self.preprocessor.for_yield_predictor(
                inputs, crop,
                yp["scaler"], yp["le_crop"], yp["le_state"],
                yp["le_district"], yp["le_season"], yp["metadata"],
            )
            # Enrich with cached stats
            crop_stats = registry.edge_cache("district_crop_stats")
            X = self.preprocessor.enrich_yield_features_from_cache(
                X, inputs["state"], inputs["district"], crop, crop_stats
            )

            pred = float(yp["model"].predict(X)[0])
            meta = yp["metadata"]
            r_std = meta.get("residual_std", 0.5)
            lower = round(max(pred + meta.get("residual_q10", -r_std), 0), 3)
            upper = round(pred + meta.get("residual_q90", r_std), 3)

            return {
                "expected_yield": round(pred, 3),
                "unit": "t/ha",
                "confidence_band": {"lower": lower, "upper": upper},
                "explanation": f"Based on historical patterns for {crop} in {inputs['district']}, {inputs['state']}",
            }
        except Exception as exc:
            log.warning("Yield prediction failed: %s", exc)
            return {
                "expected_yield": None,
                "unit": "t/ha",
                "confidence_band": {"lower": None, "upper": None},
                "explanation": f"Yield prediction unavailable: {exc}",
            }

    def _predict_agri(self, inputs: dict, crop: str, aa: dict) -> dict:
        """Run agri condition advisor and return result dict."""
        try:
            X = self.preprocessor.for_agri_advisor(
                inputs, crop,
                aa["scaler"], aa["le_crop"], aa["le_soil_type"], aa["le_season"],
            )

            sunlight = float(aa["sunlight_model"].predict(X)[0])
            irr_type_enc = aa["irrigation_type_model"].predict(X)[0]
            irr_need_enc = aa["irrigation_need_model"].predict(X)[0]

            irr_type = aa["le_irrigation_type"].inverse_transform([irr_type_enc])[0]
            irr_need = aa["le_irrigation_need"].inverse_transform([irr_need_enc])[0]

            # Get type probabilities for prior
            type_proba = aa["irrigation_type_model"].predict_proba(X)[0]
            type_classes = aa["le_irrigation_type"].classes_
            type_prob_map = {cls: float(p) for cls, p in zip(type_classes, type_proba)}

            return {
                "sunlight_hours": round(sunlight, 1),
                "irrigation_type": irr_type,
                "irrigation_need": irr_need,
                "type_probabilities": type_prob_map,
            }
        except Exception as exc:
            log.warning("Agri advisor prediction failed: %s", exc)
            return {
                "sunlight_hours": None,
                "irrigation_type": "unknown",
                "irrigation_need": "unknown",
                "type_probabilities": {},
            }


# Module-level singleton
_pipeline: InferencePipeline | None = None


def get_pipeline() -> InferencePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = InferencePipeline()
    return _pipeline
