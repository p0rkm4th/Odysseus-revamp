import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.work_models import WorkAction
from src.run_planner import RunPlanner
from src.work_engine import WorkEngine
from src.world_model import WorldModelService
from src.capability_registry import ActionSpec, CapabilitySpec
from src.execution_nodes import ExecutionNodeService


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


def test_action_execution_requirements_are_projected_and_gate_node_validation(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain":"homelab", "plan":[{"capability_id":"test.capability", "action_id":"diagnose"}]})
    planner = RunPlanner(db)
    capability = CapabilitySpec("test.capability", {"diagnose": ActionSpec(action_id="diagnose", execution_requirements={"platform":"linux", "capability":"diagnostics"})})
    planner._spec = lambda action: (capability, capability.actions.get(str(action.get("action_id") or "")))
    before = planner.validate("alice", run["id"])
    assert any(failure["code"] == "execution_node_unavailable" for failure in before["failures"])
    assert before["preview"]["actions"][0]["contract"]["execution_requirements"]["platform"] == "linux"
    ExecutionNodeService(db).register("alice", {"node_key":"diagnostic-node", "platform":"linux", "capabilities":["diagnostics"], "health":"healthy"})
    after = planner.validate("alice", run["id"])
    assert not any(failure["code"] == "execution_node_unavailable" for failure in after["failures"])


def test_validation_rejects_malformed_input_and_binding_mismatch(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab", "plan": [{"capability_id": "test.capability", "action_id": "mutate", "tool_binding_name": "manage_homelab", "normalized_input": ["not", "an", "object"]}]})
    planner = RunPlanner(db)
    capability = CapabilitySpec("test.capability", {"mutate": ActionSpec(action_id="mutate", executor_key="manage_assets")})
    planner._spec = lambda action: (capability, capability.actions.get(str(action.get("action_id") or "")))
    result = planner.validate("alice", run["id"])
    codes = {failure["code"] for failure in result["failures"]}
    assert {"invalid_action_input", "execution_path_unavailable"} <= codes
    assert result["preview"]["actions"][0]["contract"]["execution_path"]["reason"] == "executor_binding_mismatch"


def test_exact_approval_requires_sealed_input_digest(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab"})
    action = work.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "execute_network_discovery", "approval_reference": "approval-1", "target_resources": ["network:private_scope"]})
    row = db.query(WorkAction).filter_by(id=action["id"]).one()
    row.sealed_input_digest = None
    db.commit()
    result = RunPlanner(db).validate("alice", run["id"])
    assert any(failure["code"] == "approval_digest_missing" for failure in result["failures"])
    assert action["sealed_input_digest"]


def test_next_step_projects_safe_read_continuation_without_execution(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab", "plan": [{
        "capability_id": "homelab.manage", "action_id": "service_status", "target_resources": ["service:nginx"],
    }]})
    result = RunPlanner(db).next_step("alice", run["id"])
    assert result["status"] == "READY"
    assert result["action"]["action_id"] == "service_status"
    assert result["action"]["tool_binding_name"] == "manage_homelab"
    assert result["safe_auto_continue"] is True
    assert result["authority_required"] is False
    assert db.query(WorkAction).count() == 0


def test_next_step_requires_authority_for_consequential_action(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "network", "plan": [{
        "capability_id": "homelab.manage", "action_id": "execute_network_discovery",
        "target_resources": ["network:private_scope"],
    }]})
    result = RunPlanner(db).next_step("alice", run["id"])
    assert result["status"] == "WAITING_APPROVAL"
    assert result["authority_required"] is True
    assert result["safe_auto_continue"] is False


def test_next_step_auto_continues_sealed_approved_action(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "network"})
    action = work.create_action("alice", run["id"], {
        "capability_id": "homelab.manage", "action_id": "execute_network_discovery",
        "normalized_input": {"cidr": "192.168.10.0/24"},
        "target_resources": ["network:private_scope"], "status": "awaiting_approval",
        "approval_reference": "approval-discovery-1",
    })
    resumed = work.resume_approved_action("alice", action["id"], "approval-discovery-1", digest=action["sealed_input_digest"])
    assert resumed["status"] == "approved"
    next_step = RunPlanner(db).next_step("alice", run["id"])
    assert next_step["status"] == "READY"
    assert next_step["safe_auto_continue"] is True
    assert next_step["authority_required"] is False
    assert work.get_run("alice", run["id"])["lifecycle_state"] == "ready"


def test_approved_action_without_exact_seal_does_not_auto_continue(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "network"})
    action = work.create_action("alice", run["id"], {
        "capability_id": "homelab.manage", "action_id": "execute_network_discovery",
        "normalized_input": {"cidr": "192.168.10.0/24"},
        "target_resources": ["network:private_scope"], "status": "approved",
    })
    next_step = RunPlanner(db).next_step("alice", run["id"])
    assert next_step["status"] == "READY"
    assert next_step["safe_auto_continue"] is False


def test_next_step_skips_completed_action_and_selects_next_sequence(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab", "plan": []})
    first = work.create_action("alice", run["id"], {"sequence": 1, "capability_id": "homelab.manage", "action_id": "service_status", "target_resources": ["service:nginx"]})
    work.complete_action("alice", first["id"], {"result": {"service": "nginx", "status": "active"}})
    second = work.create_action("alice", run["id"], {"sequence": 2, "capability_id": "homelab.manage", "action_id": "service_status", "target_resources": ["service:postgres"]})
    result = RunPlanner(db).next_step("alice", run["id"])
    assert result["status"] == "READY"
    assert result["action"]["id"] == second["id"]
    assert result["action"]["sequence"] == 2


def test_next_step_fails_closed_for_ambiguous_run(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "network", "lifecycle_state": "execution_ambiguous", "plan": [{
        "capability_id": "homelab.manage", "action_id": "service_status",
    }]})
    result = RunPlanner(db).next_step("alice", run["id"])
    assert result["status"] == "BLOCKED"
    assert result["action"] is None
    assert result["safe_auto_continue"] is False


def test_next_step_is_owner_scoped(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab", "plan": [{
        "capability_id": "homelab.manage", "action_id": "service_status",
    }]})
    with pytest.raises(Exception):
        RunPlanner(db).next_step("bob", run["id"])


def test_focused_execution_validation_still_rejects_unknown_future_action(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {
        "domain": "homelab",
        "plan": [
            {"sequence": 1, "capability_id": "homelab.manage", "action_id": "service_status"},
            {"sequence": 2, "capability_id": "homelab.manage", "action_id": "not_registered"},
        ],
    })
    current = work.create_action("alice", run["id"], {
        "sequence": 1,
        "capability_id": "homelab.manage",
        "action_id": "service_status",
    })
    validation = RunPlanner(db).validate("alice", run["id"], focus_sequence=current["sequence"])
    assert validation["valid"] is False
    assert any(item["code"] == "unknown_action_spec" and item["sequence"] == 2 for item in validation["failures"])
