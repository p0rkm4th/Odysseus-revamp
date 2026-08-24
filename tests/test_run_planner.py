import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.run_planner import RunPlanner
from src.work_engine import WorkEngine
from src.world_model import WorldModelService
from src.capability_registry import ActionSpec, CapabilitySpec


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
    assert preview["targets"] == ["network:private_scope"]
    assert preview["target_entities"] == preview["targets"]
    assert preview["effect_classes"] == ["admin_change"]
    assert preview["capability_health"] == [{"capability_id": "homelab.manage", "status": "available", "actions": ["execute_network_discovery"]}]
    assert preview["reversibility"][0]["irreversible"] is False
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
    assert result["preview"]["capability_health"][-1]["status"] == "unavailable"


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


def test_preview_projects_evidence_backed_blast_radius(db):
    work = WorkEngine(db)
    WorldModelService(db).create_relationship("alice", {"source_ref":"host:cerberus", "relation":"RUNS_ON", "target_ref":"service:jellyfin", "status":"observed", "source":"cmdb-observation", "confidence_class":"high", "observation_kind":"observed", "evidence_references":["observation://1"]})
    WorldModelService(db).create_relationship("alice", {"source_ref":"service:jellyfin", "relation":"DEPENDS_ON", "target_ref":"service:postgres", "status":"proposed", "source":"operator-review", "confidence_class":"medium", "observation_kind":"inferred"})
    run = work.create_run("alice", {"domain":"homelab", "plan":[{"capability_id":"homelab.manage", "action_id":"service_status", "target_resources":["host:cerberus"]}]})
    preview = RunPlanner(db).compile("alice", run["id"])
    assert preview["blast_radius"][0]["focus"] == "host:cerberus"
    assert preview["blast_radius"][0]["confirmed"][0]["entity"] == "service:jellyfin"
    assert preview["blast_radius"][0]["likely"][0]["entity"] == "service:postgres"


def test_validation_reports_current_resource_lock_conflict(db):
    work = WorkEngine(db)
    first_run = work.create_run("alice", {"domain": "homelab"})
    first = work.create_action("alice", first_run["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["service:nginx"]})
    work.acquire_action_locks("alice", first["id"])
    second_run = work.create_run("alice", {"domain": "homelab", "plan": [{"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["service:nginx"]}]})
    second = work.create_action("alice", second_run["id"], {"capability_id": "homelab.manage", "action_id": "service_status", "locks": ["service:nginx"]})
    result = RunPlanner(db).validate("alice", second_run["id"])
    assert any(failure["code"] == "lock_conflict" for failure in result["failures"])


def test_declared_precheck_requires_registered_evidence_and_projects_it(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab", "plan": [{"capability_id": "test.capability", "action_id": "mutate"}]})
    planner = RunPlanner(db)
    capability = CapabilitySpec("test.capability", {"mutate": ActionSpec(action_id="mutate", precheck_actions=("status",)), "status": ActionSpec(action_id="status")})
    planner._spec = lambda action: (capability, capability.actions.get(str(action.get("action_id") or "")))
    before = planner.validate("alice", run["id"])
    assert any(failure["code"] == "precheck_required" for failure in before["failures"])
    assert before["preview"]["prechecks"][0]["required"][0]["satisfied"] is False
    work.record_precheck("alice", run["id"], {"sequence": 1, "action_id": "status", "status": "passed", "evidence": {"source": "test-probe"}})
    after = planner.validate("alice", run["id"])
    assert not any(failure["code"] == "precheck_required" for failure in after["failures"])
    assert after["preview"]["prechecks"][0]["required"][0]["satisfied"] is True


def test_mission_allowed_capabilities_are_enforced_by_run_validation(db):
    work = WorkEngine(db)
    mission = work.create_goal("alice", {"title":"Scoped mission", "constraints":{"operating_mode":"mission", "allowed_capabilities":["homelab.manage"]}})
    run = work.create_run("alice", {"goal_id":mission["id"], "domain":"homelab", "plan":[{"capability_id":"inventory.manage", "action_id":"get"}]})
    result = RunPlanner(db).validate("alice", run["id"])
    assert any(failure["code"] == "mission_capability_restricted" for failure in result["failures"])
