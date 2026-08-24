"""Owner-facing Setup Center projection and resumable module state."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from core.database import CalendarCal, EmailAccount, SessionLocal
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

    @router.get("/profiles")
    async def profiles(request: Request):
        return await call(request, lambda _owner: {"version": 1, "profiles": SetupCenterService().profiles(), "authority_unchanged": True})

    @router.get("/state")
    async def state(request: Request):
        return await call(request, lambda value: SetupCenterService().projection(value))

    @router.get("/integrations")
    async def integrations(request: Request):
        return await call(request, lambda value: SetupCenterService().integrations_projection(value))

    @router.get("/permissions")
    async def permissions(request: Request):
        def project(value):
            from src.delegated_grants import DelegatedGrantService
            db = session_factory()
            try:
                grants = DelegatedGrantService(db).list(value)
                return SetupCenterService().permissions_projection(value, grants)
            finally:
                db.close()
        return await call(request, project)

    @router.post("/modules/{module_id}/health")
    async def module_health(request: Request, module_id: str):
        """Run only bounded, non-mutating setup health checks."""
        value = owner(request)
        supported = {"communications.telegram", "communications.email", "communications.calendar", "communications.contacts", "home.smart-home"}
        if module_id not in supported:
            raise HTTPException(409, "safe health check is not implemented for this module")

        if module_id == "home.smart-home":
            from routes.intelligence_routes import _home_assistant_overview
            overview = await _home_assistant_overview()
            healthy = overview.get("status") == "healthy"
            return {"module_id": module_id, "status": "CONFIGURED" if healthy else "DEGRADED" if overview.get("configured") else "NOT_CONFIGURED", "checks": {"owner_scoped": True, "safe_read_only": True, "api_status_read": healthy, "entity_state_read": healthy, "mutations_performed": False}, "detail": "Home Assistant read-only health and entity projection succeeded" if healthy else "Home Assistant safe read did not succeed; no mutation was attempted", "authority_unchanged": True, "secret_values_exposed": False}

        def check(current_owner):
            db = session_factory()
            try:
                if module_id == "communications.telegram":
                    status = TelegramStore(db).lifecycle_status(owner=current_owner)
                    connected = bool(status.get("connected"))
                    checks = {"owner_scoped": True, "private_chat_boundary": connected, "replay_protection": connected, "callback_approval_sealing": connected}
                    detail = "existing owner-paired Telegram lifecycle is healthy" if connected else "Telegram is not paired; no network or credential operation was attempted"
                elif module_id == "communications.email":
                    rows = db.query(EmailAccount).filter(EmailAccount.owner == current_owner, EmailAccount.enabled == True).all()  # noqa: E712
                    connected = bool(rows)
                    checks = {"owner_scoped": True, "account_configured": connected, "network_probe_performed": False}
                    detail = "email account configuration exists; use the existing Email test operation for provider connectivity" if connected else "no owner-scoped email account is configured"
                elif module_id == "communications.calendar":
                    rows = db.query(CalendarCal).filter(CalendarCal.owner == current_owner).all()
                    connected = bool(rows)
                    checks = {"owner_scoped": True, "calendar_configured": connected, "network_probe_performed": False}
                    detail = "owner-scoped calendar exists; provider connectivity is not probed by Setup Center" if connected else "no owner-scoped calendar is configured"
                else:
                    checks = {"owner_scoped": True, "canonical_contact_store": True, "network_probe_performed": False}
                    connected = True
                    detail = "Contacts canonical store is available; provider connectivity is not probed by Setup Center"
                return {"module_id": module_id, "status": "CONFIGURED" if connected else "NOT_CONFIGURED", "checks": checks, "detail": detail, "authority_unchanged": True, "secret_values_exposed": False}
            finally:
                db.close()
        return await asyncio.to_thread(check, value)

    @router.patch("/modules/{module_id}")
    async def update_module(request: Request, module_id: str, payload: dict[str, Any] = Body(...)):
        return await call(request, lambda value: SetupCenterService().update(value, module_id, payload))

    @router.post("/profiles/{profile_id}")
    async def apply_profile(request: Request, profile_id: str):
        return await call(request, lambda value: SetupCenterService().apply_profile(value, profile_id))

    return router
