from src.agent_tools import FUNCTION_TOOL_SCHEMAS, TOOL_TAGS
from src.agent_loop import TOOL_SECTIONS, _DOMAIN_TOOL_MAP
from src.capability_registry import capability_for_tool
from src.tool_bindings import TOOL_BINDINGS, binding_for_tool
import asyncio
import src.tool_execution as tool_execution


def _schema(name):
    return next(schema for schema in FUNCTION_TOOL_SCHEMAS
                if schema.get("function", {}).get("name") == name)


def test_native_schema_projection_matches_registered_custom_tools():
    for name in TOOL_BINDINGS:
        projected = binding_for_tool(name).native_schema
        actual = _schema(name)
        assert actual == projected
        assert actual["function"]["name"] == name


def test_tags_contracts_domains_and_executors_are_projected():
    for name, binding in TOOL_BINDINGS.items():
        assert name in TOOL_TAGS
        assert name in TOOL_SECTIONS
        assert f'<invoke name="{name}"' in binding.textual_contract
        assert binding.executor_key == name
        capability = capability_for_tool(name)
        assert all(action.executor_key == binding.executor_key
                   for action in capability.actions.values())
        for domain in binding.domains:
            assert name in _DOMAIN_TOOL_MAP[domain]


def test_projection_has_no_duplicate_conflicting_bindings():
    assert set(TOOL_BINDINGS) == {"manage_assets", "privileged_action", "manage_homelab", "manage_osint", "manage_security_assessment", "read_memory", "read_work"}
    assert len({binding.capability_id for binding in TOOL_BINDINGS.values()}) == 7
    for name, binding in TOOL_BINDINGS.items():
        assert binding.native_schema["function"]["name"] == name
        assert binding.textual_contract.strip()
        assert binding.executor_key


def test_network_binding_preserves_host_broker_boundary():
    binding = TOOL_BINDINGS["manage_homelab"]
    assert binding.execution_location == "host_broker"
    assert binding.target_scope == "private_network"
    assert binding.requires_direct_container_access is False
    assert "manage_homelab" in _DOMAIN_TOOL_MAP["network_ops"]


def test_trusted_work_adapter_reuses_registered_binding(monkeypatch):
    async def fake_executor(block, owner=None):
        assert block.tool_type == "manage_assets"
        assert owner == "alice"
        return "manage_assets", {"exit_code": 0, "data": {"count": 1}}

    monkeypatch.setitem(tool_execution._CAPABILITY_V1_EXECUTORS, "manage_assets", fake_executor)
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="manage_assets", payload={"action": "summary"}, owner="alice"))
    assert result["binding"] == "manage_assets"
    assert result["success"] is True


def test_trusted_work_adapter_rejects_unknown_binding():
    try:
        asyncio.run(tool_execution.execute_registered_binding(tool_name="unknown", payload={}, owner="alice"))
    except ValueError as exc:
        assert "unavailable" in str(exc)
    else:
        raise AssertionError("unknown binding was accepted")


def test_memory_read_binding_is_read_only_and_structured(monkeypatch):
    class Memory:
        def load_all_for_update(self):
            return [{"id": "m1", "owner": "alice", "category": "fact", "text": "likes tea", "source": "owner"}]

    import src.ai_interaction as ai_interaction
    monkeypatch.setattr(ai_interaction, "_memory_manager", Memory())
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_memory",
        payload={"action": "summarize_owner_memory", "query": "what do you remember about me"},
        owner="alice",
    ))
    assert result["success"] is True
    assert result["data"]["status"] == "ok"
    assert result["data"]["memories"][0]["text"] == "likes tea"


def test_work_read_binding_is_owner_scoped_and_structured(monkeypatch):
    from core.database import Base
    from tests.helpers.sqlite_db import make_temp_sqlite
    from src.work_engine import WorkEngine
    session_factory, engine, tmpfile = make_temp_sqlite(Base.metadata)
    monkeypatch.setattr("core.database.SessionLocal", session_factory)
    with session_factory() as db:
        goal = WorkEngine(db).create_goal("alice", {"title": "Ship the release"})
        WorkEngine(db).update_goal("alice", goal["id"], {"status": "active"})
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_work", payload={"action": "overview"}, owner="alice"))
    assert result["success"] is True
    assert len(result["data"]["goals"]) == 1
    assert result["data"]["goals"][0]["title"] == "Ship the release"
    engine.dispose()
    tmpfile.close()
