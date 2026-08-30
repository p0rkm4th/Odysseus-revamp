import json

import pytest

from src import setup_center


def test_contract_registry_is_declarative_and_does_not_expose_secrets():
    contracts = setup_center.SetupCenterService().contracts()
    telegram = next(item for item in contracts if item["id"] == "communications.telegram")
    assert telegram["category"] == "COMMUNICATIONS"
    assert telegram["secret_references"] == ["secret://telegram/bot-token"]
    assert "token" not in json.dumps(telegram).lower() or "secret://" in json.dumps(telegram)


def test_projection_detects_existing_modules_and_preserves_authority(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(setup_center, "load_integrations", lambda: [{"name": "Home Assistant", "enabled": True, "api_key": "secret-value"}])
    projection = setup_center.SetupCenterService().projection("alice")
    by_id = {item["id"]: item for item in projection["modules"]}
    assert by_id["core.identity"]["status"] == "CONFIGURED"
    assert by_id["home.smart-home"]["status"] == "CONFIGURED"
    assert projection["authority_unchanged"] is True
    assert projection["secrets_exposed"] is False
    assert "secret-value" not in json.dumps(projection)


def test_setup_state_is_resumable_and_skip_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "state.json")
    service = setup_center.SetupCenterService()
    updated = service.update("alice", "communications.telegram", {"status": "SKIPPED"})
    telegram = next(item for item in updated["modules"] if item["id"] == "communications.telegram")
    assert telegram["status"] == "SKIPPED"
    resumed = service.projection("alice")
    assert next(item for item in resumed["modules"] if item["id"] == "communications.telegram")["status"] == "SKIPPED"
    with pytest.raises(ValueError, match="cannot be skipped"):
        service.update("alice", "core.identity", {"status": "SKIPPED"})


def test_unknown_module_and_status_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "state.json")
    service = setup_center.SetupCenterService()
    with pytest.raises(ValueError, match="unknown setup module"):
        service.update("alice", "missing.module", {"status": "CONFIGURED"})
    with pytest.raises(ValueError, match="invalid setup status"):
        service.update("alice", "communications.email", {"status": "READY"})


def test_integration_projection_is_secret_free_and_maps_setup_health(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "state.json")
    projection = setup_center.SetupCenterService().integrations_projection("alice")
    telegram = next(item for item in projection["integrations"] if item["id"] == "telegram")
    assert telegram["connection"] == "NOT_CONFIGURED"
    assert telegram["health_status"] == "NOT_CONFIGURED"
    assert telegram["secret_values_exposed"] is False
    assert projection["authority_unchanged"] is True


def test_configured_setup_does_not_claim_provider_health_without_a_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "state.json")
    projection = setup_center.SetupCenterService().projection("alice")
    modules = {item["id"]: item for item in projection["modules"]}
    # Configuration evidence is useful, but it is not a successful network or
    # runtime health check.
    assert modules["core.models"]["status"] == "CONFIGURED"
    assert modules["core.models"]["health_status"] == "UNKNOWN"
    assert "no health probe" in modules["core.models"]["health_reason"]

    integrations = setup_center.SetupCenterService().integrations_projection("alice")
    email = next(item for item in integrations["integrations"] if item["id"] == "email")
    assert email["setup_status"] == "CONFIGURED"
    assert email["health_status"] == "UNKNOWN"
    assert email["connection"] == "DEGRADED"
    assert email["last_success"] is None


def test_health_probe_persists_health_evidence_without_changing_setup_status(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "state.json")
    service = setup_center.SetupCenterService()
    service.update("alice", "communications.email", {"status": "CONFIGURED"})
    service.record_health("alice", "communications.email", {
        "module_id": "communications.email",
        "status": "DEGRADED",
        "detail": "provider check was not attempted by Setup Center",
    })
    module = next(item for item in service.projection("alice")["modules"] if item["id"] == "communications.email")
    assert module["status"] == "CONFIGURED"
    assert module["health_status"] == "DEGRADED"
    assert module["health_reason"] == "provider check was not attempted by Setup Center"
    assert module["health_checked_at"]


