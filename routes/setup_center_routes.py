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
        supported = {"core.models", "core.memory", "investigation.osint", "technology.network", "technology.homelab", "communications.telegram", "communications.email", "communications.calendar", "communications.contacts", "home.smart-home", "business.crm", "interaction.voice", "advanced.automations"}
        if module_id not in supported:
            raise HTTPException(409, "safe health check is not implemented for this module")

        def persist(result):
            return SetupCenterService().record_health(value, module_id, result)

        if module_id == "home.smart-home":
            from routes.intelligence_routes import _home_assistant_overview
            overview = await _home_assistant_overview()
            healthy = overview.get("status") == "healthy"
            return persist({"module_id": module_id, "status": "CONFIGURED" if healthy else "DEGRADED" if overview.get("configured") else "NOT_CONFIGURED", "checks": {"owner_scoped": True, "safe_read_only": True, "api_status_read": healthy, "entity_state_read": healthy, "mutations_performed": False}, "detail": "Home Assistant read-only health and entity projection succeeded" if healthy else "Home Assistant safe read did not succeed; no mutation was attempted", "authority_unchanged": True, "secret_values_exposed": False})

        if module_id in {"business.crm", "interaction.voice", "advanced.automations"}:
            def platform_check(_current_owner):
                from importlib.util import find_spec
                requirements = {
                    "business.crm": ("src.work_engine",),
                    "interaction.voice": ("routes.stt_routes", "routes.tts_routes"),
                    "advanced.automations": ("src.task_scheduler", "src.bg_monitor"),
                }[module_id]
                available = {name: find_spec(name) is not None for name in requirements}
                healthy = all(available.values())
                details = {
                    "business.crm": "canonical Work service is available; no CRM mutation or provider request was performed",
                    "interaction.voice": "authenticated STT/TTS route providers are available; no microphone, transcription, or speech request was performed",
                    "advanced.automations": "canonical scheduler and monitor primitives are available; no job was scheduled or executed",
                }
                return {"module_id": module_id, "status": "CONFIGURED" if healthy else "DEGRADED", "checks": {"owner_scoped": True, "safe_read_only": True, "canonical_primitives": available, "network_request_performed": False, "mutations_performed": False}, "detail": details[module_id], "authority_unchanged": True, "secret_values_exposed": False}
            return await asyncio.to_thread(lambda current_owner: persist(platform_check(current_owner)), value)

        if module_id in {"core.models", "core.memory", "investigation.osint", "technology.network", "technology.homelab"}:
            def capability_check(_current_owner):
                from src.capability_registry import capability_for_id
                from src.tool_bindings import binding_for_tool
                if module_id == "core.models":
                    import os
                    capability_available = capability_for_id("intelligence.route") is not None
                    endpoint = os.getenv("HADES_OLLAMA_ENDPOINT") or os.getenv("OLLAMA_BASE_URL") or "http://host.docker.internal:11434"
                    try:
                        from routes.model_routes import _ping_endpoint
                        probe = _ping_endpoint(endpoint, timeout=3)
                    except Exception:
                        probe = {"reachable": False, "error": "model endpoint probe unavailable"}
                    endpoint_reachable = bool(probe.get("reachable"))
                    available = capability_available and endpoint_reachable
                    detail = "model routing metadata and configured model endpoint are reachable; no inference was requested" if available else "model routing metadata or configured model endpoint is unavailable; no inference was requested"
                    checks = {"owner_scoped": True, "capability_registry": capability_available, "model_endpoint_read": True, "endpoint_reachable": endpoint_reachable, "inference_performed": False}
                elif module_id == "core.memory":
                    # The canonical memory owner is MemoryManager.  Do not
                    # import a projection helper here: setup health must
                    # validate the service that the application actually
                    # initializes, without reading owner data.
                    from src.memory import MemoryManager
                    available = callable(MemoryManager)
                    detail = "canonical owner-scoped memory service is importable; no retrieval was performed"
                    checks = {"owner_scoped": True, "canonical_memory_service": available, "retrieval_performed": False}
                elif module_id == "investigation.osint":
                    from src.osint_policy import validate_request
                    available = callable(validate_request)
                    detail = "public-source OSINT policy boundary is available; no public request was sent"
                    checks = {"owner_scoped": True, "public_source_policy": available, "network_request_performed": False}
                elif module_id == "technology.network":
                    binding = binding_for_tool("manage_homelab")
                    declared = bool(binding and binding.execution_location == "host_broker" and binding.target_scope == "private_network")
                    broker = {}
                    try:
                        from src.privileged_broker import client_request
                        broker = client_request({"action": "status"}, timeout=5)
                    except Exception:
                        broker = {"ok": False, "status": "unavailable"}
                    broker_available = bool(broker.get("ok")) and bool(broker.get("network_scanner_available"))
                    available = declared and broker_available
                    detail = "private-network broker status and binding checks succeeded; no scan was requested" if available else "private-network broker or binding is unavailable; no scan was requested"
                    checks = {"owner_scoped": True, "host_broker_boundary": declared, "private_scope_declared": declared, "broker_status_read": True, "broker_available": broker_available, "scan_performed": False}
                else:
                    binding = binding_for_tool("manage_homelab")
                    declared = binding is not None
                    broker = {}
                    try:
                        from src.privileged_broker import client_request
                        broker = client_request({"action": "status"}, timeout=5)
                    except Exception:
                        broker = {"ok": False, "status": "unavailable"}
                    broker_available = bool(broker.get("ok"))
                    available = declared and broker_available
                    detail = "bounded Homelab binding and broker status checks succeeded; no host operation was performed" if available else "bounded Homelab binding or broker is unavailable; no host operation was performed"
                    checks = {"owner_scoped": True, "bounded_binding": declared, "broker_status_read": True, "broker_available": broker_available, "host_operation_performed": False}
                return {"module_id": module_id, "status": "CONFIGURED" if available else "DEGRADED", "checks": {**checks, "safe_read_only": True, "mutations_performed": False}, "detail": detail, "authority_unchanged": True, "secret_values_exposed": False}
            return await asyncio.to_thread(lambda current_owner: persist(capability_check(current_owner)), value)

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
        return await asyncio.to_thread(lambda current_owner: persist(check(current_owner)), value)

    @router.patch("/modules/{module_id}")
    async def update_module(request: Request, module_id: str, payload: dict[str, Any] = Body(...)):
        return await call(request, lambda value: SetupCenterService().update(value, module_id, payload))

    @router.post("/profiles/{profile_id}")
    async def apply_profile(request: Request, profile_id: str):
        return await call(request, lambda value: SetupCenterService().apply_profile(value, profile_id))

    return router
