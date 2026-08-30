import json

import pytest
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


def test_completed_asset_result_projects_ordered_refs_for_next_turn(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-assets", "What machines do I have?",
            intent={"domains": ["asset_inventory"], "domain_concept": "TECHNICAL_ASSET", "operation_class": "READ"},
            completion_criteria={"completion_mode": "single_verified_read", "objective": "asset read"},
        )
        action_id = bridge.prepare_action("alice", run_id, "manage_assets", {"action": "list"})
        bridge.record_result("alice", action_id, {"data": {"status": "SUCCESS", "assets": [
            {"id": "asset:first"}, {"id": "asset:second"},
        ]}})
        context = bridge.recent_session_reference_context("alice", "chat-assets")
        assert [item["ref"] for item in context["ordered_entities"]] == ["asset:first", "asset:second"]
        assert [item["ref"] for item in context["eligible_entities"]] == ["asset:first", "asset:second"]
        assert [item["ref"] for item in context["entities"]] == ["asset:first", "asset:second"]
    finally:
        engine.dispose()


def test_completed_household_item_result_projects_reference_for_quantity_followup(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-household-ref", "Add 4 cans of Chickpeas.",
            intent={"domains": ["household"], "domain_concept": "HOUSEHOLD_ITEM", "operation_class": "CREATE"},
        )
        action_id = bridge.prepare_action(
            "alice", run_id, "manage_assets",
            {"action": "add_item", "name": "Chickpeas", "initial_quantity": 4},
        )
        bridge.record_result("alice", action_id, {"data": {"status": "VERIFIED", "item": {"id": "item:chickpeas"}}})
        context = bridge.recent_session_reference_context("alice", "chat-household-ref")
        assert context["ordered_entities"] == [{"ref": "item:chickpeas", "concept": "HOUSEHOLD_ITEM"}]
    finally:
        engine.dispose()


def test_consumption_action_receives_durable_idempotency_key(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-household", "Use one tomato",
            intent={"domains": ["household"], "domain_concept": "HOUSEHOLD_ITEM", "operation_class": "EXECUTE"},
        )
        action_id = bridge.prepare_action(
            "alice", run_id, "manage_assets",
            {"action": "consume_stock", "item_id": "item:tomato", "quantity": 1, "unit": "count"},
        )
        assert action_id
        with session_factory() as db:
            action = db.query(WorkAction).filter_by(id=action_id).one()
            key = action.normalized_input["idempotency_key"]
            assert key == action.idempotency_key
            assert key == action_id
            assert len(key) <= 255
    finally:
        engine.dispose()


def test_completed_recipe_result_projects_ordered_refs_for_next_turn(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-recipes", "What recipes do I have?",
            intent={"domains": ["recipes"], "domain_concept": "RECIPE", "operation_class": "READ"},
            completion_criteria={"completion_mode": "single_verified_read", "objective": "recipe read"},
        )
        action_id = bridge.prepare_action("alice", run_id, "read_recipes", {"action": "list"})
        bridge.record_result("alice", action_id, {"data": {"status": "SUCCESS", "recipes": [
            {"id": "recipe:first"}, {"id": "recipe:second"},
        ]}})
        context = bridge.recent_session_reference_context("alice", "chat-recipes")
        assert [item["ref"] for item in context["ordered_entities"]] == [
            "recipe:first", "recipe:second",
        ]
        assert all(item["concept"] == "RECIPE" for item in context["ordered_entities"])
    finally:
        engine.dispose()


