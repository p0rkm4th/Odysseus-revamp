from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.work_models import WorkAction, WorkCommitment, WorkGoal, WorkProject, WorkRun, WorkTask
from src.work_engine import AmbiguousExecution, WorkEngine, WorkError

@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try: yield session
    finally: session.close(); engine.dispose()

def test_work_hierarchy_dependencies_and_cycle_rejection(db):
    svc = WorkEngine(db)
    goal = svc.create_goal("alice", {"title":"Assess homelab", "desired_outcome":"bounded report", "success_criteria":{"report":True}})
    project = svc.create_project("alice", {"goal_id":goal["id"], "title":"Security test project", "domain":"security"})
    first = svc.create_task("alice", {"project_id":project["id"], "title":"Review server"})
    second = svc.create_task("alice", {"project_id":project["id"], "title":"Record evidence"})
    svc.add_dependency("alice", second["id"], first["id"])
    with pytest.raises(WorkError, match="cycle"):
        svc.add_dependency("alice", first["id"], second["id"])

def test_run_action_completion_is_idempotent_and_context_is_bounded(db):
    svc = WorkEngine(db)
    goal = svc.create_goal("alice", {"title":"Inventory office"})
    project = svc.create_project("alice", {"goal_id":goal["id"], "title":"Reconciliation", "domain":"inventory"})
    task = svc.create_task("alice", {"project_id":project["id"], "title":"Review device", "status":"ready"})
    run = svc.create_run("alice", {"goal_id":goal["id"], "project_id":project["id"], "task_id":task["id"], "domain":"inventory"})
    action = svc.create_action("alice", run["id"], {"capability_id":"inventory.manage", "action_id":"get", "tool_binding_name":"manage_assets", "normalized_input":{"item_id":"test"}})
    completed = svc.complete_action("alice", action["id"], {"result_reference":"inventory-item://test"})
    assert completed["status"] == "completed"
    assert svc.complete_action("alice", action["id"], {})["replayed"] is True
    context = svc.context("alice", run_id=run["id"])
    assert context["run"]["id"] == run["id"]
    assert context["actions"][0]["status"] == "completed"
    assert len(context["recent_events"]) <= 12

def test_run_lifecycle_and_action_contract_preview_are_durable(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {
        "domain": "homelab", "intent": {"kind": "network_discovery"},
        "plan": [{"step": "discover"}], "assumptions": [{"claim": "private scope"}],
    })
    assert run["lifecycle_state"] == "created"
    preview = svc.preview_action("alice", run["id"], {
        "capability_id": "homelab.manage", "action_id": "execute_network_discovery",
        "target_resources": ["network:192.168.10.0/24"],
        "locks": ["network:192.168.10.0/24"], "approval_required": True,
        "rollback_capability": "none", "verification": ["map_updated"],
    })
    assert preview["execution"] == "preview_only"
    assert svc.get_run("alice", run["id"])["actions"] == []
    transitioned = svc.transition_run("alice", run["id"], "planning", {"current_step": "compile plan"})
    assert transitioned["lifecycle_state"] == "planning"
    persisted = WorkEngine(db).get_run("alice", run["id"])
    assert persisted["plan"] == [{"step": "discover"}]
    assert persisted["events"][-1]["event_type"] == "RunPlanning"

