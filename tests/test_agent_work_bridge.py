import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.work_models import EpistemicClaim, WorkAction, WorkResult, WorkRun
import src.agent_work_bridge as bridge
from src.work_engine import WorkEngine


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def test_agent_network_intent_creates_one_owner_session_run_and_reuses_it(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-1",
            "do a deep dive network discovery scan and list all hosts",
            intent={"domains": ["network_ops"]},
            model_name="qwen3:8b",
        )
        continued = bridge.ensure_agent_run(
            "alice", "chat-1", "Continue",
            intent={"domains": []}, continuation=True,
        )
        assert run_id and continued == run_id

        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            assert run.domain == "network_ops"
            assert run.status == "queued"
            assert run.lifecycle_state == "ready"
            assert run.intent["source"] == "chat_agent"
            assert run.model_name == "qwen3:8b"
            assert db.query(WorkRun).filter_by(owner="alice", session_id="chat-1").count() == 1
            assert run.completion_criteria["completion_mode"] == "verified_run_terminal_state"
    finally:
        engine.dispose()


def test_completion_assessment_is_durable_and_does_not_use_model_prose(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-completion", "deep network discovery",
            intent={"domains": ["network_ops"]},
            completion_criteria={
                "objective": "deep network discovery",
                "deliverable": "verified host inventory",
                "required_stages": ["discovery", "report"],
            },
        )
        in_progress = bridge.assess_agent_run("alice", run_id)
        assert in_progress["status"] == "IN_PROGRESS"
        assert in_progress["deliverable"] == "verified host inventory"

        with session_factory() as db:
            WorkEngine(db).set_run_status(
                "alice", run_id, "completed",
                {"lifecycle_state": "succeeded", "current_step": "verified host inventory"},
            )
        complete = bridge.assess_agent_run("alice", run_id)
        assert complete["status"] == "COMPLETE"
        assert complete["lifecycle_state"] == "succeeded"
        assert complete["completion_criteria"]["required_stages"] == ["discovery", "report"]
    finally:
        engine.dispose()


def test_agent_binding_projects_network_action_approval_and_result(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-2", "scan my private network",
            intent={"domains": ["network_ops"]},
        )
        action_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            json.dumps({"action": "execute_network_discovery", "cidr": "192.168.10.0/24"}),
        )
        assert action_id
        with session_factory() as db:
            action = db.query(WorkAction).filter_by(id=action_id).one()
            assert action.capability_id == "homelab.manage"
            assert action.action_id == "execute_network_discovery"
            assert action.tool_binding_name == "manage_homelab"
            assert action.status == "proposed"
            assert action.sealed_input_digest

        approval_id = "approval-chat-2"
        bound = bridge.bind_approval("alice", action_id, approval_id)
        assert bound["status"] == "awaiting_approval"
        resumed = bridge.resume_approval("alice", action_id, approval_id)
        assert resumed["status"] == "approved"
        completed = bridge.record_result(
            "alice", action_id,
            {"data": {
                "hosts": [{"ip": "192.168.10.1", "inference": {"label": "router", "confidence": 0.8}}],
                "observations_recorded": True,
                "network_map_reconciled": True,
                "observation_count": 1,
            }},
        )
        assert completed["status"] == "completed"
        assert completed["run_lifecycle_state"] == "verifying"
        verification = bridge.verify_bound_action("alice", action_id)
        assert verification["verified"] is True
        assert verification["run_lifecycle_state"] == "succeeded"
        with session_factory() as db:
            result = db.query(WorkResult).filter_by(action_id=action_id).one()
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            assert result.owner == "alice"
            assert result.run_id == run_id
            assert run.lifecycle_state == "succeeded"
            assert result.provenance["source"] == "canonical ToolBinding"
            assert result.domain_reference["hosts"][0]["inference"]["label"] == "router"
    finally:
        engine.dispose()


