"""
TerraMind - Prediction API routes.
"""
from __future__ import annotations

import json
import time
from fastapi import APIRouter, HTTPException
from backend.schemas.request_response import PredictRequest, PredictResponse
from backend.services.inference_pipeline import get_pipeline
from backend.core.logging_config import log
from backend.core.config import MODEL_VERSION
from ml.pre_sowing_pipeline import run_standard_pipeline

router = APIRouter(tags=["prediction"])


def _fallback_predict(req: PredictRequest) -> dict:
    """Serve /predict from the two-mode router, mapped to the legacy shape.

    ``execution_mode`` reports the mode that ACTUALLY served the request as
    decided by the router -- not the mode the caller asked for. A request may
    ask for edge and be answered by central (no node, disabled, breaker open,
    low confidence), and the UI should show what happened.
    """
    t_start = time.time()
    payload = req.model_dump()
    payload["model_mode"] = "standard"

    try:
        from ml.advisor_edge.pipeline import run_two_mode_pipeline_detailed

        result, decision = run_two_mode_pipeline_detailed(payload)
        mode = decision.mode
    except Exception:
        result = run_standard_pipeline(payload)
        mode = payload.get("mode", "central")

    top3 = [
        {
            "crop": item.get("crop", "unknown"),
            "base_confidence": float(item.get("confidence", 0.0)),
            "local_adjustment": 0.0,
            "final_confidence": float(item.get("confidence", 0.0)),
        }
        for item in result.get("crop_recommender", {}).get("top_3", [])
    ]

    district = result.get("district_intelligence", {})
    agri = result.get("agri_condition_advisor", {})
    latency_ms = round((time.time() - t_start) * 1000, 1)

    return {
        "input_summary": result.get("input_summary", payload),
        "execution_mode": mode,
        "model_version": MODEL_VERSION,
        "adaptation_applied": False,
        "sync_status": {
            "edge_version": "n/a",
            "central_version": "n/a",
            "last_sync": None,
            "stale": False,
        },
        "crop_recommender": {
            "top_3": top3,
            "selected_crop": result.get("crop_recommender", {}).get("selected_crop", "unknown"),
            "adaptation_factors": [],
        },
        "yield_predictor": result.get("yield_predictor", {
            "expected_yield": None,
            "unit": "t/ha",
            "confidence_band": {"lower": None, "upper": None},
            "explanation": "Yield prediction unavailable",
        }),
        "agri_condition_advisor": {
            "sunlight_hours": agri.get("sunlight_hours"),
            "irrigation_type": agri.get("irrigation_type", "unknown"),
            "irrigation_need": agri.get("irrigation_need", "unknown"),
            "explanation": agri.get("explanation", ""),
            "district_prior_used": bool(agri.get("district_prior_used", False)),
            "district_irrigation_summary": agri.get("district_irrigation_summary", ""),
            "crop_irrigated_pct": agri.get("crop_irrigated_pct"),
        },
        "district_intelligence": {
            "district_crop_share_percent": district.get("district_crop_share_percent"),
            "yield_trend": district.get("yield_trend"),
            "top_competing_crops": district.get("top_competing_crops", []),
            "best_historical_season": district.get("best_historical_season"),
            "ten_year_trajectory_summary": district.get("ten_year_trajectory_summary"),
            "ten_year_trajectory_data": district.get("ten_year_trajectory_data"),
            "irrigation_infrastructure_summary": district.get("irrigation_infrastructure_summary"),
            "irrigation_infrastructure_data": district.get("irrigation_infrastructure_data"),
            "crop_irrigated_area_percent": district.get("crop_irrigated_area_percent"),
            "notes": district.get("notes", []),
        },
        "system_notes": result.get("system_notes", []),
        "latency_ms": latency_ms,
    }


@router.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """
    Run the full pre-sowing prediction pipeline.

    Exactly two modes exist:
      - **central**: full-dataset reference models, universal fallback
      - **edge**: the state's regional node when one is qualified

    The routed two-mode pipeline is the primary path so this endpoint serves
    the same retrained models as ``/api/v1/advisor/predict``. The legacy
    ``InferencePipeline`` remains only as a fallback for deployments that
    still carry the old per-mode artifact tree; without it this route would
    silently keep serving pre-refactor models.
    """
    try:
        from ml.advisor_edge.pipeline import two_mode_available

        if two_mode_available():
            return _fallback_predict(req)
    except Exception as exc:
        log.warning("Two-mode pipeline unavailable on /predict: %s", exc)

    try:
        pipeline = get_pipeline()
        return pipeline.predict(req.model_dump())
    except FileNotFoundError as exc:
        log.warning("Legacy /predict artifacts missing, using fallback pipeline: %s", exc)
        try:
            return _fallback_predict(req)
        except Exception as fallback_exc:
            raise HTTPException(status_code=503, detail=f"Models not trained yet: {fallback_exc}")
    except Exception as exc:
        log.error("Prediction error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/metadata")
async def metadata():
    """Return model versions, training dates, and dataset info."""
    from backend.core.config import CENTRAL_ARTIFACTS
    meta = {}
    for model_name in ["crop_recommender", "yield_predictor", "agri_advisor"]:
        path = CENTRAL_ARTIFACTS / model_name / "metadata.json"
        if path.exists():
            with open(path) as f:
                meta[model_name] = json.load(f)
        else:
            meta[model_name] = {"status": "not trained"}
    return meta