def test_foreground_recipe_tool_event_projects_refs_without_work_result(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        _active, session, _entities = bridge.reference_context_for_turn(
            "alice", "chat-foreground-recipes", None,
            structured_reference=True,
            history=[{"metadata": {"tool_events": [{
                "tool": "read_recipes",
                "output": json.dumps({"recipes": [{"id": "recipe:first"}, {"id": "recipe:second"}]}),
            }]}}],
        )
        assert [item["ref"] for item in session["ordered_entities"]] == [
            "recipe:first", "recipe:second",
        ]
    finally:
        engine.dispose()


def test_new_referenced_objective_does_not_reuse_terminal_run(monkeypatch):
    """A completed read's references survive, but its Run is not appendable."""
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        first = bridge.ensure_agent_run(
            "alice", "chat-terminal-reference", "What machines do I have?",
            intent={"domains": ["asset_inventory"], "domain_concept": "TECHNICAL_ASSET", "operation_class": "READ"},
        )
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=first, owner="alice").one()
            run.status = "completed"
            run.lifecycle_state = "succeeded"
            db.commit()

        second = bridge.ensure_agent_run(
            "alice", "chat-terminal-reference", "Tell me about the first one",
            intent={"domains": ["asset_inventory"], "domain_concept": "TECHNICAL_ASSET", "operation_class": "READ"},
            reference_context={"ordered_entities": [{"ref": "asset:first"}]},
        )
        assert second and second != first
        with session_factory() as db:
            runs = db.query(WorkRun).filter_by(owner="alice", session_id="chat-terminal-reference").all()
            assert len(runs) == 2
            assert db.query(WorkRun).filter_by(id=second).one().lifecycle_state == "ready"
    finally:
        engine.dispose()


def test_latest_canonical_result_owns_ordinal_reference_order(monkeypatch):
    """Older results must not shift ordinals for the current result."""
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-ordinal-refresh", "What machines do I have?",
            intent={"domains": ["asset_inventory"]},
        )
        with session_factory() as db:
            db.add_all([
                WorkResult(
                    id="result-old", owner="alice", run_id=run_id,
                    result_type="read", reference="agent-tool://old",
                    domain_reference={"canonical_refs": [
                        {"ref": "asset:stale", "concept": "TECHNICAL_ASSET"},
                    ]},
                ),
                WorkResult(
                    id="result-new", owner="alice", run_id=run_id,
                    result_type="read", reference="agent-tool://new",
                    domain_reference={"canonical_refs": [
                        {"ref": "asset:current-first", "concept": "TECHNICAL_ASSET"},
                        {"ref": "asset:current-second", "concept": "TECHNICAL_ASSET"},
                    ]},
                ),
            ])
            db.commit()
        context = bridge.recent_session_reference_context("alice", "chat-ordinal-refresh")
        assert [item["ref"] for item in context["ordered_entities"]] == [
            "asset:current-first", "asset:current-second",
        ]
    finally:
        engine.dispose()


def test_model_swap_preserves_run_and_records_owner_scoped_history(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-model-swap", "deep network discovery",
            model_name="qwen3:8b", model_endpoint="http://ollama/v1",
            intent={"domains": ["network_ops"]},
        )
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            run.plan = [{"sequence": 1, "capability_id": "homelab.manage", "action_id": "service_status"}]
            db.commit()
        assert bridge.ensure_agent_run(
            "alice", "chat-model-swap", "continue", continuation=True,
            model_name="gpt-5.6-luna", model_endpoint="https://luna.example/v1",
            intent={"domains": []},
        ) == run_id
        assert bridge.ensure_agent_run(
            "alice", "chat-model-swap", "continue", continuation=True,
            model_name="gpt-5.6-sol", model_endpoint="https://sol.example/v1",
            intent={"domains": []},
        ) == run_id
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            assert run.model_name == "gpt-5.6-sol"
            assert run.plan[0]["action_id"] == "service_status"
            history = run.continuation_state["model_history"]
            assert [item["model_name"] for item in history] == [
                "qwen3:8b", "gpt-5.6-luna", "gpt-5.6-sol",
            ]
            assert db.query(WorkRun).filter_by(owner="bob", session_id="chat-model-swap").count() == 0
    finally:
        engine.dispose()


def test_observed_fallback_model_updates_durable_run_provenance(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-observed-provider", "show my assets",
            model_name="qwen3:8b", model_endpoint="http://ollama/v1",
            intent={"domains": ["asset_inventory"], "domain_concept": "TECHNICAL_ASSET", "operation_class": "READ"},
        )
        observed = bridge.record_agent_model_observation(
            "alice", run_id,
            model_name="gpt-5.6-luna", model_endpoint="https://luna.example/v1",
        )
        assert observed["changed"] is True
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            assert run.model_name == "gpt-5.6-luna"
            assert run.model_endpoint == "https://luna.example/v1"
            assert [item["role"] for item in run.continuation_state["model_history"]] == [
                "initial", "observed",
            ]
            assert db.query(WorkRun).filter_by(owner="bob", id=run_id).one_or_none() is None
        assert bridge.record_agent_model_observation(
            "bob", run_id, model_name="gpt-5.6-sol", model_endpoint="https://sol.example/v1",
        ) is None
    finally:
        engine.dispose()


