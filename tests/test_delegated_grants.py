import pytest
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
