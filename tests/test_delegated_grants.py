import pytest
import asyncio
import json
from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.delegated_grants import DelegatedGrantService
from src.work_engine import WorkEngine, WorkError, now


@pytest.fixture()
def db():
    engine=create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); session=sessionmaker(bind=engine)()
    try: yield session
    finally: session.close(); engine.dispose()


def _action(db):
    work=WorkEngine(db); run=work.create_run("alice", {"domain":"homelab"})
    action=work.create_action("alice", run["id"], {"capability_id":"homelab.manage", "action_id":"service_restart", "approval_reference":"approval-1", "target_resources":["service:test"], "normalized_input":{"service":"test"}})
    return run, action


def test_grant_requires_exact_approval_digest_and_consumes_once(db):
    run, action = _action(db); svc=DelegatedGrantService(db)
    grant=svc.issue("alice", action["id"], {"approval_reference":"approval-1", "sealed_input_digest":action["sealed_input_digest"], "expires_at":(now()+timedelta(minutes=5)).isoformat(), "max_calls":1})
    authorized=svc.consume("alice", grant["id"], {"run_id":run["id"], "action_id":action["id"], "capability_id":"homelab.manage", "sealed_input_digest":action["sealed_input_digest"], "target_resource":"service:test"})
    assert authorized["authorized"] is True and authorized["authority_unchanged"] is True
    with pytest.raises(WorkError, match="call limit"):
        svc.consume("alice", grant["id"], {"run_id":run["id"], "action_id":action["id"], "capability_id":"homelab.manage", "sealed_input_digest":action["sealed_input_digest"]})


def test_grant_security_scope_checks_fail_closed(db):
    run, action = _action(db); svc=DelegatedGrantService(db)
    with pytest.raises(WorkError, match="exact action approval"):
        svc.issue("alice", action["id"], {"approval_reference":"wrong", "sealed_input_digest":action["sealed_input_digest"], "expires_at":(now()+timedelta(minutes=5)).isoformat()})
    grant=svc.issue("alice", action["id"], {"approval_reference":"approval-1", "sealed_input_digest":action["sealed_input_digest"], "expires_at":(now()+timedelta(minutes=5)).isoformat()})
    with pytest.raises(WorkError, match="grant not found"):
        svc.consume("bob", grant["id"], {"run_id":run["id"], "action_id":action["id"], "capability_id":"homelab.manage", "sealed_input_digest":action["sealed_input_digest"]})
    with pytest.raises(WorkError, match="scope mismatch"):
        svc.consume("alice", grant["id"], {"run_id":run["id"], "action_id":action["id"], "capability_id":"homelab.manage", "sealed_input_digest":"changed"})


def test_grant_parameter_and_target_scope_cannot_be_widened(db):
    run, action = _action(db); svc=DelegatedGrantService(db)
    grant=svc.issue("alice", action["id"], {"approval_reference":"approval-1", "sealed_input_digest":action["sealed_input_digest"], "expires_at":(now()+timedelta(minutes=5)).isoformat(), "parameter_constraints":{"service":"test"}})
    base={"run_id":run["id"], "action_id":action["id"], "capability_id":"homelab.manage", "sealed_input_digest":action["sealed_input_digest"], "target_resource":"service:test"}
    with pytest.raises(WorkError, match="parameter scope"):
        svc.consume("alice", grant["id"], base | {"parameters":{"service":"other"}})
    with pytest.raises(WorkError, match="target scope"):
        svc.consume("alice", grant["id"], base | {"target_resource":"service:other", "parameters":{"service":"test"}})
    authorized=svc.consume("alice", grant["id"], base | {"parameters":{"service":"test"}})
    assert authorized["authorized"] is True


def test_grant_constraints_cannot_disagree_with_sealed_action(db):
    _run, action = _action(db); svc=DelegatedGrantService(db)
    with pytest.raises(WorkError, match="sealed action input"):
        svc.issue("alice", action["id"], {"approval_reference":"approval-1", "sealed_input_digest":action["sealed_input_digest"], "expires_at":(now()+timedelta(minutes=5)).isoformat(), "parameter_constraints":{"service":"other"}})


def test_binding_boundary_consumes_only_exact_trusted_grant(db, monkeypatch):
    """A grant narrows a binding call; model payload cannot supply authority."""
    run, action = _action(db)
    svc = DelegatedGrantService(db)
    grant = svc.issue("alice", action["id"], {
        "approval_reference": "approval-1",
        "sealed_input_digest": action["sealed_input_digest"],
        "expires_at": (now() + timedelta(minutes=5)).isoformat(),
    })

    import src.tool_execution as execution
    import core.database as database
    monkeypatch.setattr(database, "SessionLocal", lambda: db)

    called = []

    async def fake_executor(block, owner=None):
        called.append(owner)
        return "manage_homelab", {"ok": True, "exit_code": 0}

    monkeypatch.setitem(execution._CAPABILITY_V1_EXECUTORS, "manage_homelab", fake_executor)
    block = type("Block", (), {"tool_type": "manage_homelab", "content": json.dumps({"action": "inspect_host"})})()
    result = asyncio.run(execution.execute_tool_block(
        block,
        owner="alice",
        delegated_grant_id=grant["id"],
        delegated_grant_run_id=run["id"],
        delegated_grant_action_id=action["id"],
        delegated_grant_digest=action["sealed_input_digest"],
        delegated_grant_target_resource="service:test",
    ))
    assert result[1].get("ok") is True, result
    assert called == ["alice"]

    blocked = asyncio.run(execution.execute_tool_block(
        block,
        owner="alice",
        delegated_grant_id=grant["id"],
        delegated_grant_run_id=run["id"],
        delegated_grant_action_id=action["id"],
        delegated_grant_digest=action["sealed_input_digest"],
    ))
    assert blocked[1]["blocked"] is True
    assert "call limit" in blocked[1]["error"]
