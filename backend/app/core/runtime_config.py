"""Runtime-configurable API limits and report settings."""

import os

API_RATE_LIMIT = os.getenv("TERRAMIND_API_RATE_LIMIT", "10/minute")
ADVISOR_PREDICT_RATE_LIMIT = os.getenv("TERRAMIND_ADVISOR_PREDICT_RATE_LIMIT", "15/minute")
ADVISOR_TRAIN_RATE_LIMIT = os.getenv("TERRAMIND_ADVISOR_TRAIN_RATE_LIMIT", "2/minute")
MONITOR_PREDICT_RATE_LIMIT = os.getenv("TERRAMIND_MONITOR_PREDICT_RATE_LIMIT", "15/minute")
CHATBOT_ASK_RATE_LIMIT = os.getenv("TERRAMIND_CHATBOT_ASK_RATE_LIMIT", "10/minute")
CHATBOT_REBUILD_RATE_LIMIT = os.getenv("TERRAMIND_CHATBOT_REBUILD_RATE_LIMIT", "5/minute")
DIAGNOSIS_RATE_LIMIT = os.getenv("TERRAMIND_DIAGNOSIS_RATE_LIMIT", "10/minute")

DIAGNOSIS_TOP_K_DEFAULT = int(os.getenv("TERRAMIND_DIAGNOSIS_TOP_K_DEFAULT", "3"))
DIAGNOSIS_TOP_K_MIN = int(os.getenv("TERRAMIND_DIAGNOSIS_TOP_K_MIN", "1"))
DIAGNOSIS_TOP_K_MAX = int(os.getenv("TERRAMIND_DIAGNOSIS_TOP_K_MAX", "20"))
DIAGNOSIS_REPORT_TTL_SECONDS = int(os.getenv("TERRAMIND_DIAGNOSIS_REPORT_TTL_SECONDS", "1800"))
_diagnosis_allowed_raw = os.getenv(
    "TERRAMIND_DIAGNOSIS_ALLOWED_CONTENT_TYPES",
    "image/jpeg,image/png,image/webp,image/jpg",
)
DIAGNOSIS_ALLOWED_CONTENT_TYPES = [
    ct.strip().lower() for ct in _diagnosis_allowed_raw.split(",") if ct.strip()
]

# Kept for backward compatibility in report generation code.
REPORT_OLLAMA_NUM_PREDICT = int(os.getenv("TERRAMIND_REPORT_NUM_PREDICT", "5000"))
