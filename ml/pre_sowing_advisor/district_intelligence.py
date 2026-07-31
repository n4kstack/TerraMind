"""
District Crop Intelligence Engine — Novelty Layer (v2).

Properly parses the ICRISAT 80-column wide-format district data to compute:
    1. "This crop covers X% of your district's cultivated area"
    2. "District yield trend: ↑ improving / ↓ declining / → stable"
    3. "Competing crops in your district: Wheat, Rice, Maize"
    4. "Best season historically for this crop in this district"
    5. "10-year yield trajectory for this crop"
    6. "District irrigation infrastructure: dominated by tube wells / canals / …"
    7. "Historical irrigated-area % for this crop: X%"

ICRISAT column structure (80 cols):
    Dist Code, Year, State Code, State Name, Dist Name
    Then 25 crop groups, each with: AREA (1000 ha), PRODUCTION (1000 tons), YIELD (Kg/ha)
    Examples: RICE AREA (1000 ha), RICE PRODUCTION (1000 tons), RICE YIELD (Kg per ha)

ICRISAT Source (13 cols):
    CANALS AREA, TANKS AREA, TUBE WELLS AREA, OTHER WELLS AREA,
    TOTAL WELLS AREA, OTHER SOURCES AREA, NET AREA, GROSS AREA

ICRISAT Irrigation (25 cols):
    Per-crop IRRIGATED AREA columns (e.g. RICE IRRIGATED AREA (1000 ha))
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ml.pre_sowing_advisor.normalizers import (
    normalize_crop_name,
    normalize_district_name,
    normalize_season,
    normalize_state_name,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_ROOT / "dataset before sowing"

# ═══════════════════════════════════════════════════════════════════════
# Crop name → ICRISAT column prefix mapping
# The ICRISAT dataset uses UPPERCASE prefixes like "RICE", "WHEAT", etc.
# We map normalised crop names to these prefixes.
# ═══════════════════════════════════════════════════════════════════════

_CROP_TO_ICRISAT_PREFIX: Dict[str, str] = {
    "rice": "RICE",
    "paddy": "RICE",
    "wheat": "WHEAT",
    "sorghum": "SORGHUM",
    "jowar": "SORGHUM",
    "pearl millet": "PEARL MILLET",
    "bajra": "PEARL MILLET",
    "maize": "MAIZE",
    "corn": "MAIZE",
    "finger millet": "FINGER MILLET",
    "ragi": "FINGER MILLET",
    "barley": "BARLEY",
    "chickpea": "CHICKPEA",
    "gram": "CHICKPEA",
    "pigeonpea": "PIGEONPEA",
    "tur": "PIGEONPEA",
    "arhar": "PIGEONPEA",
    "pulses": "MINOR PULSES",
    "groundnut": "GROUNDNUT",
    "sesamum": "SESAMUM",
    "sesame": "SESAMUM",
    "rapeseed and mustard": "RAPESEED AND MUSTARD",
    "mustard": "RAPESEED AND MUSTARD",
    "safflower": "SAFFLOWER",
    "castor": "CASTOR",
    "linseed": "LINSEED",
    "sunflower": "SUNFLOWER",
    "soybean": "SOYABEAN",
    "soyabean": "SOYABEAN",
    "sugarcane": "SUGARCANE",
    "cotton": "COTTON",
    "oilseeds": "OILSEEDS",
}

# All crop prefixes in the ICRISAT data (the ones with AREA/PRODUCTION/YIELD triplets)
_ALL_ICRISAT_CROP_PREFIXES = [
    "RICE", "WHEAT", "KHARIF SORGHUM", "RABI SORGHUM", "SORGHUM",
    "PEARL MILLET", "MAIZE", "FINGER MILLET", "BARLEY",
    "CHICKPEA", "PIGEONPEA", "MINOR PULSES",
    "GROUNDNUT", "SESAMUM", "RAPESEED AND MUSTARD",
    "SAFFLOWER", "CASTOR", "LINSEED", "SUNFLOWER", "SOYABEAN",
    "OILSEEDS", "SUGARCANE", "COTTON",
]

# ═══════════════════════════════════════════════════════════════════════
# Lazy-loaded DataFrames
# ═══════════════════════════════════════════════════════════════════════

_icrisat_df: Optional[pd.DataFrame] = None
_icrisat_source_df: Optional[pd.DataFrame] = None
_icrisat_irrigation_df: Optional[pd.DataFrame] = None
_production_df: Optional[pd.DataFrame] = None


def _load_icrisat() -> pd.DataFrame:
    """Load the 80-column ICRISAT district-level dataset."""
    global _icrisat_df
    if _icrisat_df is not None:
        return _icrisat_df

    p = DATASET_DIR / "ICRISAT-District Level Data.csv"
    if not p.exists():
        logger.warning("ICRISAT district data not found: %s", p)
        _icrisat_df = pd.DataFrame()
        return _icrisat_df

    df = pd.read_csv(p)
    # Normalise state/district
    df["state"] = df["State Name"].astype(str).str.strip().str.lower().apply(normalize_state_name)
    df["district"] = df["Dist Name"].astype(str).str.strip().str.lower().apply(normalize_district_name)
    df["year"] = pd.to_numeric(df["Year"], errors="coerce")

    _icrisat_df = df
    logger.info("ICRISAT district data loaded: %d rows × %d cols", *df.shape)
    return _icrisat_df


def _load_icrisat_source() -> pd.DataFrame:
    """Load ICRISAT Source data (13 cols)."""
    global _icrisat_source_df
    if _icrisat_source_df is not None:
        return _icrisat_source_df

    p = DATASET_DIR / "ICRISAT-District Level Data Source.csv"
    if not p.exists():
        logger.warning("ICRISAT Source data not found: %s", p)
        _icrisat_source_df = pd.DataFrame()
        return _icrisat_source_df

    df = pd.read_csv(p)
    df["state"] = df["State Name"].astype(str).str.strip().str.lower().apply(normalize_state_name)
    df["district"] = df["Dist Name"].astype(str).str.strip().str.lower().apply(normalize_district_name)
    df["year"] = pd.to_numeric(df["Year"], errors="coerce")

    _icrisat_source_df = df
    logger.info("ICRISAT Source data loaded: %d rows", len(df))
    return _icrisat_source_df


def _load_icrisat_irrigation() -> pd.DataFrame:
    """Load ICRISAT Irrigation data (25 cols)."""
    global _icrisat_irrigation_df
    if _icrisat_irrigation_df is not None:
        return _icrisat_irrigation_df

    p = DATASET_DIR / "ICRISAT-District Level Data Irrigation.csv"
    if not p.exists():
        logger.warning("ICRISAT Irrigation data not found: %s", p)
        _icrisat_irrigation_df = pd.DataFrame()
        return _icrisat_irrigation_df

    df = pd.read_csv(p)
    df["state"] = df["State Name"].astype(str).str.strip().str.lower().apply(normalize_state_name)
    df["district"] = df["Dist Name"].astype(str).str.strip().str.lower().apply(normalize_district_name)
    df["year"] = pd.to_numeric(df["Year"], errors="coerce")

    _icrisat_irrigation_df = df
    logger.info("ICRISAT Irrigation data loaded: %d rows", len(df))
    return _icrisat_irrigation_df


def _load_production_data() -> pd.DataFrame:
    """Load & merge the two CSV/XLSX production datasets (fallback data source)."""
    global _production_df
    if _production_df is not None:
        return _production_df

    frames = []

    p1 = DATASET_DIR / "crop_production.csv.xlsx"
    if p1.exists():
        try:
            df1 = pd.read_excel(p1)
        except Exception:
            df1 = pd.read_csv(p1)
        df1 = df1.rename(columns={
            "State_Name": "state", "District_Name": "district",
            "label": "crop", "Season": "season",
            "Area": "area", "Production": "production", "Crop_Year": "year",
        })
        frames.append(df1)

    p2 = DATASET_DIR / "India Agriculture Crop Production.csv"
    if p2.exists():
        df2 = pd.read_csv(p2)
        rename = {}
        for o, t in [("State", "state"), ("District", "district"), ("Crop", "crop"),
                      ("Season", "season"), ("Area", "area"), ("Production", "production"),
                      ("Year", "year")]:
            if o in df2.columns:
                rename[o] = t
        df2 = df2.rename(columns=rename)
        frames.append(df2)

    if not frames:
        _production_df = pd.DataFrame()
        return _production_df

    cols = ["state", "district", "crop", "season", "area", "production", "year"]
    for f in frames:
        for c in cols:
            if c not in f.columns:
                f[c] = np.nan

    df = pd.concat([f[cols] for f in frames], ignore_index=True)
    for col in ["state", "district", "crop", "season"]:
        df[col] = df[col].astype(str).str.strip().str.lower()
    df["state"] = df["state"].apply(normalize_state_name)
    df["district"] = df["district"].apply(normalize_district_name)
    df["crop"] = df["crop"].apply(normalize_crop_name)
    df["season"] = df["season"].apply(normalize_season)
    df["area"] = pd.to_numeric(df["area"], errors="coerce")
    df["production"] = pd.to_numeric(df["production"], errors="coerce")
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["area", "production"]).reset_index(drop=True)
    df["yield"] = np.where(df["area"] > 0, df["production"] / df["area"], 0)

    _production_df = df
    logger.info("Production data loaded: %d rows", len(df))
    return _production_df


# ═══════════════════════════════════════════════════════════════════════
# Helper: resolve crop → ICRISAT column prefix
# ═══════════════════════════════════════════════════════════════════════

def _resolve_icrisat_prefix(crop: str) -> Optional[str]:
    """Map a normalised crop name to its ICRISAT column prefix."""
    crop_lower = crop.lower().strip()
    # Direct map
    if crop_lower in _CROP_TO_ICRISAT_PREFIX:
        return _CROP_TO_ICRISAT_PREFIX[crop_lower]
    # Fuzzy: check if crop is a substring of any prefix
    for prefix in _ALL_ICRISAT_CROP_PREFIXES:
        if crop_lower in prefix.lower() or prefix.lower() in crop_lower:
            return prefix
    return None


def _get_col(prefix: str, suffix: str, df_columns: list) -> Optional[str]:
    """Find exact ICRISAT column from prefix + suffix."""
    # Try exact match first
    patterns = [
        f"{prefix} {suffix}",
    ]
    for pat in patterns:
        for col in df_columns:
            if col.strip().upper() == pat.upper():
                return col
    return None


# ═══════════════════════════════════════════════════════════════════════
# Intelligence Computations (ICRISAT-first, production-data fallback)
# ═══════════════════════════════════════════════════════════════════════

def _crop_area_share_icrisat(
    state: str, district: str, crop: str,
) -> Tuple[Optional[float], str]:
    """'This crop covers X% of your district's cultivated area'
    
    Uses the ICRISAT 80-col data: sums the crop's AREA column across all years
    relative to total area of all crops in the district.
    """
    df = _load_icrisat()
    if df.empty:
        return None, "No ICRISAT data available."

    prefix = _resolve_icrisat_prefix(crop)
    if prefix is None:
        return None, f"Crop '{crop}' not found in ICRISAT dataset."

    area_col = _get_col(prefix, "AREA (1000 ha)", list(df.columns))
    if area_col is None:
        return None, f"Area column for '{prefix}' not found."

    dist_data = df[(df["state"] == state) & (df["district"] == district)]
    if dist_data.empty:
        return None, f"No data for district '{district}' in '{state}'."

    # Use latest available year for most relevant snapshot
    latest_year = dist_data["year"].max()
    recent = dist_data[dist_data["year"] >= latest_year - 2]  # last 3 years avg

    crop_area = pd.to_numeric(recent[area_col], errors="coerce").mean()
    if pd.isna(crop_area) or crop_area <= 0:
        return 0.0, f"Negligible {crop} cultivation in this district."

    # Sum all crop areas for total
    all_area_cols = [c for c in df.columns if "AREA (1000 ha)" in c
                     and "IRRIGATED" not in c.upper()
                     and "FRUITS AND VEGETABLES" not in c.upper()
                     and "FODDER" not in c.upper()
                     and "OILSEEDS" not in c.upper()]  # avoid double-counting aggregates

    total_area = 0.0
    for ac in all_area_cols:
        vals = pd.to_numeric(recent[ac], errors="coerce")
        total_area += vals.mean() if not vals.isna().all() else 0

    if total_area <= 0:
        return None, "Could not compute total district crop area."

    pct = round(crop_area / total_area * 100, 2)
    note = f"This crop covers {pct}% of your district's cultivated area (avg {latest_year-2}-{latest_year})."
    return pct, note


def _yield_trend_icrisat(
    state: str, district: str, crop: str,
) -> Tuple[str, str]:
    """'District yield trend: ↑ improving / ↓ declining / → stable'
    
    Uses ICRISAT YIELD column over time and fits a linear trend.
    """
    df = _load_icrisat()
    if df.empty:
        return "unknown", "No ICRISAT data."

    prefix = _resolve_icrisat_prefix(crop)
    if prefix is None:
        return "unknown", f"Crop '{crop}' not in ICRISAT."

    yield_col = _get_col(prefix, "YIELD (Kg per ha)", list(df.columns))
    if yield_col is None:
        return "unknown", f"Yield column for '{prefix}' not found."

    dist_data = df[(df["state"] == state) & (df["district"] == district)].copy()
    if dist_data.empty:
        return "unknown", "No district data."

    dist_data["_yield"] = pd.to_numeric(dist_data[yield_col], errors="coerce")
    series = dist_data.dropna(subset=["_yield", "year"]).sort_values("year")
    series = series[series["_yield"] > 0]

    if len(series) < 3:
        return "insufficient data", "Fewer than 3 data points."

    yearly = series.groupby("year")["_yield"].mean().sort_index()
    x = np.arange(len(yearly))
    y = yearly.values
    slope = np.polyfit(x, y, 1)[0]
    mean_y = y.mean()

    if mean_y == 0:
        return "stable", "Yield is stable."

    rel_slope = slope / mean_y
    if rel_slope > 0.015:
        direction = "improving"
        emoji = "↑"
    elif rel_slope < -0.015:
        direction = "declining"
        emoji = "↓"
    else:
        direction = "stable"
        emoji = "→"

    start_y, end_y = y[0], y[-1]
    change = ((end_y - start_y) / start_y * 100) if start_y > 0 else 0

    note = (
        f"District yield trend: {emoji} {direction}. "
        f"Yield moved from {start_y:.0f} to {end_y:.0f} Kg/ha "
        f"({change:+.1f}%) over {yearly.index[0]}-{yearly.index[-1]}."
    )
    return direction, note


def _top_competing_crops_icrisat(
    state: str, district: str, crop: str, top_n: int = 5,
) -> Tuple[List[str], str]:
    """'Competing crops in your district: Wheat, Rice, Maize'
    
    Ranks all crops by their latest area in the district.
    """
    df = _load_icrisat()
    if df.empty:
        return [], "No data."

    dist_data = df[(df["state"] == state) & (df["district"] == district)]
    if dist_data.empty:
        return [], f"No data for '{district}'."

    latest_year = dist_data["year"].max()
    recent = dist_data[dist_data["year"] == latest_year]

    # Extract all crop areas
    crop_areas: Dict[str, float] = {}
    my_prefix = _resolve_icrisat_prefix(crop)

    for prefix in _ALL_ICRISAT_CROP_PREFIXES:
        # Skip aggregate categories and seasonal splits
        if prefix in ("OILSEEDS", "KHARIF SORGHUM", "RABI SORGHUM"):
            continue

        area_col = _get_col(prefix, "AREA (1000 ha)", list(df.columns))
        if area_col is None:
            continue

        val = pd.to_numeric(recent[area_col], errors="coerce").sum()
        if val > 0:
            crop_areas[prefix.title()] = val

    # Sort by area, exclude the recommended crop
    sorted_crops = sorted(crop_areas.items(), key=lambda x: x[1], reverse=True)
    excluded = (my_prefix or "").title()
    competitors = [name for name, _ in sorted_crops if name != excluded][:top_n]

    note = f"Competing crops in your district: {', '.join(competitors)}." if competitors else "No competitor data."
    return competitors, note


def _best_historical_season(
    state: str, district: str, crop: str,
) -> Tuple[str, str]:
    """'Best season historically for this crop in this district'
    
    ICRISAT doesn't have season columns, so we use the production datasets.
    Some crops have KHARIF/RABI prefix variants in ICRISAT — use those too.
    """
    # First check ICRISAT for kharif/rabi variants
    df = _load_icrisat()
    prefix = _resolve_icrisat_prefix(crop)

    if prefix and not df.empty:
        dist_data = df[(df["state"] == state) & (df["district"] == district)]
        if not dist_data.empty:
            # Check for seasonal variants (e.g. KHARIF SORGHUM vs RABI SORGHUM)
            kharif_col = _get_col(f"KHARIF {prefix}", "YIELD (Kg per ha)", list(df.columns))
            rabi_col = _get_col(f"RABI {prefix}", "YIELD (Kg per ha)", list(df.columns))

            if kharif_col and rabi_col:
                k_yield = pd.to_numeric(dist_data[kharif_col], errors="coerce").mean()
                r_yield = pd.to_numeric(dist_data[rabi_col], errors="coerce").mean()
                if not pd.isna(k_yield) and not pd.isna(r_yield):
                    if k_yield > r_yield:
                        return "kharif", f"Best season historically: Kharif (avg yield {k_yield:.0f} vs Rabi {r_yield:.0f} Kg/ha)."
                    else:
                        return "rabi", f"Best season historically: Rabi (avg yield {r_yield:.0f} vs Kharif {k_yield:.0f} Kg/ha)."

    # Fallback: use production datasets which have season
    prod_df = _load_production_data()
    norm_crop = normalize_crop_name(crop)
    data = prod_df[
        (prod_df["state"] == state) & (prod_df["district"] == district) & (prod_df["crop"] == norm_crop)
    ]
    if data.empty:
        data = prod_df[(prod_df["state"] == state) & (prod_df["crop"] == norm_crop)]
    if data.empty:
        return "unknown", "No seasonal data available."

    season_yields = data.groupby("season")["yield"].mean()
    if season_yields.empty:
        return "unknown", "No seasonal info."

    best = str(season_yields.idxmax())
    best_val = season_yields.max()
    note = f"Best season historically for this crop: {best.title()} (avg yield {best_val:.2f})."
    return best, note


def _ten_year_trajectory_icrisat(
    state: str, district: str, crop: str,
) -> str:
    """'Your recommended crop's 10-year yield trajectory'
    
    Reads ICRISAT YIELD column year-by-year and summarises the last 10 years.
    """
    df = _load_icrisat()
    if df.empty:
        return "No ICRISAT data available for trajectory analysis."

    prefix = _resolve_icrisat_prefix(crop)
    if prefix is None:
        # Fallback to production data
        return _ten_year_trajectory_fallback(state, district, crop)

    yield_col = _get_col(prefix, "YIELD (Kg per ha)", list(df.columns))
    if yield_col is None:
        return _ten_year_trajectory_fallback(state, district, crop)

    dist_data = df[(df["state"] == state) & (df["district"] == district)].copy()
    if dist_data.empty:
        return _ten_year_trajectory_fallback(state, district, crop)

    dist_data["_yield"] = pd.to_numeric(dist_data[yield_col], errors="coerce")
    yearly = dist_data.dropna(subset=["_yield"]).groupby("year")["_yield"].mean().sort_index()
    yearly = yearly[yearly > 0]

    if len(yearly) < 2:
        return f"Only {len(yearly)} year(s) of ICRISAT data for {crop} in this district."

    # Last 10 years
    if len(yearly) > 10:
        yearly = yearly.tail(10)

    years = yearly.index.tolist()
    yields = yearly.values

    start_val = yields[0]
    end_val = yields[-1]
    avg_val = np.mean(yields)
    max_val = np.max(yields)
    min_val = np.min(yields)
    change_pct = ((end_val - start_val) / start_val * 100) if start_val > 0 else 0

    direction = "increased" if change_pct > 5 else ("decreased" if change_pct < -5 else "remained stable")

    return (
        f"10-year yield trajectory ({years[0]}–{years[-1]}): "
        f"{prefix.title()} yield {direction} by {abs(change_pct):.1f}% "
        f"(from {start_val:.0f} to {end_val:.0f} Kg/ha). "
        f"Average: {avg_val:.0f} Kg/ha, "
        f"Range: [{min_val:.0f}, {max_val:.0f}] Kg/ha."
    )


def _ten_year_trajectory_fallback(state: str, district: str, crop: str) -> str:
    """Fallback trajectory using production datasets."""
    prod_df = _load_production_data()
    norm_crop = normalize_crop_name(crop)
    data = prod_df[
        (prod_df["state"] == state) & (prod_df["district"] == district) & (prod_df["crop"] == norm_crop)
    ].dropna(subset=["year", "yield"])

    if data.empty:
        data = prod_df[(prod_df["state"] == state) & (prod_df["crop"] == norm_crop)].dropna(subset=["year", "yield"])
        if data.empty:
            return "No historical data available for trajectory analysis."

    yearly = data.groupby("year")["yield"].mean().sort_index()
    if len(yearly) > 10:
        yearly = yearly.tail(10)

    if len(yearly) < 2:
        return f"Only {len(yearly)} year(s) of data."

    years = yearly.index.tolist()
    yields = yearly.values
    start_val, end_val = yields[0], yields[-1]
    change = ((end_val - start_val) / start_val * 100) if start_val > 0 else 0
    direction = "increased" if change > 5 else ("decreased" if change < -5 else "remained stable")

    return (
        f"Yield trajectory ({int(years[0])}–{int(years[-1])}): "
        f"{direction} by {abs(change):.1f}% "
        f"({start_val:.2f} → {end_val:.2f}). "
        f"Average: {np.mean(yields):.2f}, Range: [{np.min(yields):.2f}, {np.max(yields):.2f}]."
    )


def _irrigation_infrastructure_summary(
    state: str, district: str,
) -> Tuple[str, Dict[str, float]]:
    """'District irrigation infrastructure: dominated by canals / tube wells / …'
    
    Uses ICRISAT Source data (13 cols) with explicit source columns.
    """
    df = _load_icrisat_source()
    if df.empty:
        return "No irrigation infrastructure data available.", {}

    dist_data = df[(df["state"] == state) & (df["district"] == district)]
    if dist_data.empty:
        return f"No irrigation infrastructure data for '{district}'.", {}

    # Use latest year
    latest = dist_data[dist_data["year"] == dist_data["year"].max()]

    # Source columns are exactly known
    source_map = {
        "Canals": "CANALS AREA (1000 ha)",
        "Tanks": "TANKS AREA (1000 ha)",
        "Tube Wells": "TUBE WELLS AREA (1000 ha)",
        "Other Wells": "OTHER WELLS AREA (1000 ha)",
        "Other Sources": "OTHER SOURCES AREA (1000 ha)",
    }

    sources: Dict[str, float] = {}
    for name, col in source_map.items():
        if col in latest.columns:
            val = pd.to_numeric(latest[col], errors="coerce").sum()
            if val > 0:
                sources[name] = round(float(val), 2)

    if not sources:
        return "Irrigation infrastructure data could not be parsed.", {}

    total = sum(sources.values())
    if total <= 0:
        return "No measurable irrigation infrastructure data.", {}

    # Build percentage breakdown
    pct_map = {name: round(val / total * 100, 1) for name, val in sources.items()}
    sorted_sources = sorted(pct_map.items(), key=lambda x: x[1], reverse=True)
    dominant = sorted_sources[0][0]
    parts = [f"{name}: {pct}%" for name, pct in sorted_sources if pct > 0]

    summary = f"Dominated by {dominant}. Breakdown: {', '.join(parts)}."
    return summary, pct_map


def _crop_irrigated_area_pct(
    state: str, district: str, crop: str,
) -> Tuple[Optional[float], str]:
    """'Historical irrigated-area % for this crop: X%'
    
    Compares ICRISAT Irrigation 'CROP IRRIGATED AREA' to main ICRISAT 'CROP AREA'.
    """
    irr_df = _load_icrisat_irrigation()
    main_df = _load_icrisat()

    if irr_df.empty or main_df.empty:
        return None, "No irrigation percentage data."

    prefix = _resolve_icrisat_prefix(crop)
    if prefix is None:
        return None, f"Crop '{crop}' not in ICRISAT irrigation dataset."

    # Find irrigated area column
    irr_col = None
    for col in irr_df.columns:
        if col.upper().startswith(prefix) and "IRRIGATED AREA" in col.upper():
            irr_col = col
            break

    # Find total area column
    area_col = _get_col(prefix, "AREA (1000 ha)", list(main_df.columns))

    if irr_col is None or area_col is None:
        return None, f"Irrigated area data not found for '{prefix}'."

    # Get district data, latest year
    irr_dist = irr_df[(irr_df["state"] == state) & (irr_df["district"] == district)]
    main_dist = main_df[(main_df["state"] == state) & (main_df["district"] == district)]

    if irr_dist.empty or main_dist.empty:
        return None, "No irrigated area data for this district."

    # Average over recent years
    latest_yr = min(irr_dist["year"].max(), main_dist["year"].max())
    irr_recent = irr_dist[irr_dist["year"] >= latest_yr - 4]
    main_recent = main_dist[main_dist["year"] >= latest_yr - 4]

    irr_area = pd.to_numeric(irr_recent[irr_col], errors="coerce").mean()
    total_area = pd.to_numeric(main_recent[area_col], errors="coerce").mean()

    if pd.isna(irr_area) or pd.isna(total_area) or total_area <= 0:
        return None, "Insufficient data to compute irrigated percentage."

    pct = round(irr_area / total_area * 100, 1)
    pct = min(pct, 100.0)  # Cap at 100

    note = f"Historical irrigated-area for {prefix.title()}: {pct}% of total crop area in this district."
    return pct, note


# ═══════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════

def get_district_intelligence(
    state: str,
    district: str,
    crop: str,
    season: str = "",
) -> Dict[str, Any]:
    """Generate comprehensive district intelligence for the recommended crop.

    Produces human-readable insights using ICRISAT 80-column district data:
        • "This crop covers X% of your district's area"
        • "District yield trend: ↑ improving / ↓ declining"
        • "Competing crops in your district: Wheat, Rice"
        • "Best season historically for this crop here"
        • "Your recommended crop's 10-year yield trajectory"
        • "District irrigation infrastructure: dominated by …"
        • "Historical irrigated-area % for this crop: X%"
    """
    try:
        state = normalize_state_name(state)
        district = normalize_district_name(district)
        crop_norm = normalize_crop_name(crop)

        notes: List[str] = []
        insights: List[str] = []

        # 1. Crop area share
        share_pct, share_note = _crop_area_share_icrisat(state, district, crop_norm)
        if share_pct is not None:
            insights.append(share_note)
        else:
            notes.append(share_note)

        # 2. Yield trend
        trend, trend_note = _yield_trend_icrisat(state, district, crop_norm)
        insights.append(trend_note)

        # 3. Competing crops
        competitors, comp_note = _top_competing_crops_icrisat(state, district, crop_norm)
        if competitors:
            insights.append(comp_note)
        else:
            notes.append(comp_note)

        # 4. Best historical season
        best_season, season_note = _best_historical_season(state, district, crop_norm)
        insights.append(season_note)

        # 5. 10-year trajectory
        trajectory = _ten_year_trajectory_icrisat(state, district, crop_norm)
        insights.append(trajectory)

        # 6. Irrigation infrastructure
        infra_summary, infra_breakdown = _irrigation_infrastructure_summary(state, district)
        insights.append(f"Irrigation infrastructure: {infra_summary}")

        # 7. Crop irrigated area %
        irr_pct, irr_note = _crop_irrigated_area_pct(state, district, crop_norm)
        if irr_pct is not None:
            insights.append(irr_note)
        else:
            notes.append(irr_note)

        result: Dict[str, Any] = {
            "district_crop_share_percent": share_pct,
            "yield_trend": trend,
            "top_competing_crops": competitors,
            "best_historical_season": best_season,
            "ten_year_trajectory_summary": trajectory,
            "irrigation_infrastructure_summary": infra_summary,
            "irrigation_infrastructure_breakdown": infra_breakdown,
            "crop_irrigated_area_percent": irr_pct,
            "insights": insights,
            "notes": notes,
        }

        logger.info("District intelligence generated for %s/%s/%s: %d insights, %d notes",
                    state, district, crop_norm, len(insights), len(notes))
        return result
    except Exception as exc:
        logger.warning("District intelligence fallback due to runtime error: %s", exc)
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
