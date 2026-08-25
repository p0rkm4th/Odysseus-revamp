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


def test_native_action_enums_cover_every_registered_action():
    """Native providers must not silently lose a canonical ActionSpec."""
    for name, binding in TOOL_BINDINGS.items():
        capability = capability_for_tool(name)
        schema_actions = set(
            binding.native_schema["function"]["parameters"]["properties"]["action"].get("enum", ())
        )
        assert set(capability.actions) <= schema_actions, (name, set(capability.actions) - schema_actions)


def test_projection_has_no_duplicate_conflicting_bindings():
    assert set(TOOL_BINDINGS) == {"manage_assets", "privileged_action", "manage_homelab", "manage_osint", "manage_security_assessment", "read_memory", "read_work", "read_household", "read_setup", "read_career"}
    assert len({binding.capability_id for binding in TOOL_BINDINGS.values()}) == 10
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


def test_registered_binding_cannot_bypass_disabled_or_tool_policy(monkeypatch):
    calls = []

    async def fake_executor(block, owner=None):
        calls.append(block.tool_type)
        return "manage_assets", {"exit_code": 0}

    monkeypatch.setitem(tool_execution._CAPABILITY_V1_EXECUTORS, "manage_assets", fake_executor)
    block = type("Block", (), {"tool_type": "manage_assets", "content": '{"action":"summary"}'})()

    disabled = asyncio.run(tool_execution.execute_tool_block(block, owner="alice", disabled_tools={"manage_assets"}))
    assert disabled[1]["blocked"] is True
    assert disabled[1]["policy"] == "disabled_tools"

    class Policy:
        def blocks(self, name):
            return name == "manage_assets"

    policy = asyncio.run(tool_execution.execute_tool_block(block, owner="alice", tool_policy=Policy()))
    assert policy[1]["blocked"] is True
    assert policy[1]["policy"] == "tool_policy"
    assert calls == []


def test_registered_consequential_action_requires_exact_approval_or_grant(monkeypatch):
    called = []

    async def fake_executor(block, owner=None):
        called.append(True)
        return "manage_homelab", {"exit_code": 0}

    monkeypatch.setitem(tool_execution._CAPABILITY_V1_EXECUTORS, "manage_homelab", fake_executor)
    result = asyncio.run(tool_execution.execute_tool_block(
        type("Block", (), {"tool_type": "manage_homelab", "content": '{"action":"execute_network_discovery"}'})(),
        owner="alice",
    ))
    assert result[1]["blocked"] is True
    assert result[1]["policy"] == "exact_tool_approval"
    assert called == []


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


def test_household_read_binding_reuses_owner_scoped_inventory_service(monkeypatch):
    from core import database as cdb
    from core import inventory_models  # noqa: F401
    from src.inventory_service import get_inventory_service
    from tests.helpers.sqlite_db import make_temp_sqlite
    session_factory, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    service.create_item("alice", name="Rice", domain="kitchen", item_kind="ingredient")
    monkeypatch.setattr("src.inventory_service.get_inventory_service", lambda: service)
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_household", payload={"action": "overview"}, owner="alice"))
    assert result["success"] is True
    assert result["data"]["canonical_store"] == "inventory_service"
    assert result["data"]["item_count"] == 1
    assert result["data"]["items"][0]["name"] == "Rice"
    engine.dispose()
    tmpfile.close()


def test_setup_read_binding_reuses_secret_free_owner_projection(monkeypatch, tmp_path):
    import src.setup_center as setup_center
    monkeypatch.setattr(setup_center, "SETUP_STATE_FILE", tmp_path / "setup.json")
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_setup", payload={"action": "state"}, owner="alice"))
    assert result["success"] is True
    assert result["data"]["owner"] == "alice"
    assert result["data"]["secrets_exposed"] is False


def test_osint_read_binding_reuses_owner_scoped_case_store(tmp_path, monkeypatch):
    import json
    import src.osint_read as osint_read
    monkeypatch.setattr(osint_read, "RESEARCH_DATA_DIR", tmp_path)
    (tmp_path / "case-1.json").write_text(json.dumps({
        "owner": "alice", "query": "Cerberus", "status": "done",
        "sources": [{"url": "https://example.test/source", "title": "Example"}],
    }), encoding="utf-8")
    (tmp_path / "other.json").write_text(json.dumps({"owner": "bob", "query": "private"}), encoding="utf-8")
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="manage_osint", payload={"action": "list_cases"}, owner="alice"))
    assert result["success"] is True
    assert result["data"]["case_count"] == 1
    assert result["data"]["cases"][0]["id"] == "case-1"
