"""
TerraMind Chatbot - Configuration
==================================
All chatbot / RAG settings live here so they can be changed in one place.
Values are read from environment variables when available, falling back to
sensible defaults that work on modest local hardware (i7-11 / MX330 / 32 GB).
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency safety
    load_dotenv = None

# ── Paths ────────────────────────────────────────────────────────────────────
# Project root is two levels above this file: backend/app/core/config.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

if load_dotenv is not None:
    # Load root .env once so os.getenv values are available in all modules.
    load_dotenv(_PROJECT_ROOT / ".env", override=False)

PDF_FOLDER_PATH: str = os.getenv(
    "TERRAMIND_PDF_FOLDER",
    str(_PROJECT_ROOT / "chatbot"),
)

VECTOR_STORE_DIR: str = os.getenv(
    "TERRAMIND_VECTOR_STORE_DIR",
    str(Path(__file__).resolve().parents[1] / "chatbot" / "storage"),
)

# ── Embedding model ─────────────────────────────────────────────────────────
# all-MiniLM-L6-v2: 80 MB, 384-dim, top-tier for its size on MTEB benchmarks.
# Runs entirely on CPU - no GPU required.
EMBEDDING_MODEL_NAME: str = os.getenv(
    "TERRAMIND_EMBEDDING_MODEL",
    "all-MiniLM-L6-v2",
)

# ── OpenRouter / LLM ────────────────────────────────────────────────────────
# Keep API keys server-side only; never expose to frontend code.
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL_NAME: str = os.getenv(
    "OPENROUTER_MODEL_NAME",
    os.getenv("GEMINI_MODEL_NAME", os.getenv("OLLAMA_MODEL_NAME", "nvidia/nemotron-3-ultra-550b-a55b:free")),
)
OPENROUTER_TEMPERATURE: float = float(
    os.getenv("OPENROUTER_TEMPERATURE", os.getenv("GEMINI_TEMPERATURE", os.getenv("OLLAMA_TEMPERATURE", "0.3")))
)
OPENROUTER_TIMEOUT_SECONDS: int = int(
    os.getenv("OPENROUTER_TIMEOUT", os.getenv("GEMINI_TIMEOUT", os.getenv("OLLAMA_TIMEOUT", "240")))
)
OPENROUTER_REASONING_EFFORT: str = os.getenv("OPENROUTER_REASONING_EFFORT", "low").strip().lower()

# Compatibility aliases used by existing imports and schema fields.
GEMINI_API_KEY: str = OPENROUTER_API_KEY
GEMINI_MODEL_NAME: str = OPENROUTER_MODEL_NAME
GEMINI_TEMPERATURE: float = OPENROUTER_TEMPERATURE
GEMINI_TIMEOUT_SECONDS: int = OPENROUTER_TIMEOUT_SECONDS

# Legacy compatibility exports (older modules still import OLLAMA_*).
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "")
OLLAMA_MODEL_NAME: str = OPENROUTER_MODEL_NAME

# ── Chunking ─────────────────────────────────────────────────────────────────
# 500-char chunks with 50-char overlap keeps retrieval precise while giving
# the small LLM enough context per chunk without blowing up the prompt.
CHUNK_SIZE: int = int(os.getenv("TERRAMIND_CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("TERRAMIND_CHUNK_OVERLAP", "50"))

# ── Retrieval ────────────────────────────────────────────────────────────────
RETRIEVAL_TOP_K: int = int(os.getenv("TERRAMIND_TOP_K", "5"))
MAX_CONTEXT_CHUNKS: int = int(os.getenv("TERRAMIND_MAX_CONTEXT_CHUNKS", "5"))

# Cosine-similarity floor.  Chunks scoring below this are considered
# irrelevant and the chatbot will refuse to answer.
SIMILARITY_THRESHOLD: float = float(os.getenv("TERRAMIND_SIM_THRESHOLD", "0.35"))

# ── LLM generation parameters ───────────────────────────────────────────────
OLLAMA_TEMPERATURE: float = OPENROUTER_TEMPERATURE
OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
OLLAMA_TIMEOUT_SECONDS: int = OPENROUTER_TIMEOUT_SECONDS
