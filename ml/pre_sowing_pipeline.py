"""
Unified Pre-Sowing Advisory Pipeline.

Orchestrates all 3 models + district intelligence engine + irrigation prior
into a single deterministic response.

Pipeline:
    1. Validate input
    2. Run Crop Recommender (Model 1) → top-3 + selected crop
    3. Run Yield Predictor (Model 2) → yield + confidence band
    4. Run Pre-Sowing Advisor (Model 3) → sunlight + irrigation
    5. Apply District Irrigation Prior
    6. Run District Intelligence Engine
    7. Return unified JSON response
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _to_input_dict(payload: Any) -> Dict[str, Any]:
    """Normalise object/dict payload into plain dict."""
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    out = {}
    for key in [
        "N", "P", "K", "temperature", "humidity", "rainfall", "ph",
        "soil_type", "season", "state", "district", "area",
        "state_name", "district_name", "model_mode",
    ]:
        if hasattr(payload, key):
            out[key] = getattr(payload, key)
    return out


def run_standard_pipeline(payload: Any) -> Dict[str, Any]:
    """Run the full pre-sowing advisory pipeline.

    Returns a unified JSON-serialisable response matching the API spec.
    """
    from ml.pre_sowing_advisor.crop_recommendation.predict import predict_crop
    from ml.pre_sowing_advisor.yield_prediction.predict import predict_yield
    from ml.pre_sowing_advisor.irrigation_sunlight.predict import predict_irrigation_advisory
    from ml.pre_sowing_advisor.district_intelligence import get_district_intelligence
    from ml.pre_sowing_advisor.irrigation_prior import apply_irrigation_prior

    data = _to_input_dict(payload)
    system_notes = []

    # Resolve state/district keys (support both old and new key names)
    state = data.get("state") or data.get("state_name", "")
    district = data.get("district") or data.get("district_name", "")
    season = data.get("season", "kharif")
    area = data.get("area")

    # ── Step 1: Input summary ──────────────────────────────────────────────
    input_summary = {
        "N": data.get("N"),
        "P": data.get("P"),
        "K": data.get("K"),
        "ph": data.get("ph"),
        "temperature": data.get("temperature"),
        "humidity": data.get("humidity"),
        "rainfall": data.get("rainfall"),
        "soil_type": data.get("soil_type"),
        "state": state,
        "district": district,
        "season": season,
        "area": area,
    }

    # ── Step 2: Crop Recommender ───────────────────────────────────────────
    try:
        crop_result = predict_crop({
            "N": float(data["N"]),
            "P": float(data["P"]),
            "K": float(data["K"]),
            "temperature": float(data["temperature"]),
            "humidity": float(data["humidity"]),
            "rainfall": float(data["rainfall"]),
            "ph": float(data["ph"]),
        })
        selected_crop = crop_result["selected_crop"]
        logger.info("Crop Recommender → selected: %s", selected_crop)
    except Exception as e:
        logger.error("Crop recommendation failed: %s", e)
        raise RuntimeError(f"Crop recommendation failed: {e}")

    # ── Step 3: Yield Predictor ────────────────────────────────────────────
    try:
        yield_input = {
            "crop": selected_crop,
            "state": state,
            "district": district,
            "season": season,
        }
        yield_result = predict_yield(yield_input)
        logger.info("Yield Predictor → %.4f t/ha", yield_result["expected_yield"])
    except FileNotFoundError:
        logger.warning("Yield model artifact missing; returning graceful fallback")
        yield_result = {
            "expected_yield": 0.0,
            "unit": "t/ha",
            "confidence_band": {"lower": 0.0, "upper": 0.0},
            "explanation": "Yield prediction is temporarily unavailable in this deployment.",
        }
    except Exception as e:
        logger.error("Yield prediction failed: %s", e)
        yield_result = {
            "expected_yield": 0.0,
            "unit": "t/ha",
            "confidence_band": {"lower": 0.0, "upper": 0.0},
            "explanation": f"Yield prediction unavailable: {e}",
        }
        system_notes.append("Yield prediction is temporarily unavailable.")

    # ── Step 4: Pre-Sowing Advisor ────────────────────────────────────
    try:
        irrigation_input = {
            "crop": selected_crop,
            "ph": float(data["ph"]),
            "temperature": float(data["temperature"]),
            "humidity": float(data["humidity"]),
            "rainfall": float(data["rainfall"]),
            "soil_type": data.get("soil_type", "loamy"),
            "season": season,
        }
        irrigation_result = predict_irrigation_advisory(irrigation_input)
        logger.info("Pre-Sowing Advisor → type=%s, need=%s",
                    irrigation_result["irrigation_type"],
                    irrigation_result["irrigation_need"])
    except Exception as e:
        logger.error("Irrigation advisory failed: %s", e)
        irrigation_result = {
            "sunlight_hours": 6.0,
            "irrigation_type": "sprinkler",
            "irrigation_need": "medium",
            "irrigation_type_probabilities": {},
            "explanation": f"Irrigation advisory unavailable: {e}",
        }
        system_notes.append(f"Irrigation advisory error: {e}")

    # ── Step 5: District Intelligence ──────────────────────────────────────
    try:
        district_intel = get_district_intelligence(
            state=state,
            district=district,
            crop=selected_crop,
            season=season,
        )
        if district_intel.get("notes"):
            system_notes.extend(district_intel["notes"])
        logger.info("District Intelligence generated.")
    except Exception as e:
        logger.error("District intelligence failed: %s", e)
        district_intel = {
            "district_crop_share_percent": None,
            "yield_trend": "unavailable",
            "top_competing_crops": [],
            "best_historical_season": "unknown",
            "ten_year_trajectory_summary": "District intelligence unavailable.",
            "irrigation_infrastructure_summary": "Unavailable.",
            "crop_irrigated_area_percent": None,
            "notes": [str(e)],
        }
        system_notes.append("District intelligence is temporarily unavailable.")

    # ── Step 6: Apply Irrigation Prior ─────────────────────────────────────
    try:
        irrigation_result = apply_irrigation_prior(
            irrigation_result=irrigation_result,
            state=state,
            district=district,
            crop=selected_crop,
            district_intelligence=district_intel,
        )
        logger.info("Irrigation prior applied: %s", irrigation_result.get("district_prior_used"))
    except Exception as e:
        logger.error("Irrigation prior failed: %s", e)
        irrigation_result["district_prior_used"] = False
        irrigation_result["district_irrigation_summary"] = ""
        irrigation_result["irrigation_reasoning"] = ""
        system_notes.append(f"Irrigation prior error: {e}")

    # ── Step 7: Build Unified Response ─────────────────────────────────────
    response = {
        "success": True,
        "input_summary": input_summary,
        "crop_recommender": {
            "top_3": crop_result.get("top_3", []),
            "selected_crop": selected_crop,
            "selected_confidence": crop_result.get("selected_confidence", 0.0),
        },
        "yield_predictor": {
            "expected_yield": yield_result.get("expected_yield", 0.0),
            "unit": yield_result.get("unit", "t/ha"),
            "confidence_band": yield_result.get("confidence_band", {"lower": 0.0, "upper": 0.0}),
            "explanation": yield_result.get("explanation", ""),
        },
        "agri_condition_advisor": {
            "sunlight_hours": irrigation_result.get("sunlight_hours", 0.0),
            "irrigation_type": irrigation_result.get("irrigation_type", ""),
            "irrigation_need": irrigation_result.get("irrigation_need", ""),
            "explanation": irrigation_result.get("explanation", ""),
            "district_prior_used": irrigation_result.get("district_prior_used", False),
            "district_irrigation_summary": irrigation_result.get("district_irrigation_summary", ""),
            "irrigation_reasoning": irrigation_result.get("irrigation_reasoning", ""),
            "irrigation_type_probabilities": irrigation_result.get("irrigation_type_probabilities", {}),
        },
        "district_intelligence": {
            "district_crop_share_percent": district_intel.get("district_crop_share_percent"),
            "yield_trend": district_intel.get("yield_trend", ""),
            "top_competing_crops": district_intel.get("top_competing_crops", []),
            "best_historical_season": district_intel.get("best_historical_season", ""),
            "ten_year_trajectory_summary": district_intel.get("ten_year_trajectory_summary", ""),
            "irrigation_infrastructure_summary": district_intel.get("irrigation_infrastructure_summary", ""),
            "irrigation_infrastructure_breakdown": district_intel.get("irrigation_infrastructure_breakdown", {}),
            "crop_irrigated_area_percent": district_intel.get("crop_irrigated_area_percent"),
            "insights": district_intel.get("insights", []),
        },
        "system_notes": system_notes,
        # Legacy backward-compatible keys
        "recommended_crop": selected_crop,
        "predicted_yield": yield_result.get("expected_yield", 0.0),
        "expected_yield": yield_result.get("expected_yield", 0.0),
        "sunlight_hours": irrigation_result.get("sunlight_hours", 0.0),
        "irrigation_type": irrigation_result.get("irrigation_type", ""),
        "irrigation_need": irrigation_result.get("irrigation_need", ""),
        "confidence": crop_result.get("selected_confidence", 0.0),
        "top_3_predictions": crop_result.get("top_3", []),
        "model_type": "standard",
    }

    logger.info("Pipeline complete → %s", selected_crop)
    return response
