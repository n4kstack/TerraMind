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
from fastapi.middleware.gzip import GZipMiddleware
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

from backend.core.logging_config import log
from backend.core.config import API_HOST, API_PORT, MODEL_VERSION, EDGE_ARTIFACTS

app = FastAPI(
    title="TerraMind Unified Agriculture Intelligence",
    description="Unified Advisor, Monitor, and Diagnosis Suite (Hybrid Edge & Graph RAG)",
    version=MODEL_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Compress responses. Measured with Lighthouse against this server: the JS/CSS
# bundle was served uncompressed, costing ~1.65s of load time and ~300 kB on the
# wire (react-vendor alone dropped 174.6 kB -> 57 kB once gzipped).
# minimum_size skips tiny JSON payloads where framing overhead exceeds the win.
app.add_middleware(GZipMiddleware, minimum_size=1000)

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

# Graph RAG integration
from backend.app.api.v1.graph_rag import router as graph_rag_v1
app.include_router(graph_rag_v1, prefix="/api/v1/graph-rag", tags=["v1-graph-rag"])


# Serve prebuilt frontend (if available) so a single container can host UI + API.
#
# NOTE ON ORDERING: this is defined as a function and invoked at the BOTTOM of
# this module, after every API route has been registered. Starlette matches
# routes in registration order, so the `/{full_path:path}` catch-all below
# shadows anything registered after it. Previously this block ran inline here,
# which left `/health`, `/api/states` and `/api/districts/{state}` permanently
# unreachable (404) whenever a built frontend was present — the catch-all
# matched them first and raised 404 from its passthrough guard. Uptime checks
# against /health failed, and the frontend's state/district dropdowns silently
# fell back to their bundled copy of the dataset.
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


class ImmutableStaticFiles(StaticFiles):
    """
    Serves /assets with a one-year immutable cache.

    Safe specifically because Vite content-hashes every filename under /assets
    (index-84wK2YQI.js); a new build produces a new URL, so a stale cache entry
    can never be served for changed content. Previously these responses carried
    no Cache-Control at all, which Lighthouse flagged as a 0-second TTL on every
    asset — returning visitors re-downloaded the whole bundle each time.

    index.html is deliberately NOT covered here: it is the un-hashed entry point
    that names the hashed assets, and it must always revalidate.
    """

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def mount_frontend() -> None:
    """Register SPA static-file and fallback routes. Must be called last."""
    if not FRONTEND_DIST.exists():
        return

    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", ImmutableStaticFiles(directory=str(assets_dir)), name="frontend-assets")

    # index.html must never be cached. Vite fingerprints every file under
    # /assets, so those are safe to cache forever, but the entry HTML is what
    # points at them. Served without a Cache-Control header the browser applies
    # heuristic caching and can keep serving an old shell that references asset
    # filenames from a previous build - so a deploy appears not to have landed
    # until the user hard-refreshes.
    _INDEX_HEADERS = {"Cache-Control": "no-cache, must-revalidate"}

    def _index_response() -> FileResponse:
        return FileResponse(str(FRONTEND_DIST / "index.html"), headers=_INDEX_HEADERS)

    @app.get("/", include_in_schema=False)
    async def spa_index():
        return _index_response()

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
        # SPA deep links fall back to the shell, which must revalidate too.
        return _index_response()


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


# ── SPA fallback (MUST be the last route registration) ──────────────────
# Every API route above is now registered first, so the catch-all can no longer
# shadow them. Anything added below this line will be unreachable.
mount_frontend()


@app.on_event("startup")
async def startup():
    log.info("=== TerraMind Pre-Sowing Advisor API starting ===")
    log.info("Version: %s", MODEL_VERSION)

    # Pay the cold-start costs here rather than inside somebody's first
    # question. Both run on background threads, so startup is not delayed and a
    # failure in either only costs a slower or thinner first answer.
    try:
        from graph_rag.retrieval import agris_ods

        agris_ods.start_warmup()
    except Exception as exc:
        log.warning("AGRIS ODS warmup could not be scheduled: %s", exc)

    try:
        import threading

        from app.chatbot.client import is_available as llm_available, generate as llm_generate

        def _warm_llm():
            # A hosted free-tier model is slow on its first hit and quick once
            # warm. That gap is what made a first AugNosis query time out and
            # the identical retry succeed, so spend it on a throwaway token now.
            try:
                if llm_available():
                    llm_generate("ping", num_predict=1, timeout=30)
                    log.info("LLM warmup complete")
            except Exception as exc:
                log.info("LLM warmup skipped: %s", exc)

        threading.Thread(target=_warm_llm, name="llm-warmup", daemon=True).start()
    except Exception as exc:
        log.warning("LLM warmup could not be scheduled: %s", exc)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=API_HOST, port=API_PORT, reload=True)
