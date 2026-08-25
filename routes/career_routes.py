"""Authenticated Career projection routes under the Work workspace."""
import asyncio
from fastapi import APIRouter, HTTPException, Request
from core.database import SessionLocal
from src.auth_helpers import require_user
from src.owner_identity import effective_storage_owner
from src.career_service import CareerService


def setup_career_routes(*, session_factory=SessionLocal):
    router = APIRouter(prefix="/api/work/career", tags=["career"])
    async def read(request, action):
        user = require_user(request); owner = effective_storage_owner(user)
        if not owner: raise HTTPException(401, "authenticated Career owner required")
        def run():
            with session_factory() as db: return CareerService(db).read(owner, action)
        try: return await asyncio.to_thread(run)
        except Exception as exc: raise HTTPException(409, str(exc)) from exc
    @router.get("/overview")
    async def overview(request: Request): return await read(request, "overview")
    @router.get("/saved")
    async def saved(request: Request): return await read(request, "saved_opportunities")
    @router.get("/applications")
    async def applications(request: Request): return await read(request, "applications")
    @router.get("/follow-ups")
    async def follow_ups(request: Request): return await read(request, "follow_ups")
    @router.get("/interviews")
    async def interviews(request: Request): return await read(request, "interviews")
    @router.get("/provider-status")
    async def provider_status_route(request: Request): return await read(request, "provider_status")
    return router
