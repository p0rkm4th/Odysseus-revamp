import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.work_models import WorkAction, WorkResult, WorkRun
import src.agent_work_bridge as bridge


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
            {"data": {"hosts": [{"ip": "192.168.10.1", "inference": {"label": "router", "confidence": 0.8}}]}},
        )
        assert completed["status"] == "completed"
        with session_factory() as db:
            result = db.query(WorkResult).filter_by(action_id=action_id).one()
            assert result.owner == "alice"
            assert result.run_id == run_id
            assert result.provenance["source"] == "canonical ToolBinding"
            assert result.domain_reference["hosts"][0]["inference"]["label"] == "router"
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
