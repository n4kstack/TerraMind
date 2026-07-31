"""Two-mode Advisor pipeline -- identical output contract, different serving path.

This is the integration seam. ``ml/pre_sowing_pipeline.run_standard_pipeline``
delegates here when the two-mode artifacts are present, and falls back to the
original per-model path when they are not. The public entry point keeps its
signature (Deliverable 3) and the response keeps every field name, nesting
level and legacy duplicate it had before the refactor (Hard Constraint 2).

Only steps 2-4 of the original pipeline change -- the three model calls become
one routed call. District Intelligence and the Irrigation Prior are untouched
and still run centrally, because they read reference datasets rather than
models and carry no per-state training.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ml.advisor_edge import router as R
from ml.advisor_edge.router import central_artifacts

logger = logging.getLogger(__name__)


def two_mode_available() -> bool:
    """True when the central artifact set is complete enough to serve."""
    try:
        return central_artifacts.ready()
    except Exception:
        return False


def _to_dict(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    out = {}
    for key in ["N", "P", "K", "temperature", "humidity", "rainfall", "ph",
                "soil_type", "season", "state", "district", "area",
                "state_name", "district_name", "model_mode"]:
        if hasattr(payload, key):
            out[key] = getattr(payload, key)
    return out


def run_two_mode_pipeline(payload: Any) -> Dict[str, Any]:
    """Run the Advisor through the central/edge router.

    Returns exactly the pre-refactor v1 response shape. The chosen mode is
    recorded in ``system_notes`` (a pre-existing free-text list) and never as a
    new field, so the v1 schema is unchanged.
    """
    response, _decision, _intel = run_two_mode_pipeline_detailed(payload)
    return response


def run_two_mode_pipeline_detailed(
    payload: Any,
) -> tuple[Dict[str, Any], Any, Dict[str, Any]]:
    """Same as :func:`run_two_mode_pipeline`, plus the routing context.

    Returns ``(response, decision, district_intel)``.

    The legacy ``/predict`` surface exposes fields the v1 response does not --
    ``execution_mode``, and the raw chart series ``ten_year_trajectory_data`` /
    ``irrigation_infrastructure_data``. Those are handed back separately rather
    than folded into ``response``, because the v1 response shape is frozen by
    the schema-regression baseline and must not gain fields. Callers that need
    the frozen shape use :func:`run_two_mode_pipeline`.
    """
    from ml.pre_sowing_advisor.district_intelligence import get_district_intelligence
    from ml.pre_sowing_advisor.irrigation_prior import apply_irrigation_prior

    data = _to_dict(payload)
    system_notes: list[str] = []

    state = data.get("state") or data.get("state_name", "")
    district = data.get("district") or data.get("district_name", "")
    season = data.get("season", "kharif")
    area = data.get("area")

    input_summary = {
        "N": data.get("N"), "P": data.get("P"), "K": data.get("K"),
        "ph": data.get("ph"), "temperature": data.get("temperature"),
        "humidity": data.get("humidity"), "rainfall": data.get("rainfall"),
        "soil_type": data.get("soil_type"), "state": state,
        "district": district, "season": season, "area": area,
    }

    # ── Routed inference: crop + yield + sunlight + irrigation ─────────────
    routed = dict(data)
    routed["state"] = state
    routed["district"] = district
    routed["season"] = season

    predictions, decision = R.route_and_predict(routed)
    selected_crop = predictions["crop"]

    logger.info("advisor routed: state=%s mode=%s reason=%s conf=%.3f",
                decision.state, decision.mode, decision.reason,
                decision.confidence or 0.0)

    yield_result = {
        "expected_yield": predictions["expected_yield"],
        "unit": "t/ha",
        "confidence_band": _confidence_band(predictions["expected_yield"]),
        "explanation": (
            f"Predicted yield of {predictions['expected_yield']:.2f} t/ha for "
            f"{selected_crop} in {district}, {state} ({season})."
        ),
    }

    irrigation_result = {
        "sunlight_hours": predictions["sunlight_hours"],
        "irrigation_type": predictions["irrigation_type"],
        "irrigation_need": predictions["irrigation_need"],
        "irrigation_type_probabilities": predictions["irrigation_type_probabilities"],
        "explanation": (
            f"For {selected_crop} in {season} season on "
            f"{data.get('soil_type', 'loamy')} soil: recommended "
            f"{predictions['irrigation_type']} irrigation with "
            f"{predictions['irrigation_need']} intensity. Expected sunlight: "
            f"{predictions['sunlight_hours']} hours/day."
        ),
    }

    # ── District Intelligence (unchanged, central reference data) ──────────
    try:
        district_intel = get_district_intelligence(
            state=state, district=district, crop=selected_crop, season=season,
        )
        if district_intel.get("notes"):
            system_notes.extend(district_intel["notes"])
    except Exception as exc:
        logger.error("District intelligence failed: %s", exc)
        district_intel = _empty_district_intel()
        system_notes.append("District intelligence is temporarily unavailable.")

    # ── Irrigation Prior (unchanged) ───────────────────────────────────────
    try:
        irrigation_result = apply_irrigation_prior(
            irrigation_result=irrigation_result, state=state, district=district,
            crop=selected_crop, district_intelligence=district_intel,
        )
    except Exception as exc:
        logger.error("Irrigation prior failed: %s", exc)
        irrigation_result.setdefault("district_prior_used", False)
        irrigation_result.setdefault("district_irrigation_summary", "")
        irrigation_result.setdefault("irrigation_reasoning", "")

    # Explain the district prior in system_notes -- a pre-existing free-text
    # list, so nothing is added to the schema.
    crop_meta = predictions.get("crop_prior") or {}
    if crop_meta.get("prior_applied"):
        top_local = ", ".join(crop_meta.get("top_district_crops", []))
        scope = crop_meta.get("scope", "district")
        if crop_meta.get("reordered"):
            system_notes.append(
                f"Crop choice adjusted for local cultivation history "
                f"({scope}-level: {top_local}); soil profile alone favoured "
                f"{crop_meta.get('model_top')}."
            )
        else:
            system_notes.append(
                f"Crop choice consistent with {scope} cultivation history "
                f"({top_local})."
            )

    system_notes.append(f"Served via {decision.mode} mode ({decision.reason}).")

    # ── Response assembly: byte-for-byte the pre-refactor shape ────────────
    return {
        "success": True,
        "input_summary": input_summary,
        "crop_recommender": {
            "top_3": predictions["top_3"],
            "selected_crop": selected_crop,
            "selected_confidence": predictions["confidence"],
        },
        "yield_predictor": {
            "expected_yield": yield_result["expected_yield"],
            "unit": yield_result["unit"],
            "confidence_band": yield_result["confidence_band"],
            "explanation": yield_result["explanation"],
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
        # Legacy backward-compatible keys -- present before the refactor, kept.
        "recommended_crop": selected_crop,
        "predicted_yield": yield_result["expected_yield"],
        "expected_yield": yield_result["expected_yield"],
        "sunlight_hours": irrigation_result.get("sunlight_hours", 0.0),
        "irrigation_type": irrigation_result.get("irrigation_type", ""),
        "irrigation_need": irrigation_result.get("irrigation_need", ""),
        "confidence": predictions["confidence"],
        "top_3_predictions": predictions["top_3"],
        "model_type": "standard",
    }, decision, district_intel


def _confidence_band(point: float) -> Dict[str, float]:
    """Residual-derived band, read from central metadata when available."""
    try:
        import json

        from ml.advisor_edge.registry import CENTRAL_DIR

        meta = json.loads((CENTRAL_DIR / "central_metadata.json").read_text(encoding="utf-8"))
        y = meta["targets"]["yield_predictor"]
        lower = max(point + y.get("residual_q10", -y.get("residual_std", 0.5)), 0.0)
        upper = point + y.get("residual_q90", y.get("residual_std", 0.5))
        return {"lower": round(lower, 4), "upper": round(upper, 4)}
    except Exception:
        return {"lower": round(max(point - 0.5, 0.0), 4), "upper": round(point + 0.5, 4)}


def _empty_district_intel() -> Dict[str, Any]:
    return {
        "district_crop_share_percent": None,
        "yield_trend": "unavailable",
        "top_competing_crops": [],
        "best_historical_season": "unknown",
        "ten_year_trajectory_summary": "District intelligence unavailable.",
        "irrigation_infrastructure_summary": "Unavailable.",
        "irrigation_infrastructure_breakdown": {},
        "crop_irrigated_area_percent": None,
        "insights": [],
        "notes": ["District intelligence data unavailable in this deployment."],
    }
