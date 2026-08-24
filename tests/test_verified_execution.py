import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.work_engine import WorkEngine, WorkError
from src.world_model import WorldModelService


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
    action = svc.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "execute_network_discovery", "approval_reference": "approval-1", "locks": ["network:private_scope"]})
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


def test_invalidation_propagates_only_through_strong_declared_dependency(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    database = svc.record_claim("alice", {"claim_class": "Observation", "subject_ref": "service:postgres", "predicate": "health", "value": "healthy", "source": "probe"})
    app = svc.record_claim("alice", {"claim_class": "Observation", "subject_ref": "service:acme", "predicate": "health", "value": "healthy", "source": "probe"})
    unrelated = svc.record_claim("alice", {"claim_class": "Observation", "subject_ref": "service:nginx", "predicate": "health", "value": "healthy", "source": "probe"})
    WorldModelService(db).create_relationship("alice", {"source_ref": "service:acme", "relation": "DEPENDS_ON", "target_ref": "service:postgres", "status": "observed", "confidence_class": "high", "observation_kind": "observed", "source": "cmdb"})
    result = svc.invalidate_state("alice", run["id"], [{"subject_ref": "service:postgres", "predicate": "health", "propagate": {"relation": "DEPENDS_ON", "predicate": "health"}}])
    assert set(result["stale_claims"]) == {database["id"], app["id"]}
    assert unrelated["id"] not in result["stale_claims"]


def test_invalidation_does_not_propagate_proposed_dependency(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    database = svc.record_claim("alice", {"claim_class": "Observation", "subject_ref": "service:postgres", "predicate": "health", "value": "healthy", "source": "probe"})
    app = svc.record_claim("alice", {"claim_class": "Observation", "subject_ref": "service:acme", "predicate": "health", "value": "healthy", "source": "probe"})
    WorldModelService(db).create_relationship("alice", {"source_ref": "service:acme", "relation": "DEPENDS_ON", "target_ref": "service:postgres", "status": "proposed", "confidence_class": "high", "observation_kind": "inferred", "source": "model"})
    result = svc.invalidate_state("alice", run["id"], [{"subject_ref": "service:postgres", "predicate": "health", "propagate": {"relation": "DEPENDS_ON", "predicate": "health"}}])
    assert result["stale_claims"] == [database["id"]]
    assert app["id"] not in result["stale_claims"]


def test_invalid_transition_fails_closed(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {})
    with pytest.raises(WorkError, match="invalid execution transition"):
        svc.verified_execution_step("alice", run["id"], "succeeded")


def test_consequential_execution_requires_structured_plan_validation(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab", "plan": [{"capability_id": "homelab.manage", "action_id": "execute_network_discovery", "target_resources": ["network:public"]}]})
    svc.verified_execution_step("alice", run["id"], "planning")
    svc.verified_execution_step("alice", run["id"], "ready")
    with pytest.raises(WorkError, match="plan validation failed.*scope_invalid"):
        svc.verified_execution_step("alice", run["id"], "executing")


def test_cancellation_is_immediate_before_mutation_and_blocks_new_actions(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    cancelled = svc.request_cancel("alice", run["id"], reason="owner stopped plan")
    assert cancelled["lifecycle_state"] == "cancelled"
    with pytest.raises(WorkError, match="cancellation requested"):
        svc.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "service_status"})


def test_cancellation_during_execution_requires_verification(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    svc.verified_execution_step("alice", run["id"], "planning")
    svc.verified_execution_step("alice", run["id"], "ready")
    svc.verified_execution_step("alice", run["id"], "executing")
    requested = svc.request_cancel("alice", run["id"], reason="stop after bounded action")
    assert requested["continuation_state"]["cancellation_requested"] is True
    with pytest.raises(WorkError, match="minimum verification"):
        svc.verified_execution_step("alice", run["id"], "cancelled")
    verifying = svc.verified_execution_step("alice", run["id"], "verifying")
    assert verifying["lifecycle_state"] == "verifying"


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


def test_legacy_transition_path_enforces_lifecycle_graph_and_plan_validation(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "network", "plan": [{
        "capability_id": "homelab.manage", "action_id": "execute_network_discovery",
        "target_resources": ["network:public"],
    }]})
    work.transition_run("alice", run["id"], "planning")
    with pytest.raises(WorkError, match="plan validation failed before execution"):
        work.transition_run("alice", run["id"], "executing")
    assert work.get_run("alice", run["id"])["lifecycle_state"] == "planning"

    projection = work.create_run("alice", {"domain": "general"})
    with pytest.raises(WorkError, match="invalid execution transition"):
        work.transition_run("alice", projection["id"], "succeeded")
