import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.run_planner import RunPlanner
from src.work_engine import WorkEngine


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_preview_is_structured_and_owner_scoped(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab", "intent": {"goal": "discover private network"}, "plan": [{
        "capability_id": "homelab.manage", "action_id": "execute_network_discovery",
        "target_resources": ["network:private_scope"], "preconditions": [],
    }]})
    preview = RunPlanner(db).compile("alice", run["id"])
    assert preview["objective"] == {"goal": "discover private network"}
    assert preview["actions"][0]["known"] is True
    assert preview["actions"][0]["contract"]["approval"] == "exact"
    with pytest.raises(Exception):
        RunPlanner(db).compile("bob", run["id"])


def test_validation_rejects_unknown_action_and_scope(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "network", "plan": [
        {"capability_id": "homelab.manage", "action_id": "execute_network_discovery", "target_resources": ["network:public"]},
        {"capability_id": "missing.capability", "action_id": "execute"},
    ]})
    result = RunPlanner(db).validate("alice", run["id"])
    assert result["valid"] is False
    assert {failure["code"] for failure in result["failures"]} >= {"scope_invalid", "unknown_action_spec", "approval_required"}


def test_validation_surfaces_stale_precondition_without_mutating_run(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab", "plan": [{
        "capability_id": "homelab.manage", "action_id": "service_status",
        "preconditions": [{"subject_ref": "service:nginx", "predicate": "status"}],
    }]})
    work.record_claim("alice", {"claim_class": "Observation", "subject_ref": "service:nginx", "predicate": "status", "value": "active", "source": "old-check", "valid_until": "2020-01-01T00:00:00"})
    result = RunPlanner(db).validate("alice", run["id"])
    assert result["valid"] is False
    assert any(f["code"] == "knowledge_gap" for f in result["failures"])
    assert work.get_run("alice", run["id"])["lifecycle_state"] == "created"
