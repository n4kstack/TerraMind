"""Architecture snapshot API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.services.architecture_service import generate_architecture_snapshot

router = APIRouter()


@router.get(
    "/snapshot",
    summary="Get Project Architecture Snapshot",
    description=(
        "Scans the codebase and returns an auto-generated read-only architecture graph "
        "including layers, modules, dependencies, API boundaries, and execution paths."
    ),
)
async def architecture_snapshot(force: bool = Query(False, description="Force a fresh scan and bypass cache.")):
    return generate_architecture_snapshot(force_refresh=force)
