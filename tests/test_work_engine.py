from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.work_models import WorkAction, WorkCommitment, WorkGoal, WorkProject, WorkRun, WorkTask
from src.work_engine import WorkEngine, WorkError

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


def test_life_review_is_deterministic_and_owner_scoped(db):
    svc = WorkEngine(db)
    goal = svc.create_goal("alice", {"title": "Prepare launch", "priority": 5, "status": "active"})
    goal = svc.update_goal("alice", goal["id"], {"status": "active"})
    svc.create_commitment("alice", {"goal_id": goal["id"], "text": "Review checklist", "due_at": (datetime.utcnow() + timedelta(hours=4)).isoformat()})
    review = svc.life_review("alice", horizon_hours=48)
    assert review["focus_goals"][0]["id"] == goal["id"]
    assert len(review["due_soon_commitments"]) == 1
    assert svc.life_review("bob")["focus_goals"] == []
