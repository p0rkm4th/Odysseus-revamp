import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.work_engine import WorkEngine, WorkError


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


def test_execution_lifecycle_replays_and_releases_locks(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    action = svc.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "execute_network_discovery", "locks": ["network:private_scope"]})
    svc.acquire_action_locks("alice", action["id"])
    svc.verified_execution_step("alice", run["id"], "planning")
    svc.verified_execution_step("alice", run["id"], "ready")
    svc.verified_execution_step("alice", run["id"], "executing")
    svc.verified_execution_step("alice", run["id"], "verifying")
    final = svc.verified_execution_step("alice", run["id"], "succeeded")
    assert final["status"] == "completed"
    assert all(lock["released_at"] for lock in svc.get_run("alice", run["id"])["locks"])
    assert svc.reconstruct_run("alice", run["id"])["lifecycle_state"] == "succeeded"


def test_invalidation_preserves_claim_and_makes_gap_stale(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    claim = svc.record_claim("alice", {"claim_class": "Observation", "subject_ref": "service:nginx", "predicate": "status", "value": "active", "source": "probe"})
    result = svc.invalidate_state("alice", run["id"], [{"subject_ref": "service:nginx", "predicate": "status"}])
    assert claim["id"] in result["stale_claims"]
    assert svc.knowledge_gaps("alice", [{"subject_ref": "service:nginx", "predicate": "status"}])["stale"]


def test_invalid_transition_fails_closed(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {})
    with pytest.raises(WorkError, match="invalid execution transition"):
        svc.verified_execution_step("alice", run["id"], "succeeded")
