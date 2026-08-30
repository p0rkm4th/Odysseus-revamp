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
from src.capability_dependencies import artifact_manager, dependency_manager

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
    SetupContract("communications.contacts", "Contacts", "Stable people and organization references.", "contacts", "COMMUNICATIONS", dependencies=("core.identity",), permissions=("contacts read/write",)),
    SetupContract("home.smart-home", "Home Assistant", "Safe smart-home discovery and read boundary.", "smart-home", "HOME", dependencies=("core.identity",), secret_references=("secret://home-assistant/token",), permissions=("entity read", "mutations require policy")),
    SetupContract("technology.network", "Network Discovery", "Bounded private-network discovery through the host broker.", "network", "TECHNOLOGY", dependencies=("core.models",), permissions=("private IPv4 scope only",)),
    SetupContract("technology.homelab", "Homelab", "Brokered host diagnostics and bounded operations.", "homelab", "TECHNOLOGY", dependencies=("core.identity",), permissions=("brokered diagnostics",)),
    SetupContract("investigation.osint", "OSINT", "Public-source investigations with provenance and taint.", "osint", "INVESTIGATION", dependencies=("core.models",), permissions=("public sources only",)),
    SetupContract("business.crm", "Business / CRM", "Work-backed contacts, opportunities, and follow-ups.", "business", "BUSINESS", dependencies=("communications.contacts",), permissions=("canonical Work records",)),
    SetupContract("interaction.voice", "Voice", "Push-to-talk transcription and optional speech replies.", "voice", "INTERACTION", dependencies=("core.models",), permissions=("microphone only while enabled",)),
    SetupContract("advanced.automations", "Automations", "Reviewable schedules, Watches, and bounded responses.", "automations", "ADVANCED", dependencies=("core.identity",), permissions=("pre-authorized actions only",)),
)

SETUP_PROFILES: dict[str, tuple[str, ...]] = {
    "PERSONAL": ("core.identity", "core.models", "core.memory", "communications.email", "communications.calendar", "communications.contacts"),
    "HOME_HOMELAB": ("core.identity", "core.models", "core.memory", "home.smart-home", "technology.network", "technology.homelab"),
    "BUSINESS": ("core.identity", "core.models", "core.memory", "communications.email", "communications.calendar", "communications.contacts", "business.crm"),
    "SECURITY_RESEARCH": ("core.identity", "core.models", "core.memory", "technology.network", "investigation.osint"),
    "DEVELOPER": ("core.identity", "core.models", "technology.homelab", "advanced.automations"),
    "EVERYTHING": tuple(item.id for item in CONTRACTS),
}


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


def _health_projection(status: str) -> tuple[str, str]:
    """Map setup/configuration state to health without inventing a probe.

    ``CONFIGURED`` means that setup evidence exists; it does not mean that a
    provider or runtime was contacted successfully.  Keeping this distinction
    in the projection prevents the Integration Center from reporting false
    green while retaining the resumable setup state users already own.
    """
    if status == "NOT_CONFIGURED":
        return "NOT_CONFIGURED", "configuration evidence is absent"
    if status == "SKIPPED":
        return "DISABLED", "module was explicitly skipped"
    if status in {"DEGRADED", "NEEDS_ATTENTION"}:
        return "DEGRADED", "setup state requires attention"
    if status == "PARTIAL":
        return "PARTIAL", "setup is present but not fully validated"
    if status == "UNAVAILABLE":
        return "UNAVAILABLE", "module is unavailable"
    return "UNKNOWN", "configuration exists; no health probe has run"


