"""
TerraMind Pre-Sowing Advisor - Central Configuration

All paths, constants, and tunables for the project.
Uses relative paths from project root.
"""
import os
from pathlib import Path

# ── Project root (two levels up from this file: backend/core/config.py) ──────
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ── Dataset directory ────────────────────────────────────────────────────────
DATASET_DIR = PROJECT_ROOT / "dataset before sowing"

# Individual dataset paths
CROP_DATASET       = DATASET_DIR / "crop_dataset_rebuilt.csv"
IRRIGATION_DATASET = DATASET_DIR / "irrigation_prediction.csv"
INDIA_AGRI_CSV     = DATASET_DIR / "India Agriculture Crop Production.csv"
CROP_PROD_XLSX     = DATASET_DIR / "crop_production.csv.xlsx"
ICRISAT_MAIN       = DATASET_DIR / "ICRISAT-District Level Data.csv"
ICRISAT_SOURCE     = DATASET_DIR / "ICRISAT-District Level Data Source.csv"
ICRISAT_IRRIGATION = DATASET_DIR / "ICRISAT-District Level Data Irrigation.csv"
MERGE_XLS          = DATASET_DIR / "main merge (droped _merge==2) (560 dist 1990-2015).xls"

# ── Artifact directories ────────────────────────────────────────────────────
ARTIFACTS_DIR     = PROJECT_ROOT / "backend" / "artifacts"
CENTRAL_ARTIFACTS = ARTIFACTS_DIR / "central"
EDGE_ARTIFACTS    = ARTIFACTS_DIR / "edge"
LOCAL_ARTIFACTS   = ARTIFACTS_DIR / "local"

# Ensure artifact dirs exist
for d in [CENTRAL_ARTIFACTS, EDGE_ARTIFACTS, LOCAL_ARTIFACTS]:
    d.mkdir(parents=True, exist_ok=True)

# ── Model hyper-parameters ──────────────────────────────────────────────────
# Model 1 - Crop Recommender
CROP_REC_RF_PARAMS = {
    "n_estimators": 300,
    "max_depth": 20,
    "min_samples_split": 5,
    "min_samples_leaf": 2,
    "random_state": 42,
    "n_jobs": -1,
}
CROP_REC_GB_PARAMS = {
    "n_estimators": 250,
    "max_depth": 8,
    "learning_rate": 0.1,
    "subsample": 0.8,
    "random_state": 42,
}

# Model 2 - Yield Predictor (GradientBoostingRegressor fallback)
YIELD_GB_PARAMS = {
    "n_estimators": 300,
    "max_depth": 8,
    "learning_rate": 0.08,
    "subsample": 0.85,
    "random_state": 42,
}

# Model 3 - Agri-Condition Advisor
AGRI_RF_PARAMS = {
    "n_estimators": 200,
    "max_depth": 16,
    "min_samples_split": 4,
    "random_state": 42,
    "n_jobs": -1,
}

# ── Edge compression settings ──────────────────────────────────────────────
EDGE_RF_N_ESTIMATORS = 80          # reduced tree count for edge
EDGE_MAX_DEPTH       = 12          # shallower trees

# ── Local adaptation settings ──────────────────────────────────────────────
LOCAL_ADAPT_MAX_SHIFT  = 0.15      # max probability shift per crop
LOCAL_ADAPT_DECAY      = 0.6       # adaptation strength decay factor
ADAPTATION_MIN_SAMPLES = 30        # minimum samples to trust local prior

# ── Agro-climatic zone mapping (configurable) ──────────────────────────────
# Fallback: state-level grouping. Can be enriched with external zone file.
AGRO_CLIMATIC_ZONE_FILE = ARTIFACTS_DIR / "agro_climatic_zones.json"

# ── Training split settings ────────────────────────────────────────────────
TEST_SIZE  = 0.15
VAL_SIZE   = 0.15
RANDOM_SEED = 42

# ── API settings ────────────────────────────────────────────────────────────
API_HOST = os.getenv("TERRAMIND_HOST", "0.0.0.0")
API_PORT = int(os.getenv("TERRAMIND_PORT", "8000"))
MODEL_VERSION = "1.0.0"

# ── Crop label features for Model 1 ────────────────────────────────────────
CROP_REC_FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]

# ── Agri-Advisor features ──────────────────────────────────────────────────
AGRI_INPUT_FEATURES  = ["crop", "ph", "temperature", "humidity", "rainfall", "soil_type", "season"]
AGRI_REG_TARGET      = "sunlight_hours"
AGRI_CLF_TARGETS     = ["irrigation_type", "irrigation_need"]
