"""
TerraMind - FastAPI Application Entry Point

Wires all routers, configures CORS, and provides health endpoint.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root and backend root are on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

for path in [PROJECT_ROOT, BACKEND_ROOT]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes_predict   import router as predict_router
from backend.api.routes_train     import router as train_router
from backend.api.routes_sync      import router as sync_router
from backend.api.routes_benchmark import router as benchmark_router

# v1 Integration Routers
from backend.app.api.v1.advisor   import router as advisor_v1
from backend.app.api.v1.monitor   import router as monitor_v1
from backend.app.api.v1.diagnosis import router as diagnosis_v1
from backend.app.api.v1.chatbot   import router as chatbot_v1
from backend.app.api.v1.architecture import router as architecture_v1

from backend.core.logging_config import log
from backend.core.config import API_HOST, API_PORT, MODEL_VERSION, EDGE_ARTIFACTS

app = FastAPI(
    title="TerraMind Unified Agriculture Intelligence",
    description="Unified Advisor, Monitor, and Diagnosis Suite (Hybrid Edge & Graph RAG)",
    version=MODEL_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS - allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routers ───────────────────────────────────────────────────────
# New Edge Advisor & Management
app.include_router(predict_router)
app.include_router(train_router)
app.include_router(sync_router)
app.include_router(benchmark_router)

# Unified v1 Suite
app.include_router(advisor_v1,   prefix="/api/v1/advisor",   tags=["v1-advisor"])
app.include_router(monitor_v1,   prefix="/api/v1/monitor",   tags=["v1-monitor"])
app.include_router(diagnosis_v1, prefix="/api/v1/diagnosis", tags=["v1-diagnosis"])
app.include_router(chatbot_v1,   prefix="/api/v1/chatbot",   tags=["v1-chatbot"])
app.include_router(architecture_v1, prefix="/api/v1/architecture", tags=["v1-architecture"])

# Graph RAG integration
from backend.app.api.v1.graph_rag import router as graph_rag_v1
app.include_router(graph_rag_v1, prefix="/api/v1/graph-rag", tags=["v1-graph-rag"])


# Serve prebuilt frontend (if available) so a single container can host UI + API.
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    async def spa_index():
        return FileResponse(str(FRONTEND_DIST / "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # Keep API and docs paths untouched.
        passthrough_prefixes = (
            "api/",
            "predict",
            "train/",
            "benchmark/",
            "sync/",
            "metadata",
            "health",
            "docs",
            "redoc",
            "openapi.json",
        )
        if full_path.startswith(passthrough_prefixes):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = FRONTEND_DIST / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))


# ── Health & utility endpoints ──────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "version": MODEL_VERSION}


@app.get("/api/states")
async def get_states():
    """Return list of states for the frontend dropdown."""
    path = EDGE_ARTIFACTS / "state_district_map.json"
    if not path.exists():
        from backend.core.config import CENTRAL_ARTIFACTS
        path = CENTRAL_ARTIFACTS / "state_district_map.json"
    if path.exists():
        with open(path) as f:
            sd_map = json.load(f)
        return {"states": sorted(sd_map.keys())}
    return {"states": []}


@app.get("/api/districts/{state}")
async def get_districts(state: str):
    """Return districts for a given state."""
    from backend.utils.naming_maps import normalize_state
    state = normalize_state(state)
    path = EDGE_ARTIFACTS / "state_district_map.json"
    if not path.exists():
        from backend.core.config import CENTRAL_ARTIFACTS
        path = CENTRAL_ARTIFACTS / "state_district_map.json"
    if path.exists():
        with open(path) as f:
            sd_map = json.load(f)
        return {"districts": sd_map.get(state, [])}
    return {"districts": []}


@app.on_event("startup")
async def startup():
    log.info("=== TerraMind Pre-Sowing Advisor API starting ===")
    log.info("Version: %s", MODEL_VERSION)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=API_HOST, port=API_PORT, reload=True)