class SetupCenterService:
    def contracts(self) -> list[dict[str, Any]]:
        return [_safe_contract(item) for item in CONTRACTS]

    def profiles(self) -> list[dict[str, Any]]:
        return [{"id": name, "module_ids": list(module_ids), "authority_unchanged": True} for name, module_ids in SETUP_PROFILES.items()]

    def apply_profile(self, owner: str, profile_id: str) -> dict[str, Any]:
        selected = SETUP_PROFILES.get(str(profile_id or "").upper())
        if selected is None:
            raise ValueError("unknown setup profile")
        import datetime
        with _STATE_LOCK:
            state = _read_state()
            owner_state = state.setdefault(owner, {})
            selected_ids = set(selected)
            for contract in CONTRACTS:
                entry = owner_state.get(contract.id) if isinstance(owner_state.get(contract.id), dict) else {}
                entry["selected"] = contract.id in selected_ids
                owner_state[contract.id] = entry
            owner_state["_profile"] = {"id": str(profile_id).upper(), "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
            atomic_write_json(SETUP_STATE_FILE, state, indent=2)
        projection = self.projection(owner)
        projection["selected_profile"] = str(profile_id).upper()
        return projection

    def projection(self, owner: str) -> dict[str, Any]:
        if not owner:
            raise ValueError("setup owner is required")
        state = _read_state().get(owner, {})
        selected_profile = state.get("_profile", {}).get("id") if isinstance(state, dict) and isinstance(state.get("_profile"), dict) else None
        integrations = _integration_names()
        modules = []
        for contract in CONTRACTS:
            detected, reason = _detected_status(contract, integrations)
            override = state.get(contract.id, {}) if isinstance(state, dict) else {}
            status = str(override.get("status") or detected).upper()
            if status not in STATUSES:
                status = detected
            health_status, health_reason = _health_projection(status)
            modules.append({
                **_safe_contract(contract),
                "status": status,
                "status_reason": str(override.get("status_reason") or reason),
                "health_status": str(override.get("health_status") or health_status).upper(),
                "health_reason": str(override.get("health_reason") or health_reason),
                "health_checked_at": override.get("health_checked_at"),
                "selected": bool(override.get("selected", status not in {"SKIPPED", "NOT_CONFIGURED"})),
                "last_updated": override.get("last_updated"),
            })
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
        return {"version": 1, "owner": owner, "categories": categories, "modules": modules, "selected_profile": selected_profile, "authority_unchanged": True, "secrets_exposed": False}

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
            health_status = module["health_status"]
            # ``connection`` is retained for existing clients, but now reflects
            # health evidence rather than merely setup selection.
            connection = (
                "CONNECTED" if health_status == "HEALTHY" else
                "DEGRADED" if health_status in {"PARTIAL", "DEGRADED", "UNKNOWN"} else
                "NOT_CONFIGURED" if health_status in {"NOT_CONFIGURED", "DISABLED"} else
                "DISCONNECTED"
            )
            integrations.append({
                **descriptor,
                "connection": connection,
                "setup_status": status,
                "health_status": health_status,
                "health_reason": module["health_reason"],
                "capabilities": list(module["permissions"]),
                "last_success": module.get("health_checked_at") if health_status == "HEALTHY" else None,
                "last_error": module["health_reason"] if health_status in {"DEGRADED", "UNAVAILABLE"} else None,
                "secret_values_exposed": False,
                "authority_unchanged": True,
            })
        return {"version": 1, "owner": owner, "integrations": integrations, "authority_unchanged": True, "secret_values_exposed": False}

    def permissions_projection(self, owner: str, grants: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Project effective capability vocabulary without becoming policy."""
        from src.capability_registry import CAPABILITY_REGISTRY
        capabilities = []
        for capability_id, capability in CAPABILITY_REGISTRY.items():
            capabilities.append({"capability_id": capability_id, "description": capability.description, "actions": [{
                "action_id": action.action_id, "effects": list(action.effects), "approval": action.approval.value,
                "execution_location": action.execution_location, "target_scope": action.target_scope,
                "dependencies": list(action.dependencies),
            } for action in capability.actions.values()]})
        safe_grants = []
        for grant in grants or []:
            if not isinstance(grant, dict): continue
            safe_grants.append({key: grant.get(key) for key in ("id", "run_id", "action_id", "capability_id", "target_resources", "parameter_constraints", "max_calls", "consumed_calls", "expires_at", "revoked_at")})
        return {"version": 1, "owner": owner, "capabilities": capabilities, "resource_contracts": dependency_manager.contracts(), "artifact_contracts": artifact_manager.contracts(), "setup_permissions": [{"module_id": module["id"], "title": module["title"], "permissions": module["permissions"], "status": module["status"]} for module in self.projection(owner)["modules"]], "grants": safe_grants, "authority_unchanged": True, "secret_values_exposed": False, "policy_source": "canonical capability/policy/approval services"}

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

    def record_health(self, owner: str, module_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """Persist secret-free evidence from one bounded health probe.

        Health evidence is deliberately separate from resumable setup status:
        a successful probe must not silently mark a module configured, and a
        failed optional probe must not erase configuration or permissions.
        """
        if not owner:
            raise ValueError("setup owner is required")
        if not isinstance(result, dict):
            raise ValueError("health result must be structured")
        if next((item for item in CONTRACTS if item.id == module_id), None) is None:
            raise ValueError("unknown setup module")
        import datetime
        status = str(result.get("status") or "UNKNOWN").upper()
        health_status = {
            "CONFIGURED": "HEALTHY",
            "HEALTHY": "HEALTHY",
            "DEGRADED": "DEGRADED",
            "UNAVAILABLE": "UNAVAILABLE",
            "NOT_CONFIGURED": "NOT_CONFIGURED",
        }.get(status, "UNKNOWN")
        detail = str(result.get("detail") or result.get("health_reason") or "health probe completed")[:500]
        checked_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with _STATE_LOCK:
            state = _read_state()
            owner_state = state.setdefault(owner, {})
            entry = owner_state.get(module_id) if isinstance(owner_state.get(module_id), dict) else {}
            entry.update({
                "health_status": health_status,
                "health_reason": detail,
                "health_checked_at": checked_at,
            })
            owner_state[module_id] = entry
            atomic_write_json(SETUP_STATE_FILE, state, indent=2)
        return result
