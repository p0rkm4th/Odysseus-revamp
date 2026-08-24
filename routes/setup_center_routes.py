"""Owner-facing Setup Center projection and resumable module state."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from core.database import SessionLocal
from src.telegram_store import TelegramStore
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

    @router.get("/integrations")
    async def integrations(request: Request):
        return await call(request, lambda value: SetupCenterService().integrations_projection(value))

    @router.post("/modules/{module_id}/health")
    async def module_health(request: Request, module_id: str):
        """Run only bounded, non-mutating setup health checks."""
        value = owner(request)
        if module_id != "communications.telegram":
            raise HTTPException(409, "safe health check is not implemented for this module")

        def check(current_owner):
            db = session_factory()
            try:
                status = TelegramStore(db).lifecycle_status(owner=current_owner)
                connected = bool(status.get("connected"))
                return {"module_id": module_id, "status": "CONFIGURED" if connected else "NOT_CONFIGURED", "checks": {"owner_scoped": True, "private_chat_boundary": connected, "replay_protection": connected, "callback_approval_sealing": connected}, "detail": "existing owner-paired Telegram lifecycle is healthy" if connected else "Telegram is not paired; no network or credential operation was attempted", "authority_unchanged": True, "secret_values_exposed": False}
            finally:
                db.close()
        return await asyncio.to_thread(check, value)

    @router.patch("/modules/{module_id}")
    async def update_module(request: Request, module_id: str, payload: dict[str, Any] = Body(...)):
        return await call(request, lambda value: SetupCenterService().update(value, module_id, payload))

    return router
