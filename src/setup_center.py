"""Declarative, resumable Setup Center projection.

Setup metadata is intentionally separate from integration execution.  A setup
record can describe dependencies and health expectations, but it never grants
authority or resolves secrets for a model or browser response.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from core.atomic_io import atomic_write_json
from src.constants import DATA_DIR
from src.integrations import load_integrations

SETUP_STATE_FILE = Path(DATA_DIR) / "setup-center-state.json"
_STATE_LOCK = Lock()
STATUSES = {"CONFIGURED", "PARTIAL", "NOT_CONFIGURED", "SKIPPED", "DEGRADED", "UNAVAILABLE", "NEEDS_ATTENTION"}


@dataclass(frozen=True)
class SetupContract:
    id: str
    title: str
    description: str
    icon: str
    category: str
    required: bool = False
    dependencies: tuple[str, ...] = ()
    secret_references: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    supports_skip: bool = True
    supports_reset: bool = True
    supports_reconfigure: bool = True


CONTRACTS: tuple[SetupContract, ...] = (
    SetupContract("core.identity", "Hades identity", "Identity and owner context for Hades.", "hades", "CORE", required=True, supports_skip=False, permissions=("owner identity",)),
    SetupContract("core.models", "Local AI / models", "Local model availability and routing prerequisites.", "models", "CORE", required=True, permissions=("model runtime metadata",)),
    SetupContract("core.memory", "Memory", "Working, semantic, episodic, and procedural memory preferences.", "memory", "CORE", permissions=("memory retention policy",)),
    SetupContract("communications.telegram", "Telegram", "Owner-paired remote interaction and notifications.", "telegram", "COMMUNICATIONS", dependencies=("core.identity",), secret_references=("secret://telegram/bot-token",), permissions=("private chat", "notifications")),
    SetupContract("communications.email", "Email", "Read and explicitly authorized send capabilities.", "email", "COMMUNICATIONS", dependencies=("core.identity",), permissions=("mailbox read", "send requires approval")),
    SetupContract("communications.calendar", "Calendar", "External calendar read/write scope and health.", "calendar", "COMMUNICATIONS", dependencies=("core.identity",), permissions=("calendar read", "calendar write")),
    SetupContract("communications.contacts", "Contacts", "Stable people and organization references.", "contacts", "COMMUNICATIONS", dependencies=("core.identity",), permissions=("contacts read/write")),
    SetupContract("home.smart-home", "Home Assistant", "Safe smart-home discovery and read boundary.", "smart-home", "HOME", dependencies=("core.identity",), secret_references=("secret://home-assistant/token",), permissions=("entity read", "mutations require policy")),
    SetupContract("technology.network", "Network Discovery", "Bounded private-network discovery through the host broker.", "network", "TECHNOLOGY", dependencies=("core.models",), permissions=("private IPv4 scope only",)),
    SetupContract("technology.homelab", "Homelab", "Brokered host diagnostics and bounded operations.", "homelab", "TECHNOLOGY", dependencies=("core.identity",), permissions=("brokered diagnostics",)),
    SetupContract("investigation.osint", "OSINT", "Public-source investigations with provenance and taint.", "osint", "INVESTIGATION", dependencies=("core.models",), permissions=("public sources only",)),
    SetupContract("business.crm", "Business / CRM", "Work-backed contacts, opportunities, and follow-ups.", "business", "BUSINESS", dependencies=("communications.contacts",), permissions=("canonical Work records",)),
    SetupContract("interaction.voice", "Voice", "Push-to-talk transcription and optional speech replies.", "voice", "INTERACTION", dependencies=("core.models",), permissions=("microphone only while enabled",)),
    SetupContract("advanced.automations", "Automations", "Reviewable schedules, Watches, and bounded responses.", "automations", "ADVANCED", dependencies=("core.identity",), permissions=("pre-authorized actions only",)),
)


def _safe_contract(contract: SetupContract) -> dict[str, Any]:
    value = asdict(contract)
    for key in ("dependencies", "secret_references", "permissions"):
        value[key] = list(value[key])
    return value


def _read_state() -> dict[str, Any]:
    try:
        value = json.loads(SETUP_STATE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _integration_names() -> set[str]:
    names = set()
    for item in load_integrations():
        if isinstance(item, dict) and item.get("enabled", True):
            names.add(str(item.get("name") or item.get("preset") or "").strip().lower())
    return names


def _detected_status(contract: SetupContract, integrations: set[str]) -> tuple[str, str]:
    cid = contract.id
    if cid == "core.identity":
        return "CONFIGURED", "authenticated owner context is available"
    if cid == "core.models":
        return "CONFIGURED", "model capability configuration is available"
    if cid == "core.memory":
        return "CONFIGURED", "canonical memory service is present"
    if cid == "communications.telegram":
        return ("CONFIGURED", "existing Telegram integration detected") if "telegram" in integrations else ("NOT_CONFIGURED", "no Telegram integration detected")
    if cid == "home.smart-home":
        return ("CONFIGURED", "Home Assistant integration detected") if {"home assistant", "homeassistant"} & integrations else ("NOT_CONFIGURED", "no Home Assistant integration detected")
    if cid == "communications.email":
        return ("CONFIGURED", "email capability is available; account health requires a safe test")
    if cid == "communications.calendar":
        return ("CONFIGURED", "calendar capability is available; provider health requires a safe test")
    if cid == "communications.contacts":
        return "PARTIAL", "contacts store is available; provider linkage is optional"
    if cid in {"technology.network", "technology.homelab", "investigation.osint", "business.crm", "interaction.voice", "advanced.automations"}:
        return "PARTIAL", "canonical subsystem is available; optional setup or health validation remains"
    return "NOT_CONFIGURED", "no setup evidence recorded"


class SetupCenterService:
    def contracts(self) -> list[dict[str, Any]]:
        return [_safe_contract(item) for item in CONTRACTS]

    def projection(self, owner: str) -> dict[str, Any]:
        if not owner:
            raise ValueError("setup owner is required")
        state = _read_state().get(owner, {})
        integrations = _integration_names()
        modules = []
        for contract in CONTRACTS:
            detected, reason = _detected_status(contract, integrations)
            override = state.get(contract.id, {}) if isinstance(state, dict) else {}
            status = str(override.get("status") or detected).upper()
            if status not in STATUSES:
                status = detected
            modules.append({**_safe_contract(contract), "status": status, "status_reason": str(override.get("status_reason") or reason), "selected": bool(override.get("selected", status not in {"SKIPPED", "NOT_CONFIGURED"})), "last_updated": override.get("last_updated")})
        status_by_id = {item["id"]: item["status"] for item in modules}
        for module in modules:
            dependencies = list(module.get("dependencies") or [])
            missing = [dependency for dependency in dependencies if status_by_id.get(dependency) != "CONFIGURED"]
            module["dependency_status"] = "READY" if not missing else "MISSING_DEPENDENCY"
            module["missing_dependencies"] = missing
            # This is advisory setup metadata only. It never changes module
            # status and never grants a capability when a dependency is ready.
            module["remediation_available"] = bool(missing and all(dependency in status_by_id for dependency in missing))
        categories: dict[str, list[dict[str, Any]]] = {}
        for module in modules:
            categories.setdefault(module["category"], []).append(module)
        return {"version": 1, "owner": owner, "categories": categories, "modules": modules, "authority_unchanged": True, "secrets_exposed": False}

    def integrations_projection(self, owner: str) -> dict[str, Any]:
        """Project integration readiness without exposing integration records."""
        projection = self.projection(owner)
        linked = {
            "communications.telegram": {"id": "telegram", "title": "Telegram"},
            "communications.email": {"id": "email", "title": "Email"},
            "communications.calendar": {"id": "calendar", "title": "Calendar"},
            "communications.contacts": {"id": "contacts", "title": "Contacts"},
            "home.smart-home": {"id": "home-assistant", "title": "Home Assistant"},
            "technology.network": {"id": "network", "title": "Network broker"},
            "technology.homelab": {"id": "homelab", "title": "Homelab broker"},
        }
        integrations = []
        for module in projection["modules"]:
            descriptor = linked.get(module["id"])
            if not descriptor:
                continue
            status = module["status"]
            connection = "CONNECTED" if status == "CONFIGURED" else "DEGRADED" if status in {"PARTIAL", "DEGRADED", "NEEDS_ATTENTION"} else "NOT_CONFIGURED" if status in {"NOT_CONFIGURED", "SKIPPED"} else "DISCONNECTED"
            integrations.append({**descriptor, "connection": connection, "setup_status": status, "capabilities": list(module["permissions"]), "last_success": module.get("last_updated") if status == "CONFIGURED" else None, "last_error": None, "secret_values_exposed": False, "authority_unchanged": True})
        return {"version": 1, "owner": owner, "integrations": integrations, "authority_unchanged": True, "secret_values_exposed": False}

    def update(self, owner: str, module_id: str, data: dict[str, Any]) -> dict[str, Any]:
        contract = next((item for item in CONTRACTS if item.id == module_id), None)
        if contract is None:
            raise ValueError("unknown setup module")
        status = str(data.get("status") or "").upper()
        if status not in STATUSES:
            raise ValueError("invalid setup status")
        if status == "SKIPPED" and not contract.supports_skip:
            raise ValueError("setup module cannot be skipped")
        import datetime
        with _STATE_LOCK:
            state = _read_state()
            owner_state = state.setdefault(owner, {})
            owner_state[module_id] = {"status": status, "selected": bool(data.get("selected", status != "SKIPPED")), "status_reason": str(data.get("status_reason") or "operator updated setup state")[:500], "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat()}
            atomic_write_json(SETUP_STATE_FILE, state, indent=2)
        return self.projection(owner)
