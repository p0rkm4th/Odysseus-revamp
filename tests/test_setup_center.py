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
    assert telegram["secret_values_exposed"] is False
    assert projection["authority_unchanged"] is True


def test_contract_declares_telegram_setup_requirements():
    telegram = next(item for item in setup_center.CONTRACTS if item.id == "communications.telegram")
    assert telegram.dependencies == ("core.identity",)
    assert "private chat" in telegram.permissions
    assert telegram.supports_reconfigure is True