def test_action_contract_fields_persist_with_owner_scoped_run(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    action = svc.create_action("alice", run["id"], {
        "capability_id": "homelab.manage", "action_id": "execute_network_discovery",
        "target_resources": ["network:192.168.10.0/24"], "locks": ["network:private_scope"],
        "risk_level": "high", "idempotency_key": "scan-1",
        "retry_policy": {"max_attempts": 1}, "timeout_seconds": 120,
        "postconditions": ["observations_persisted"],
    })
    assert action["locks"] == ["network:private_scope"]
    assert WorkEngine(db).get_run("alice", run["id"])["actions"][0]["idempotency_key"] == "scan-1"


def test_retry_requires_replay_safe_contract_and_does_not_copy_approval(db):
    svc = WorkEngine(db)
    unsafe_run = svc.create_run("alice", {"domain": "homelab"})
    unsafe = svc.create_action("alice", unsafe_run["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "status": "failed"})
    with pytest.raises(WorkError, match="not safely retryable"):
        svc.retry_action("alice", unsafe["id"])
    run = svc.create_run("alice", {"domain": "homelab"})
    action = svc.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "execute_network_discovery", "status": "failed", "approval_reference": "old-approval", "locks": ["network:private_scope"], "retry_policy": {"max_attempts": 2}})
    retry = svc.retry_action("alice", action["id"])
    assert retry["retry_of_action_id"] == action["id"] and retry["approval_reference"] is None
    assert retry["status"] == "proposed"

def test_resource_locks_prevent_collisions_and_release_on_completion(db):
    svc = WorkEngine(db)
    first_run = svc.create_run("alice", {"domain": "homelab"})
    first = svc.create_action("alice", first_run["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "locks": [{"resource": "service:nginx", "mode": "shared"}]})
    svc.acquire_action_locks("alice", first["id"])
    second_run = svc.create_run("alice", {"domain": "homelab"})
    second = svc.create_action("alice", second_run["id"], {"capability_id": "homelab.manage", "action_id": "execute_service_restart", "locks": ["service:nginx"]})
    with pytest.raises(WorkError, match="lock conflict"):
        svc.acquire_action_locks("alice", second["id"])
    assert svc.lock_conflicts("alice", second["id"])[0]["resource"] == "service:nginx"
    svc.complete_action("alice", first["id"], {})
    assert svc.acquire_action_locks("alice", second["id"])["status"] == "executing"

def test_shared_resource_locks_can_coexist(db):
    svc = WorkEngine(db)
    actions = []
    for _ in range(2):
        run = svc.create_run("alice", {"domain": "homelab"})
        action = svc.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "locks": [{"resource": "service:nginx", "mode": "shared"}]})
        actions.append(action)
    svc.acquire_action_locks("alice", actions[0]["id"])
    assert svc.acquire_action_locks("alice", actions[1]["id"])["status"] == "executing"

def test_terminal_runs_release_locks_and_recovery_expires_abandoned_locks(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    action = svc.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["host:cerberus", "service:nginx"]})
    svc.acquire_action_locks("alice", action["id"])
    assert len(svc.get_run("alice", run["id"])["locks"]) == 2
    svc.set_run_status("alice", run["id"], "cancelled")
    assert all(lock["released_at"] for lock in svc.get_run("alice", run["id"])["locks"])

    abandoned = svc.create_run("alice", {"domain": "homelab"})
    second = svc.create_action("alice", abandoned["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["service:postgres"]})
    svc.acquire_action_locks("alice", second["id"])
    result = svc.recover_locks("alice", max_age_seconds=0)
    assert result["count"] >= 1

def test_epistemic_claims_preserve_provenance_and_valid_record_time(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "network"})
    claim = svc.record_claim("alice", {
        "claim_class": "Observation", "subject_ref": "asset:web-01", "predicate": "ip_address",
        "value": {"address": "192.168.10.20"}, "source": "nmap-result-1", "confidence": 92,
        "observed_at": "2026-08-20T12:00:00", "valid_from": "2026-08-20T12:00:00",
        "valid_until": "2026-08-21T12:00:00", "run_id": run["id"],
        "evidence_references": ["result://nmap-result-1"], "provenance": {"kind": "host_broker"},
    })
    assert claim["claim_class"] == "Observation"
    assert claim["run_id"] == run["id"]
    context = svc.epistemic_context("alice", subject_ref="asset:web-01", at="2026-08-20T18:00:00")
    assert context["claim_count"] == 1
    assert context["current"][0]["evidence_references"] == ["result://nmap-result-1"]
    later = svc.epistemic_context("alice", subject_ref="asset:web-01", at="2026-08-22T00:00:00")
    assert later["claim_count"] == 0
    assert len(later["stale"]) == 1
    with pytest.raises(WorkError, match="claim class"):
        svc.record_claim("alice", {"claim_class": "Guess", "predicate": "x", "source": "user"})


def test_owner_claim_review_preserves_history_and_requires_scoped_replacement(db):
    svc = WorkEngine(db)
    original = svc.record_claim("alice", {"claim_class": "RetrievedClaim", "subject_ref": "osint:case:one", "predicate": "role", "value": "CEO", "source": "source-a"})
    replacement = svc.record_claim("alice", {"claim_class": "UserAssertion", "subject_ref": "osint:case:one", "predicate": "role", "value": "Former CEO", "source": "owner://correction"})
    confirmed = svc.review_claim("alice", original["id"], decision="confirmed", note="Owner reviewed source")
    assert confirmed["status"] == "active"
    assert confirmed["provenance"]["resolution_status"] == "OWNER_CONFIRMED"
    superseded = svc.review_claim("alice", original["id"], decision="superseded", replacement_claim_id=replacement["id"])
    assert superseded["status"] == "superseded"
    assert superseded["provenance"]["review_history"][-1]["replacement_claim_id"] == replacement["id"]
    assert len(svc.list_claims("alice", subject_ref="osint:case:one", include_inactive=True)) == 2
    with pytest.raises(WorkError, match="same scope"):
        other = svc.record_claim("alice", {"claim_class": "Fact", "subject_ref": "osint:case:two", "predicate": "role", "value": "CEO", "source": "source-b"})
        svc.review_claim("alice", replacement["id"], decision="superseded", replacement_claim_id=other["id"])

def test_run_journal_reconstructs_lifecycle_and_checkpoints(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "network"})
    svc.transition_run("alice", run["id"], "planning", {"current_step": "compile"})
    checkpoint = svc.checkpoint_run("alice", run["id"], {"cursor": 2, "note": "plan sealed"})
    svc.transition_run("alice", run["id"], "executing", {"current_step": "scan"})
    svc.record_verification("alice", run["id"], {"passed": True, "evidence": ["result://1"]})
    replay = WorkEngine(db).reconstruct_run("alice", run["id"])
    assert replay["lifecycle_state"] == "executing"
    assert [item["state"] for item in replay["transitions"]] == ["planning", "executing"]
    assert checkpoint["cursor"] == 2
    assert WorkEngine(db).get_run("alice", run["id"])["verification"]["passed"] is True