def test_continuation_projection_includes_canonical_next_step_without_materializing_action(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-next-step", "check homelab service status",
            intent={"domains": ["homelab"], "domain_concept": "SERVICE", "operation_class": "READ"},
        )
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            run.plan = [{
                "sequence": 1,
                "capability_id": "homelab.manage",
                "action_id": "service_status",
                "target_resources": ["service:nginx"],
            }]
            db.commit()
        projection = bridge.continuation_run_projection("alice", run_id)
        assert projection["next_step"]["status"] == "READY"
        assert projection["next_step"]["safe_auto_continue"] is True
        assert projection["next_step"]["action"]["action_id"] == "service_status"
        with session_factory() as db:
            assert db.query(WorkAction).filter_by(run_id=run_id).count() == 0
    finally:
        engine.dispose()


def test_safe_auto_continuation_projects_only_available_read_action(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-auto-read", "check homelab service status",
            intent={"domains": ["homelab"], "domain_concept": "SERVICE", "operation_class": "READ"},
        )
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            run.plan = [{
                "sequence": 1,
                "capability_id": "homelab.manage",
                "action_id": "service_status",
                "target_resources": ["service:nginx"],
            }]
            db.commit()

        projected = bridge.safe_auto_continuation(
            "alice", run_id, allowed_tools={"manage_homelab"}, disabled_tools=set(),
        )
        assert projected["tool"] == "manage_homelab"
        assert projected["action_id"] == "service_status"
        assert json.loads(projected["content"]) == {
            "_hades_target_resources": ["service:nginx"],
            "action": "service_status",
        }
        assert bridge.safe_auto_continuation(
            "alice", run_id, allowed_tools=set(), disabled_tools=set(),
        ) is None
        assert bridge.safe_auto_continuation(
            "alice", run_id, allowed_tools={"manage_homelab"}, disabled_tools={"manage_homelab"},
        ) is None
        with session_factory() as db:
            assert db.query(WorkAction).filter_by(run_id=run_id).count() == 0
    finally:
        engine.dispose()


def test_safe_auto_continuation_refuses_consequential_or_ambiguous_steps(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-auto-write", "discover network",
            intent={"domains": ["network_ops"]},
        )
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            run.plan = [{
                "sequence": 1,
                "capability_id": "homelab.manage",
                "action_id": "execute_network_discovery",
                "target_resources": ["network:private_scope"],
            }]
            db.commit()
        assert bridge.safe_auto_continuation(
            "alice", run_id, allowed_tools={"manage_homelab"}, disabled_tools=set(),
        ) is None
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            run.lifecycle_state = "execution_ambiguous"
            db.commit()
        assert bridge.safe_auto_continuation(
            "alice", run_id, allowed_tools={"manage_homelab"}, disabled_tools=set(),
        ) is None
    finally:
        engine.dispose()


def test_safe_auto_continuation_advances_into_unmaterialized_declared_step(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-auto-chain", "check both services",
            intent={"domains": ["homelab"]},
        )
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            run.plan = [
                {"sequence": 1, "capability_id": "homelab.manage", "action_id": "service_status", "target_resources": ["service:nginx"]},
                {"sequence": 2, "capability_id": "homelab.manage", "action_id": "service_status", "target_resources": ["service:postgres"]},
            ]
            db.commit()

        first_action = bridge.prepare_action("alice", run_id, "manage_homelab", {"action": "service_status"})
        assert first_action
        bridge.record_result("alice", first_action, {"data": {"status": "active"}})
        projected = bridge.safe_auto_continuation(
            "alice", run_id, allowed_tools={"manage_homelab"}, disabled_tools=set(),
        )
        assert projected["action_id"] == "service_status"
        assert projected["target_resources"] == ["service:postgres"]
        second_action = bridge.prepare_action("alice", run_id, projected["tool"], projected["content"])
        assert second_action
        with session_factory() as db:
            assert db.query(WorkAction).filter_by(run_id=run_id).count() == 2
            row = db.query(WorkAction).filter_by(id=second_action).one()
            assert row.target_resources == ["service:postgres"]
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


