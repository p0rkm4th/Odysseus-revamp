"""Fail-closed and recoverability checks for the verified execution boundary."""
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from src.setup_center import SetupCenterService
from src.tool_execution import execute_registered_binding
from src.work_engine import AmbiguousExecution, WorkEngine, WorkError


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close(); engine.dispose()


def test_malformed_binding_result_fails_action_and_releases_locks(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab"})
    action = work.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["host:test"]})
    with pytest.raises(WorkError, match="structured result"):
        work.execute_bound_action("alice", action["id"], lambda _action: "malformed provider output")
    stored = work.get_run("alice", run["id"])["actions"][0]
    assert stored["status"] == "failed"
    assert work.lock_conflicts("alice", action["id"]) == []


def test_ambiguous_action_cannot_be_resolved_cross_owner(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab"})
    action = work.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["host:test"]})
    work.execute_bound_action("alice", action["id"], lambda _action: (_ for _ in ()).throw(AmbiguousExecution("timeout")))
    with pytest.raises(WorkError, match="action not found"):
        work.resolve_ambiguous_action("bob", action["id"], occurred=False)


def test_unavailable_registered_binding_fails_closed():
    with pytest.raises(ValueError, match="unavailable"):
        asyncio.run(execute_registered_binding(tool_name="not-registered", payload={}, owner="alice"))


def test_setup_projection_never_returns_integration_secrets(tmp_path, monkeypatch):
    import src.setup_center as setup_center
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(setup_center, "load_integrations", lambda: [{"name": "Telegram", "bot_token": "owner-secret"}, {"name": "Home Assistant", "api_key": "ha-secret"}])
    projection = SetupCenterService().projection("alice")
    rendered = str(projection)
    assert "owner-secret" not in rendered and "ha-secret" not in rendered
    assert projection["authority_unchanged"] is True
    assert projection["secrets_exposed"] is False
