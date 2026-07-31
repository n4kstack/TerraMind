"""
TerraMind - Input normaliser / preprocessor for inference requests.

Ensures user inputs are cleaned and validated before hitting models.
"""
from __future__ import annotations
from backend.utils.naming_maps import (
    normalize_state, normalize_district, normalize_crop, normalize_season,
)


def normalise_input(data: dict) -> dict:
    """
    Clean and normalise raw user input dictionary.

    Expected keys:
        N, P, K, ph, temperature, humidity, rainfall,
        soil_type, state, district, season, area (optional), mode
    """
    cleaned = {}

    # Numeric fields - cast safely
    for key in ("N", "P", "K", "ph", "temperature", "humidity", "rainfall"):
        val = data.get(key)
        cleaned[key] = float(val) if val is not None else 0.0

    # Area - optional
    area = data.get("area")
    cleaned["area"] = float(area) if area is not None else None

    # Text fields
    cleaned["soil_type"] = str(data.get("soil_type", "")).strip().lower()
    cleaned["state"]     = normalize_state(data.get("state", ""))
    cleaned["district"]  = normalize_district(data.get("district", ""))
    cleaned["season"]    = normalize_season(data.get("season", ""))

    # Execution mode
    mode = str(data.get("mode", "central")).lower()
    if mode not in ("central", "edge", "local_only"):
        mode = "central"
    cleaned["mode"] = mode

    return cleaned