def test_canonical_read_is_a_terminal_durable_run_result(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-memory", "What do you remember about me?",
            intent={
                "domains": ["memory"],
                "domain_concept": "MEMORY",
                "operation_class": "READ",
            },
        )
        action_id = bridge.prepare_action(
            "alice", run_id, "read_memory",
            {"action": "summarize_owner_memory"},
        )
        assert action_id
        completed = bridge.record_result(
            "alice", action_id,
            {"success": True, "data": {"status": "SUCCESS_EMPTY", "records": []}},
        )
        assert completed["status"] == "completed"
        assert completed["read_completion"]["lifecycle_state"] == "succeeded"
        assessment = bridge.assess_agent_run("alice", run_id)
        assert assessment["status"] == "COMPLETE"
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            assert run.domain == "memory"
            assert run.result_summary["result_status"] == "SUCCESS_EMPTY"
            assert db.query(WorkResult).filter_by(run_id=run_id, owner="alice").count() == 1
            assert run.continuation_state["phase"] == "COMPLETE"
    finally:
        engine.dispose()


def test_canonical_read_unavailable_is_not_recorded_as_success(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-memory-unavailable", "What do you remember about me?",
            intent={"domains": ["memory"], "domain_concept": "MEMORY", "operation_class": "READ"},
        )
        action_id = bridge.prepare_action("alice", run_id, "read_memory", {"action": "summarize_owner_memory"})
        completed = bridge.record_result(
            "alice", action_id,
            {"success": True, "data": {"status": "UNAVAILABLE", "reason": "memory provider offline", "records": []}},
        )
        assert completed["read_completion"]["status"] == "failed"
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            result = db.query(WorkResult).filter_by(run_id=run_id, owner="alice").one()
            assert run.lifecycle_state == "failed"
            assert run.result_summary is None or run.result_summary.get("result_status") != "SUCCESS_WITH_DATA"
            assert result.domain_reference["status"] == "UNAVAILABLE"
    finally:
        engine.dispose()


def test_work_engine_direct_read_completion_preserves_failure_status():
    engine, session_factory = _session_factory()
    try:
        with session_factory() as db:
            work = WorkEngine(db)
            run = work.create_run("alice", {
                "domain": "memory",
                "completion_criteria": {"completion_mode": "single_verified_read", "deliverable": "memory"},
            })
            action = work.create_action("alice", run["id"], {
                "capability_id": "memory.read", "action_id": "summarize_owner_memory",
                "effect_class": "read_private", "status": "proposed",
            })
            work.complete_action("alice", action["id"], {"result": {"domain_reference": {"status": "UNAVAILABLE"}}})
            failed = work.complete_read_deliverable("alice", run["id"], action["id"], result={"status": "UNAVAILABLE", "reason": "provider offline"})
            assert failed["status"] == "failed"
            assert failed["lifecycle_state"] == "failed"
    finally:
        engine.dispose()


def test_work_engine_direct_read_completion_rejects_nested_failure_status():
    engine, session_factory = _session_factory()
    try:
        with session_factory() as db:
            work = WorkEngine(db)
            run = work.create_run("alice", {
                "domain": "memory",
                "completion_criteria": {"completion_mode": "single_verified_read", "deliverable": "memory"},
            })
            action = work.create_action("alice", run["id"], {
                "capability_id": "memory.read", "action_id": "summarize_owner_memory",
                "effect_class": "read_private", "status": "proposed",
            })
            work.complete_action("alice", action["id"], {"result": {"domain_reference": {"status": "UNAVAILABLE"}}})
            failed = work.complete_read_deliverable(
                "alice", run["id"], action["id"],
                result={"domain_reference": {"status": "UNAVAILABLE", "reason": "provider offline"}},
            )
            assert failed["status"] == "failed"
            assert failed["lifecycle_state"] == "failed"
    finally:
        engine.dispose()


