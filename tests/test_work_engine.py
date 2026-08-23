from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.work_models import WorkAction, WorkGoal, WorkProject, WorkRun, WorkTask
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