def test_owner_isolation_and_restart_state(db):
    svc = WorkEngine(db)
    goal = svc.create_goal("alice", {"title":"Private work"})
    run = svc.create_run("alice", {"goal_id":goal["id"], "domain":"security"})
    with pytest.raises(WorkError): svc.context("bob", run_id=run["id"])
    svc.set_run_status("alice", run["id"], "awaiting_approval", {"current_step":"resolve target", "continuation_state":{"cursor":2}})
    # A new service/session observes the persisted awaiting state.
    db.expire_all(); resumed = WorkEngine(db).get_run("alice", run["id"])
    assert resumed["status"] == "awaiting_approval"
    assert resumed["continuation_state"] == {"cursor":2}

def test_awaiting_approval_action_promotes_parent_run(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain":"inventory"})
    svc.create_action("alice", run["id"], {"capability_id":"inventory.manage", "action_id":"update", "status":"awaiting_approval"})
    assert svc.get_run("alice", run["id"])["status"] == "awaiting_approval"

def test_exact_work_approval_binding_and_resume(db):
    svc=WorkEngine(db)
    run=svc.create_run("alice", {"domain":"security"})
    action=svc.create_action("alice", run["id"], {"capability_id":"security.run.plan", "action_id":"plan", "status":"proposed", "normalized_input":{"target":"asset-1"}})
    svc.bind_approval("alice", action["id"], "approval-1", digest=action["sealed_input_digest"])
    with pytest.raises(WorkError, match="bound"):
        svc.resume_approved_action("alice", action["id"], "approval-2")
    resumed=svc.resume_approved_action("alice", action["id"], "approval-1", digest=action["sealed_input_digest"])
    assert resumed["status"] == "approved"
    assert svc.complete_action("alice", action["id"], {})["status"] == "completed"
    assert svc.resume_approved_action("alice", action["id"], "approval-1")["replayed"] is True


def test_approval_resume_restores_parent_run_ready_state(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "network"})
    action = svc.create_action("alice", run["id"], {
        "capability_id": "homelab.manage", "action_id": "execute_network_discovery",
        "normalized_input": {"cidr": "192.168.10.0/24"},
        "target_resources": ["network:private_scope"], "status": "awaiting_approval",
        "approval_reference": "approval-ready-1",
    })
    resumed = svc.resume_approved_action("alice", action["id"], "approval-ready-1", digest=action["sealed_input_digest"])
    assert resumed["status"] == "approved"
    current = svc.get_run("alice", run["id"])
    assert current["status"] == "queued"
    assert current["lifecycle_state"] == "ready"
    assert current["continuation_state"]["pending_action_id"] == action["id"]


