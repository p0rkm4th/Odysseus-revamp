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


def _to_verifying(svc, owner, run_id):
    for state in ("planning", "ready", "executing", "verifying"):
        svc.verified_execution_step(owner, run_id, state)


def test_verification_failure_requires_explicit_compensation_and_restoration(db):
    svc = WorkEngine(db); run = svc.create_run("alice", {"domain":"homelab"}); _to_verifying(svc, "alice", run["id"])
    compensating = svc.complete_verification("alice", run["id"], success=False, details={"postcondition":"inactive"}, compensation_reference="action://restore-config")
    assert compensating["lifecycle_state"] == "compensating"
    verifying = svc.complete_compensation("alice", run["id"], success=True, details={"restored":"prior-config"})
    assert verifying["lifecycle_state"] == "verifying"
    final = svc.complete_verification("alice", run["id"], success=True, details={"postcondition":"restored"})
    assert final["lifecycle_state"] == "succeeded" and final["result_summary"]["outcome"] == "compensated_restored"
    replay = svc.reconstruct_run("alice", run["id"])
    assert [x["state"] for x in replay["transitions"]][-3:] == ["compensating", "verifying", "succeeded"]


def test_verification_failure_without_compensation_is_distinct(db):
    svc = WorkEngine(db); run = svc.create_run("alice", {}); _to_verifying(svc, "alice", run["id"])
    final = svc.complete_verification("alice", run["id"], success=False, details={"postcondition":"unmet"})
    assert final["status"] == "failed" and final["result_summary"]["outcome"] == "execution_succeeded_verification_failed"
    with pytest.raises(WorkError, match="run not found"):
        svc.complete_verification("bob", run["id"], success=True)


def test_compensation_failure_is_terminal_and_explicit(db):
    svc = WorkEngine(db); run = svc.create_run("alice", {}); _to_verifying(svc, "alice", run["id"])
    svc.complete_verification("alice", run["id"], success=False, compensation_reference="action://restore")
    final = svc.complete_compensation("alice", run["id"], success=False, details={"error":"restore unavailable"})
    assert final["status"] == "failed" and final["result_summary"]["outcome"] == "compensation_failed"