def test_communications_canonical_read_is_persisted_in_the_shared_work_run(monkeypatch):
    """Every first-class canonical read must remain inspectable and resumable."""
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-communications", "What communications are configured?",
            intent={
                "domains": ["communications"],
                "domain_concept": "COMMUNICATIONS",
                "operation_class": "READ",
            },
        )
        action_id = bridge.prepare_action(
            "alice", run_id, "read_communications", {"action": "overview"},
        )
        assert action_id
        completed = bridge.record_result(
            "alice", action_id,
            {"success": True, "data": {"status": "SUCCESS_EMPTY", "email": {}, "calendar": {}}},
        )
        assert completed["read_completion"]["lifecycle_state"] == "succeeded"
        with session_factory() as db:
            action = db.query(WorkAction).filter_by(id=action_id).one()
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            assert action.tool_binding_name == "read_communications"
            assert run.domain == "communications"
            assert run.result_summary["result_status"] == "SUCCESS_EMPTY"
    finally:
        engine.dispose()


def test_canonical_read_failure_is_not_reported_as_empty(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-assets", "What IT assets do I have?",
            intent={
                "domains": ["asset_inventory"],
                "domain_concept": "TECHNICAL_ASSET",
                "operation_class": "READ",
            },
        )
        action_id = bridge.prepare_action("alice", run_id, "manage_assets", {"action": "list"})
        assert action_id
        bridge.record_result("alice", action_id, {"error": "CMDB unavailable", "exit_code": 1})
        assessment = bridge.assess_agent_run("alice", run_id)
        assert assessment["status"] == "BLOCKED"
        assert "CMDB unavailable" in assessment["reason"]
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
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            assert action.capability_id == "homelab.manage"
            assert action.action_id == "execute_network_discovery"
            assert action.tool_binding_name == "manage_homelab"
            assert action.status == "proposed"
            assert action.sealed_input_digest
            assert run.continuation_state["pending_action_id"] == action_id
            assert run.continuation_state["phase"] == "PROPOSED"

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
        # The whole network deliverable is one durable Run. Declaring the
        # later stages up front prevents the verified discovery step from
        # becoming a falsely terminal Run before service enumeration begins.
        with session_factory() as db:
            run = db.query(WorkRun).filter_by(id=run_id, owner="alice").one()
            run.plan = [
                {"sequence": 1, "capability_id": "homelab.manage", "action_id": "execute_network_discovery", "target_resources": ["network:private_scope"]},
                {"sequence": 2, "capability_id": "homelab.manage", "action_id": "plan_network_service_enumeration"},
                {"sequence": 3, "capability_id": "homelab.manage", "action_id": "execute_network_service_enumeration", "target_resources": ["network:private_scope"]},
            ]
            db.commit()
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
                    {"ip_addresses": ["192.168.10.4", "192.168.10.6"]},
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
            assert plan.normalized_input["targets"] == ["192.168.10.4", "192.168.10.6", "192.168.10.5"]
        bridge.record_result("alice", plan_id, {"data": {"operation_digest": "s" * 64}})

        action_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "execute_network_service_enumeration", "plan_digest": "s" * 64},
        )
        with session_factory() as db:
            action = db.query(WorkAction).filter_by(id=action_id).one()
            assert action.normalized_input["targets"] == ["192.168.10.4", "192.168.10.6", "192.168.10.5"]
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


def test_continuation_run_projection_is_owner_scoped_and_read_only(monkeypatch):
    engine, session_factory = _session_factory()
    monkeypatch.setattr(bridge, "SessionLocal", session_factory)
    try:
        run_id = bridge.ensure_agent_run(
            "alice", "chat-continuation", "deep network discovery",
            intent={"domains": ["network_ops"]},
        )
        action_id = bridge.prepare_action(
            "alice", run_id, "manage_homelab",
            {"action": "plan_network_discovery", "cidr": "192.168.10.0/24"},
        )
        projection = bridge.continuation_run_projection("alice", run_id)
        assert projection["id"] == run_id
        assert projection["actions"] == [{"id": action_id, "status": "proposed", "sequence": 1}]
        assert projection["continuation_state"]["source"] == "chat_agent"
        assert bridge.continuation_run_projection("bob", run_id) is None
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