def test_life_review_is_deterministic_and_owner_scoped(db):
    svc = WorkEngine(db)
    goal = svc.create_goal("alice", {"title": "Prepare launch", "priority": 5, "status": "active"})
    goal = svc.update_goal("alice", goal["id"], {"status": "active"})
    svc.create_commitment("alice", {"goal_id": goal["id"], "text": "Review checklist", "due_at": (datetime.utcnow() + timedelta(hours=4)).isoformat()})
    review = svc.life_review("alice", horizon_hours=48)
    assert review["focus_goals"][0]["id"] == goal["id"]
    assert len(review["due_soon_commitments"]) == 1
    assert svc.life_review("bob")["focus_goals"] == []


def test_complete_action_persists_structured_result_record(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    action = svc.create_action("alice", run["id"], {
        "capability_id": "homelab.manage", "action_id": "service_status",
        "normalized_input": {"service": "nginx"},
    })
    completed = svc.complete_action("alice", action["id"], {
        "result_reference": "service://nginx/status",
        "result": {
            "result_type": "observation",
            "reference": "service://nginx/status",
            "metadata": {"state": "active"},
            "provenance": {"source": "broker", "tainted": True},
        },
    })
    assert completed["result"]["action_id"] == action["id"]
    assert completed["result"]["metadata_json"] == {"state": "active"}
    assert svc.get_run("alice", run["id"])["results"][0]["reference"] == "service://nginx/status"


def test_terminal_run_rejects_new_actions(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    svc.set_run_status("alice", run["id"], "completed", {
        "lifecycle_state": "succeeded",
        "current_step": "deliverable verified",
    })
    with pytest.raises(WorkError, match="terminal Run cannot accept new actions"):
        svc.create_action("alice", run["id"], {
            "capability_id": "homelab.manage",
            "action_id": "service_status",
        })


def test_add_result_rejects_cross_owner_or_cross_run_action_reference(db):
    svc = WorkEngine(db)
    alice_run = svc.create_run("alice", {"domain": "homelab"})
    bob_run = svc.create_run("bob", {"domain": "homelab"})
    other_alice_run = svc.create_run("alice", {"domain": "homelab"})
    alice_action = svc.create_action("alice", alice_run["id"], {"capability_id": "homelab.manage", "action_id": "service_status"})
    with pytest.raises(WorkError, match="owner-scoped run"):
        svc.add_result("bob", bob_run["id"], {"action_id": alice_action["id"], "reference": "result://cross-owner"})
    with pytest.raises(WorkError, match="owner-scoped run"):
        svc.add_result("alice", other_alice_run["id"], {"action_id": alice_action["id"], "reference": "result://cross-run"})


def test_bound_action_orchestration_uses_structured_result_and_releases_locks(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    action = svc.create_action("alice", run["id"], {
        "capability_id": "homelab.manage", "action_id": "service_status",
        "normalized_input": {"service": "nginx"}, "locks": ["host:lab-1"],
    })
    seen = {}
    completed = svc.execute_bound_action("alice", action["id"], lambda value: seen.update(value) or {
        "result_type": "observation", "reference": "service://nginx/status",
        "metadata": {"state": "active"}, "provenance": {"source": "test-binding"},
    })
    assert seen["id"] == action["id"]
    assert completed["status"] == "completed"
    assert svc.get_run("alice", run["id"])["results"][0]["reference"] == "service://nginx/status"
    assert svc.lock_conflicts("alice", action["id"]) == []


def test_bound_action_failure_is_durable_and_releases_locks(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    action = svc.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["host:lab-1"]})
    with pytest.raises(WorkError, match="binding unavailable"):
        svc.execute_bound_action("alice", action["id"], lambda _value: (_ for _ in ()).throw(WorkError("binding unavailable")))
    stored = svc.get_run("alice", run["id"])["actions"][0]
    assert stored["status"] == "failed"
    assert stored["error"] == "binding unavailable"
    assert svc.lock_conflicts("alice", action["id"]) == []


def test_ambiguous_binding_outcome_retains_locks_and_requires_resolution(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {"domain": "homelab"})
    action = svc.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["host:lab-1"], "retry_policy": {"max_attempts": 2}})
    ambiguous = svc.execute_bound_action("alice", action["id"], lambda _value: (_ for _ in ()).throw(AmbiguousExecution("transport timeout")))
    assert ambiguous["run_lifecycle_state"] == "execution_ambiguous"
    assert ambiguous["locks_retained"] is True
    assert svc.get_run("alice", run["id"])["continuation_state"]["execution_ambiguous"] is True
    with pytest.raises(WorkError, match="independently verified"):
        svc.retry_action("alice", action["id"])
    resolved = svc.resolve_ambiguous_action("alice", action["id"], occurred=False)
    assert resolved["run_lifecycle_state"] == "failed"
    assert svc.lock_conflicts("alice", action["id"]) == []


