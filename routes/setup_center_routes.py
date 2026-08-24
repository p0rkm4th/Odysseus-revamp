"""Owner-facing Setup Center projection and resumable module state."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from core.database import SessionLocal
from src.auth_helpers import require_user
from src.owner_identity import effective_storage_owner
from src.setup_center import SetupCenterService


def setup_setup_center_routes(*, session_factory=SessionLocal) -> APIRouter:
    router = APIRouter(prefix="/api/setup-center", tags=["setup-center"])

    def owner(request: Request) -> str:
        user = require_user(request)
        value = effective_storage_owner(user)
        if not value:
            raise HTTPException(401, "authenticated setup owner required")
        return value

    async def call(request: Request, fn):
        value = owner(request)
        try:
            return await asyncio.to_thread(fn, value)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/contracts")
    async def contracts(request: Request):
        return await call(request, lambda _owner: {"version": 1, "contracts": SetupCenterService().contracts(), "authority_unchanged": True})

    @router.get("/state")
    async def state(request: Request):
        return await call(request, lambda value: SetupCenterService().projection(value))

    @router.patch("/modules/{module_id}")
    async def update_module(request: Request, module_id: str, payload: dict[str, Any] = Body(...)):
        return await call(request, lambda value: SetupCenterService().update(value, module_id, payload))

    return router