def test_service_enumeration_inherits_exact_discovery_targets_and_verifies_projection(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-deep-network", "deep network discovery", intent={"domains": ["network_ops"]},
        )
        discovery_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "execute_network_discovery", "cidr": "192.168.10.0/24"},
        )
        bridge.bind_approval("alice", discovery_id, "approval-discovery-deep")
        bridge.resume_approval("alice", discovery_id, "approval-discovery-deep")
        bridge.record_result(
            "alice", discovery_id,
            {"data": {
                "asset_draft_candidates": [
                    {"ip_addresses": ["192.168.10.4"]},
                    {"ip_addresses": ["192.168.10.5"]},
                ],
                "observations_recorded": True,
                "network_map_reconciled": True,
                "observation_count": 2,
            }},
        )
        bridge.verify_bound_action("alice", discovery_id)

        plan_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "plan_network_service_enumeration"},
        )
        with session_factory() as db:
            plan = db.query(WorkAction).filter_by(id=plan_id).one()
            assert plan.normalized_input["targets"] == ["192.168.10.4", "192.168.10.5"]
        bridge.record_result("alice", plan_id, {"data": {"operation_digest": "s" * 64}})

        action_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "execute_network_service_enumeration", "plan_digest": "s" * 64},
        )
        with session_factory() as db:
            action = db.query(WorkAction).filter_by(id=action_id).one()
            assert action.normalized_input["targets"] == ["192.168.10.4", "192.168.10.5"]
            assert action.verification == ["service_observations_persisted", "network_map_reconciled"]
        bridge.bind_approval("alice", action_id, "approval-service-enum")
        bridge.resume_approval("alice", action_id, "approval-service-enum")
        bridge.record_result(
            "alice", action_id,
            {"data": {
                "service_observations": [{"ip": "192.168.10.4", "services": []}],
                "observations_recorded": True,
                "network_map_reconciled": True,
                "observation_count": 1,
            }},
        )
        verification = bridge.verify_bound_action("alice", action_id)
        assert verification["verified"] is True
        assert verification["run_lifecycle_state"] == "succeeded"
    finally:
        engine.dispose()


def test_agent_binding_is_owner_scoped(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run("alice", "chat-3", "scan network", intent={"domains": ["network_ops"]})
        assert bridge.prepare_action("bob", run_id, "manage_homelab", {"action": "discovery_status"}) is None
        with session_factory() as db:
            assert db.query(WorkAction).count() == 0
    finally:
        engine.dispose()


def test_agent_binding_preserves_ambiguous_post_action_projection_failure(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run("alice", "chat-4", "scan network", intent={"domains": ["network_ops"]})
        action_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "execute_network_discovery", "cidr": "192.168.10.0/24"},
        )
        result = bridge.record_result(
            "alice", action_id,
            {
                "error": "network discovery completed but CMDB observation persistence failed",
                "execution_ambiguous": True,
                "persistence_error": "CMDB unavailable",
                "exit_code": 1,
            },
        )
        assert result["run_lifecycle_state"] == "execution_ambiguous"
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            action = db.query(WorkAction).filter_by(id=action_id).one()
            assert run.lifecycle_state == "execution_ambiguous"
            assert run.continuation_state["execution_ambiguous"] is True
            assert action.status == "failed"
            assert action.error.startswith("execution_ambiguous:")
            assert db.query(WorkResult).filter_by(action_id=action_id).count() == 0
    finally:
        engine.dispose()