def test_restart_reconstructs_failed_and_ambiguous_execution_boundaries(db):
    svc = WorkEngine(db)

    failed_run = svc.create_run("alice", {"domain": "homelab"})
    failed_action = svc.create_action(
        "alice", failed_run["id"],
        {"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["host:lab-1"]},
    )
    with pytest.raises(WorkError, match="binding unavailable"):
        svc.execute_bound_action(
            "alice", failed_action["id"],
            lambda _value: (_ for _ in ()).throw(WorkError("binding unavailable")),
        )

    ambiguous_run = svc.create_run("alice", {"domain": "homelab"})
    ambiguous_action = svc.create_action(
        "alice", ambiguous_run["id"],
        {"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["host:lab-2"]},
    )
    svc.execute_bound_action(
        "alice", ambiguous_action["id"],
        lambda _value: (_ for _ in ()).throw(AmbiguousExecution("transport timeout")),
    )

    restarted = WorkEngine(db)
    failed_replay = restarted.reconstruct_run("alice", failed_run["id"])
    ambiguous_replay = restarted.reconstruct_run("alice", ambiguous_run["id"])
    failed_action_state = restarted.get_run("alice", failed_run["id"])["actions"][0]
    ambiguous_run_state = restarted.get_run("alice", ambiguous_run["id"])
    # A binding failure is an Action failure; the parent Run remains
    # reconstructible for an explicit retry or alternative next step.
    assert failed_replay["lifecycle_state"] == "created"
    assert failed_replay["action_events"]
    assert failed_action_state["status"] == "failed"
    assert failed_action_state["error"] == "binding unavailable"
    assert ambiguous_replay["current_projection"] == "execution_ambiguous"
    assert ambiguous_replay["action_events"]
    # The Action is marked failed with an explicit ambiguous error while the
    # parent Run retains the unresolved execution state and its lock.
    assert ambiguous_run_state["actions"][0]["status"] == "failed"
    assert ambiguous_run_state["actions"][0]["error"].startswith("execution_ambiguous:")
    assert ambiguous_run_state["continuation_state"]["execution_ambiguous"] is True
