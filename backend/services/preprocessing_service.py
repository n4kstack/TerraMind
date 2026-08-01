"""
TerraMind - Preprocessing Service

Transforms cleaned user inputs into model-ready feature vectors
for each of the three models.
"""
from __future__ import annotations

import numpy as np

from backend.core.config import CROP_REC_FEATURES
from backend.core.logging_config import log


class PreprocessingService:
    """Converts normalised user input dict -> feature arrays for each model."""

    @staticmethod
    def for_crop_recommender(inputs: dict, scaler) -> np.ndarray:
        """Build feature vector for Model 1."""
        features = [float(inputs.get(f, 0)) for f in CROP_REC_FEATURES]
        X = np.array(features).reshape(1, -1)
        return scaler.transform(X)

    @staticmethod
    def for_yield_predictor(
        inputs: dict,
        crop: str,
        scaler,
        le_crop, le_state, le_district, le_season,
        metadata: dict,
        crop_stats_cache: dict | None = None,
    ) -> np.ndarray:
        """
        Build feature vector for Model 2.
        Uses label encoders, falling back to the most common class
        when a value is unseen.

        Cache enrichment happens here, on the raw vector, *before* scaling.
        It used to run afterwards, against the already-standardised array, so
        a district mean of 1.608 t/ha was written where a z-score belonged.
        With yield_lag1 at mean=19.24 scale=275.0, the model read that 1.608 as
        19.24 + 1.608*275.0 = 461 t/ha and Durg rice came back as 495 t/ha
        against a historical mean of 1.6.
        """
        def safe_encode(le, val: str) -> int:
            val = str(val).lower().strip()
            if val in le.classes_:
                return int(le.transform([val])[0])
            log.warning("Unseen label '%s' for encoder - using fallback 0", val)
            return 0

        crop_enc     = safe_encode(le_crop, crop)
        state_enc    = safe_encode(le_state, inputs.get("state", ""))
        district_enc = safe_encode(le_district, inputs.get("district", ""))
        season_enc   = safe_encode(le_season, inputs.get("season", ""))
        area_log     = float(np.log1p(max(float(inputs.get("area") or 1.0), 0)))

        # Lag features start at 0 and are overwritten from the district cache
        # below when we have history for this state/district/crop.
        features = [
            crop_enc, state_enc, district_enc, season_enc,
            area_log,
            0.0,  # yield_lag1
            0.0,  # yield_lag2
            0.0,  # yield_lag3
            0.0,  # yield_rolling3_mean
            0.0,  # yield_rolling5_mean
            0.0,  # area_lag1
            0.0,  # yield_trend_slope
        ]
        # Remove duplicates from feature list based on metadata
        expected_n = len(metadata.get("features", features))
        features = features[:expected_n]

        X = np.array(features, dtype=float).reshape(1, -1)

        if crop_stats_cache:
            X = PreprocessingService.enrich_yield_features_from_cache(
                X,
                inputs.get("state", ""), inputs.get("district", ""), crop,
                crop_stats_cache,
                area_fallback=float(getattr(scaler, "mean_", [0] * 11)[10]),
            )

        return scaler.transform(X)

    @staticmethod
    def for_agri_advisor(
        inputs: dict,
        crop: str,
        scaler,
        le_crop, le_soil_type, le_season,
    ) -> np.ndarray:
        """Build feature vector for Model 3."""
        def safe_encode(le, val: str) -> int:
            val = str(val).lower().strip()
            if val in le.classes_:
                return int(le.transform([val])[0])
            return 0

        features = [
            float(inputs.get("ph", 6.5)),
            float(inputs.get("temperature", 25.0)),
            float(inputs.get("humidity", 60.0)),
            float(inputs.get("rainfall", 100.0)),
            safe_encode(le_crop, crop),
            safe_encode(le_soil_type, inputs.get("soil_type", "")),
            safe_encode(le_season, inputs.get("season", "")),
        ]
        X = np.array(features).reshape(1, -1)
        return scaler.transform(X)

    @staticmethod
    def enrich_yield_features_from_cache(
        X: np.ndarray,
        state: str,
        district: str,
        crop: str,
        crop_stats_cache: dict,
        area_fallback: float = 0.0,
    ) -> np.ndarray:
        """
        Fill lag/rolling features from cached district stats.
        Modifies positions 5-10 in the feature vector.

        Operates on the RAW feature vector. Call before scaler.transform(),
        never after: these are t/ha and hectare values, not z-scores.
        """
        key = f"{state}|{district}|{crop}"
        stats = crop_stats_cache.get(key, {})

        if stats:
            mean_yield = float(stats.get("mean_yield", 0) or 0)
            X[0, 5]  = mean_yield          # yield_lag1 proxy
            X[0, 6]  = mean_yield * 0.95   # yield_lag2 proxy
            X[0, 7]  = mean_yield * 0.90   # yield_lag3 proxy
            X[0, 8]  = mean_yield          # rolling3_mean proxy
            X[0, 9]  = mean_yield          # rolling5_mean proxy
            # The cache carries no area series, so impute area_lag1 with the
            # training mean (z-score 0, i.e. no contribution) rather than the
            # literal 0 hectares this used to send.
            X[0, 10] = float(stats.get("mean_area") or area_fallback)
        return X