def test_service_restart_requires_plan_records_invalidation_and_verifies(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-service-1", "restart the synthetic service",
            intent={"domains": ["homelab"]},
        )
        assert bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "execute_service_restart", "service": "nginx"},
        ) is None
        with session_factory() as db:
            waiting = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            assert waiting.lifecycle_state == "waiting_input"
            WorkEngine(db).record_claim(
                "alice", {"claim_class": "Observation", "subject_ref": "service:nginx", "predicate": "status", "value": "active", "source": "probe"},
            )
            WorkEngine(db).record_claim(
                "alice", {"claim_class": "Observation", "subject_ref": "service:nginx", "predicate": "uptime", "value": "10m", "source": "probe"},
            )

        plan_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "plan_service_restart", "service": "nginx"},
        )
        assert plan_id
        bridge.record_result(
            "alice", plan_id,
            {"data": {"success": True, "operation_digest": "d" * 64, "current_state": "active"}},
        )
        action_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "execute_service_restart", "service": "nginx", "plan_digest": "d" * 64},
        )
        assert action_id
        with session_factory() as db:
            action = db.query(WorkAction).filter_by(id=action_id).one()
            assert "service:nginx" in action.target_resources
            assert "service:nginx" in action.locks
            assert action.verification == ["service_active"]

        bridge.bind_approval("alice", action_id, "approval-service-1")
        bridge.resume_approval("alice", action_id, "approval-service-1")
        completed = bridge.record_result(
            "alice", action_id,
            {"data": {"success": True, "verification_exit_code": 0, "verification_output": "active"}},
        )
        assert completed["run_lifecycle_state"] == "verifying"
        verified = bridge.verify_bound_action("alice", action_id)
        assert verified["verified"] is True
        assert verified["run_lifecycle_state"] == "succeeded"
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            assert run.lifecycle_state == "succeeded"
            claims = db.query(EpistemicClaim).filter_by(owner="alice").all()
            assert claims and all((claim.provenance or {}).get("state") == "stale" for claim in claims)
    finally:
        engine.dispose()


def test_service_restart_verification_failure_is_not_success(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run("alice", "chat-service-2", "restart the synthetic service", intent={"domains": ["homelab"]})
        plan_id = bridge.prepare_action("alice", run_id, "manage_homelab", {"action": "plan_service_restart", "service": "nginx"})
        bridge.record_result("alice", plan_id, {"data": {"success": True, "operation_digest": "e" * 64}})
        action_id = bridge.prepare_action("alice", run_id, "manage_homelab", {"action": "execute_service_restart", "service": "nginx"})
        bridge.bind_approval("alice", action_id, "approval-service-2")
        bridge.resume_approval("alice", action_id, "approval-service-2")
        bridge.record_result(
            "alice", action_id,
            {"data": {"success": True, "verification_exit_code": 1, "verification_output": "inactive"}},
        )
        verified = bridge.verify_bound_action("alice", action_id)
        assert verified["verified"] is False
        assert verified["run_lifecycle_state"] == "failed"
    finally:
        engine.dispose()


def test_diagnostic_install_requires_plan_locks_package_manager_and_verifies(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run("alice", "chat-install-1", "install the network discovery prerequisite", intent={"domains": ["homelab"]})
        assert bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "execute_diagnostic_install", "capability": "network_discovery", "packages": ["nmap"]},
        ) is None
        with session_factory() as db:
            WorkEngine(db).record_claim(
                "alice", {"claim_class": "Observation", "subject_ref": "capability:network_discovery", "predicate": "health", "value": "missing", "source": "setup"},
            )
        plan_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "plan_diagnostic_install", "capability": "network_discovery"},
        )
        bridge.record_result("alice", plan_id, {"data": {"success": True, "operation_digest": "f" * 64}})
        action_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "execute_diagnostic_install", "capability": "network_discovery", "packages": ["nmap"]},
        )
        assert action_id
        with session_factory() as db:
            action = db.query(WorkAction).filter_by(id=action_id).one()
            assert "host:package_manager" in action.locks
            assert "capability:network_discovery" in action.target_resources
            assert action.verification == ["prerequisites_verified"]
        bridge.bind_approval("alice", action_id, "approval-install-1")
        bridge.resume_approval("alice", action_id, "approval-install-1")
        completed = bridge.record_result(
            "alice", action_id,
            {"data": {"verified_prerequisites": True, "broker_result": {"verification": {"ok": True}}}},
        )
        assert completed["run_lifecycle_state"] == "verifying"
        verified = bridge.verify_bound_action("alice", action_id)
        assert verified["verified"] is True
        assert verified["run_lifecycle_state"] == "succeeded"
        with session_factory() as db:
            claim = db.query(EpistemicClaim).filter_by(owner="alice").one()
            assert (claim.provenance or {}).get("state") == "stale"
    finally:
        engine.dispose()
