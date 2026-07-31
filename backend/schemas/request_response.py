"""
TerraMind - Pydantic request/response schemas for the prediction API.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """Input schema for POST /predict."""
    N: float = Field(..., description="Nitrogen content in soil")
    P: float = Field(..., description="Phosphorus content in soil")
    K: float = Field(..., description="Potassium content in soil")
    ph: float = Field(..., description="Soil pH value")
    temperature: float = Field(..., description="Temperature in °C")
    humidity: float = Field(..., description="Relative humidity %")
    rainfall: float = Field(..., description="Rainfall in mm")
    soil_type: str = Field(..., description="Soil type (e.g., loamy, clay)")
    state: str = Field(..., description="State name")
    district: str = Field(..., description="District name")
    season: str = Field(..., description="Season (kharif, rabi, etc.)")
    area: Optional[float] = Field(None, description="Cultivated area in hectares (optional)")
    mode: str = Field("central", description="Execution mode: central | edge | local_only")

    model_config = {"json_schema_extra": {
        "examples": [{
            "N": 90, "P": 42, "K": 43, "ph": 6.5,
            "temperature": 25.0, "humidity": 80.0, "rainfall": 200.0,
            "soil_type": "loamy", "state": "Punjab", "district": "Ludhiana",
            "season": "kharif", "area": 2.5, "mode": "edge",
        }]
    }}


class CropEntry(BaseModel):
    crop: str
    base_confidence: float
    local_adjustment: float
    final_confidence: float


class CropRecommenderOutput(BaseModel):
    top_3: list[CropEntry]
    selected_crop: str
    adaptation_factors: list[str] = []


class ConfidenceBand(BaseModel):
    lower: Optional[float]
    upper: Optional[float]


class YieldPredictorOutput(BaseModel):
    expected_yield: Optional[float]
    unit: str = "t/ha"
    confidence_band: ConfidenceBand
    explanation: str = ""


class AgriConditionOutput(BaseModel):
    sunlight_hours: Optional[float]
    irrigation_type: str
    irrigation_need: str
    explanation: str = ""
    district_prior_used: bool = False
    district_irrigation_summary: str = ""
    crop_irrigated_pct: Optional[float] = None


class DistrictIntelligenceOutput(BaseModel):
    district_crop_share_percent: Optional[float]
    yield_trend: Optional[str]
    top_competing_crops: list[str] = []
    best_historical_season: Optional[str]
    ten_year_trajectory_summary: Optional[str]
    ten_year_trajectory_data: Optional[dict] = None
    irrigation_infrastructure_summary: Optional[str]
    irrigation_infrastructure_data: Optional[dict] = None
    crop_irrigated_area_percent: Optional[float]
    notes: list[str] = []


class SyncStatus(BaseModel):
    edge_version: str = "n/a"
    central_version: str = "n/a"
    last_sync: Optional[str] = None
    stale: bool = False


class PredictResponse(BaseModel):
    input_summary: dict
    execution_mode: str
    model_version: str
    adaptation_applied: bool
    sync_status: SyncStatus
    crop_recommender: CropRecommenderOutput
    yield_predictor: YieldPredictorOutput
    agri_condition_advisor: AgriConditionOutput
    district_intelligence: DistrictIntelligenceOutput
    system_notes: list[str] = []
    latency_ms: float = 0.0