def test_contract_declares_telegram_setup_requirements():
    telegram = next(item for item in setup_center.CONTRACTS if item.id == "communications.telegram")
    assert telegram.dependencies == ("core.identity",)
    assert "private chat" in telegram.permissions
    assert telegram.supports_reconfigure is True


def test_communications_contracts_expose_read_write_authority_explicitly():
    contracts = {item.id: item for item in setup_center.CONTRACTS}
    assert "mailbox read" in contracts["communications.email"].permissions
    assert "send requires approval" in contracts["communications.email"].permissions
    assert "calendar write" in contracts["communications.calendar"].permissions
    assert "contacts read/write" in contracts["communications.contacts"].permissions


def test_projection_resolves_dependency_readiness_without_granting_authority(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "state.json")
    service = setup_center.SetupCenterService()
    projection = service.projection("alice")
    modules = {item["id"]: item for item in projection["modules"]}
    assert modules["core.identity"]["dependency_status"] == "READY"
    assert modules["communications.telegram"]["dependency_status"] == "READY"
    assert modules["technology.network"]["dependency_status"] == "READY"
    service.update("alice", "core.identity", {"status": "NEEDS_ATTENTION"})
    degraded = {item["id"]: item for item in service.projection("alice")["modules"]}
    assert degraded["communications.telegram"]["dependency_status"] == "MISSING_DEPENDENCY"
    assert degraded["communications.telegram"]["missing_dependencies"] == ["core.identity"]
    assert degraded["communications.telegram"]["remediation_available"] is True
    assert degraded["communications.telegram"]["status"] == "NOT_CONFIGURED"


def test_setup_profiles_only_change_selection_and_are_resumable(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "state.json")
    service = setup_center.SetupCenterService()
    profiles = {item["id"]: item for item in service.profiles()}
    assert "communications.email" in profiles["PERSONAL"]["module_ids"]
    projection = service.apply_profile("alice", "SECURITY_RESEARCH")
    selected = {item["id"]: item["selected"] for item in projection["modules"]}
    assert projection["selected_profile"] == "SECURITY_RESEARCH"
    assert selected["investigation.osint"] is True
    assert selected["communications.email"] is False
    assert projection["authority_unchanged"] is True
    with pytest.raises(ValueError, match="unknown setup profile"):
        service.apply_profile("alice", "ROOT_ACCESS")


def test_permissions_projection_is_owner_facing_and_secret_free(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "state.json")
    projection = setup_center.SetupCenterService().permissions_projection("alice", [{
        "id": "grant-1", "capability_id": "homelab.manage", "sealed_input_digest": "secret-digest",
        "run_id": "run-1", "action_id": "action-1", "max_calls": 1, "consumed_calls": 0,
    }])
    assert any(item["capability_id"] == "homelab.manage" for item in projection["capabilities"])
    assert projection["grants"][0]["id"] == "grant-1"
    assert "sealed_input_digest" not in json.dumps(projection)
    assert projection["authority_unchanged"] is True


def test_safe_health_checks_cover_non_mutating_core_and_domain_readiness():
    from pathlib import Path
    routes = (Path(__file__).resolve().parents[1] / "routes/setup_center_routes.py").read_text()
    frontend = (Path(__file__).resolve().parents[1] / "static/js/setupCenter.js").read_text()
    for module_id in ("core.models", "core.memory", "investigation.osint", "technology.network", "technology.homelab", "business.crm", "interaction.voice", "advanced.automations"):
        assert module_id in routes
        assert module_id in frontend
    # The readiness route must validate the canonical MemoryManager that the
    # application initializes, rather than a stale/nonexistent projection
    # helper that turns the owner-facing health check into HTTP 500.
    assert "from src.memory import MemoryManager" in routes
    assert "callable(MemoryManager)" in routes
    assert "scan_performed" in routes
    assert "mutations_performed" in routes
    assert "canonical_primitives" in routes
