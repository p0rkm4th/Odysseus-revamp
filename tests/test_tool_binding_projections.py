from src.agent_tools import FUNCTION_TOOL_SCHEMAS, TOOL_TAGS, ToolBlock
from src.agent_loop import TOOL_SECTIONS, _DOMAIN_TOOL_MAP
from src.capability_registry import capability_for_tool
from src.tool_bindings import TOOL_BINDINGS, binding_for_tool
import asyncio
import json
import src.tool_execution as tool_execution
from src.homelab_operations import HomelabOperations


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
        if name in {"web_search", "web_fetch"}:
            action_id = {"web_search": "search", "web_fetch": "fetch"}[name]
            assert capability.actions[action_id].executor_key == binding.executor_key
        else:
            assert all(action.executor_key == binding.executor_key
                       for action in capability.actions.values())
        for domain in binding.domains:
            assert name in _DOMAIN_TOOL_MAP[domain]


def test_native_action_enums_cover_every_registered_action():
    """Native providers must not silently lose a canonical ActionSpec."""
    for name, binding in TOOL_BINDINGS.items():
        capability = capability_for_tool(name)
        properties = binding.native_schema["function"]["parameters"]["properties"]
        if "action" in properties:
            schema_actions = set(properties["action"].get("enum", ()))
            if name in {"web_search", "web_fetch"}:
                # These are intentionally single-purpose bindings over the
                # shared web.evidence capability.
                expected = {"web_search": "search", "web_fetch": "fetch"}[name]
                assert schema_actions == {expected}
            else:
                assert set(capability.actions) <= schema_actions, (name, set(capability.actions) - schema_actions)
        else:
            # Single-purpose bindings expose their ActionSpec through the
            # binding identity rather than a multiplexed action enum.
            assert name in {"web_search", "web_fetch"}
            action_id = {"web_search": "search", "web_fetch": "fetch"}[name]
            assert capability.actions[action_id].executor_key == name


def test_recipe_import_schema_allows_unprepared_commit_payload():
    """Import arguments are completed by prepare_import, not the model call."""
    schema = _schema("manage_recipes")["function"]["parameters"]
    assert schema["required"] == ["action"]
    assert "requested_name" in schema["properties"]
    assert "source_url" in schema["properties"]
    assert "draft" in schema["properties"]


def test_projection_has_no_duplicate_conflicting_bindings():
    assert set(TOOL_BINDINGS) == {"manage_assets", "privileged_action", "manage_homelab", "manage_osint", "manage_security_assessment", "read_memory", "read_work", "manage_work", "read_household", "read_recipes", "manage_recipes", "read_setup", "read_career", "read_communications", "developer_read", "web_search", "web_fetch"}
    assert len({binding.capability_id for binding in TOOL_BINDINGS.values()}) == 16
    for name, binding in TOOL_BINDINGS.items():
        assert binding.native_schema["function"]["name"] == name
        assert binding.textual_contract.strip()
        assert binding.executor_key


def test_recipe_binding_executes_canonical_scale_read(monkeypatch):
    class FakeInventory:
        def manage_recipes(self, payload, *, owner):
            assert owner == "alice"
            assert payload == {"action": "scale", "recipe_id": "recipe-1", "servings": "6"}
            return {
                "recipe_id": "recipe-1",
                "recipe_name": "Chili",
                "servings": "6",
                "scaled_ingredients": [],
            }

    monkeypatch.setattr(
        "src.inventory_service.get_inventory_service",
        lambda: FakeInventory(),
    )
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_recipes",
        payload={"action": "scale", "recipe_id": "recipe-1", "servings": "6"},
        owner="alice",
    ))
    assert result["success"] is True
    assert result["data"]["scaled_ingredients"] == []


def test_recipe_binding_executes_canonical_shopping_requirements_read(monkeypatch):
    class FakeInventory:
        def manage_recipes(self, payload, *, owner):
            assert owner == "alice"
            assert payload == {"action": "shopping_requirements", "recipe_id": "recipe-1"}
            return {
                "status": "SUCCESS",
                "result_type": "recipe_shopping_requirements",
                "operation": "shopping_requirements",
                "canonical_store": "inventory_service",
                "recipe_id": "recipe-1",
                "recipe_name": "Chili",
                "can_make": False,
                "missing_ingredients": [{"name": "beans", "quantity": "1", "unit": "can"}],
            }

    monkeypatch.setattr(
        "src.inventory_service.get_inventory_service",
        lambda: FakeInventory(),
    )
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_recipes",
        payload={"action": "shopping_requirements", "recipe_id": "recipe-1"},
        owner="alice",
    ))
    assert result["success"] is True
    assert result["data"]["result_type"] == "recipe_shopping_requirements"


def test_recipe_binding_executes_canonical_search_read(monkeypatch):
    class FakeInventory:
        def manage_recipes(self, payload, *, owner):
            assert owner == "alice"
            assert payload == {"action": "search", "query": "chili"}
            return {
                "status": "SUCCESS",
                "result_type": "recipe_search",
                "operation": "search",
                "canonical_store": "inventory_service",
                "query": "chili",
                "recipes": [],
            }

    monkeypatch.setattr(
        "src.inventory_service.get_inventory_service",
        lambda: FakeInventory(),
    )
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_recipes",
        payload={"action": "search", "query": "chili"},
        owner="alice",
    ))
    assert result["success"] is True
    assert result["data"]["operation"] == "search"


def test_network_binding_preserves_host_broker_boundary():
    binding = TOOL_BINDINGS["manage_homelab"]
    assert binding.execution_location == "host_broker"
    assert binding.target_scope == "private_network"
    assert binding.requires_direct_container_access is False
    assert "manage_homelab" in _DOMAIN_TOOL_MAP["network_ops"]


def test_network_read_views_project_owner_scoped_canonical_data(monkeypatch):
    projection = {
        "identity_rule": "IP addresses remain observations; no IP-only merge",
        "nodes": [
            {
                "id": "unidentified:192.168.10.20",
                "resolution_state": "unidentified",
                "canonical": False,
                "attributes": {"ip": "192.168.10.20"},
                "observations": [],
            },
            {
                "id": "asset-server",
                "resolution_state": "canonical",
                "canonical": True,
                "attributes": {"observed_ip": "192.168.10.30"},
                "observations": [{
                    "observed_at": "2026-08-25T10:00:00+00:00",
                    "data_json": json.dumps({"open_ports": [445], "port_meanings": ["microsoft-ds"]}),
                }],
            },
        ],
        "edges": [],
    }
    monkeypatch.setattr("src.network_projection.map_projection", lambda *, owner: projection)

    unidentified = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="manage_homelab", payload={"action": "list_unidentified_hosts"}, owner="alice"))
    assert unidentified["success"] is True
    assert unidentified["data"]["status"] == "SUCCESS"
    assert unidentified["data"]["owner_scope"] == "alice"
    assert [host["id"] for host in unidentified["data"]["hosts"]] == ["unidentified:192.168.10.20"]

    roles = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="manage_homelab", payload={"action": "infer_role_hypotheses"}, owner="alice"))
    assert roles["success"] is True
    assert roles["data"]["status"] == "SUCCESS"
    assert roles["data"]["hypotheses"][0]["role"] == "file_server_or_windows_host"
    assert roles["data"]["hypotheses"][0]["classification"] == "INFERRED"
    assert roles["data"]["hypotheses"][0]["canonical_ref"] == "asset-server"
    assert roles["data"]["hypotheses"][0]["canonical_identity_updated"] is False


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


def test_asset_detail_binding_preserves_collection_result_contract(monkeypatch):
    class Completed:
        returncode = 0
        stdout = json.dumps({"id": "PHYSICAL-001", "name": "Cerberus"})
        stderr = ""

    calls = []
    monkeypatch.setattr(
        tool_execution._ody_v34_subprocess,
        "run",
        lambda argv, **kwargs: (calls.append(argv) or Completed()),
    )
    binding, result = asyncio.run(tool_execution._execute_manage_assets_binding(
        type("Block", (), {"content": '{"action":"get","asset":"PHYSICAL-001"}'})(),
        owner="alice",
    ))
    assert binding == "manage_assets"
    assert result["success"] is True
    assert result["data"]["assets"] == [{"id": "PHYSICAL-001", "name": "Cerberus"}]
    assert calls and calls[0][-1] == "PHYSICAL-001"


def test_registered_dispatch_rejects_malformed_canonical_read_result(monkeypatch):
    async def fake_executor(block, owner=None):
        return "manage_homelab", {
            "exit_code": 0,
            "success": True,
            "data": {"status": "SUCCESS", "hosts": []},
        }

    monkeypatch.setitem(tool_execution._CAPABILITY_V1_EXECUTORS, "manage_homelab", fake_executor)
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="manage_homelab",
        payload={"action": "read_network_observations"},
        owner="alice",
    ))
    assert result["success"] is False
    assert result["error_code"] == "RESULT_INVALID"
    assert result["status"] == "INVALID_RESULT"


def test_homelab_binding_preserves_structured_executor_failure(monkeypatch):
    class FailingHomelab:
        async def execute(self, payload, *, owner):
            assert payload == {"action": "read_network_context"}
            assert owner == "alice"
            return {
                "status": "UNAVAILABLE",
                "error_code": "HOST_NETWORK_CONTEXT_UNAVAILABLE",
                "source": "host_network_broker",
            }

    monkeypatch.setattr("src.homelab_operations.HomelabOperations", FailingHomelab)
    block = type("Block", (), {
        "content": '{"action":"read_network_context"}',
    })()
    binding, result = asyncio.run(tool_execution._execute_manage_homelab_binding(block, owner="alice"))
    assert binding == "manage_homelab"
    assert result["success"] is False
    assert result["exit_code"] == 1
    assert result["data"]["error_code"] == "HOST_NETWORK_CONTEXT_UNAVAILABLE"


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
    assert result["data"]["status"] == "SUCCESS_WITH_DATA"
    assert result["data"]["result_type"] == "work_overview"
    assert result["data"]["operation"] == "overview"
    assert result["data"]["canonical_store"] == "work_engine"
    assert len(result["data"]["goals"]) == 1
    assert result["data"]["goals"][0]["title"] == "Ship the release"
    engine.dispose()
    tmpfile.close()


def test_work_task_mutation_uses_existing_engine_and_verifies_readback(monkeypatch):
    from core.database import Base
    from tests.helpers.sqlite_db import make_temp_sqlite
    from src.work_engine import WorkEngine
    session_factory, engine, tmpfile = make_temp_sqlite(Base.metadata)
    monkeypatch.setattr("core.database.SessionLocal", session_factory)
    with session_factory() as db:
        project = WorkEngine(db).create_project("alice", {"title": "Hades V1"})

    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="manage_work",
        payload={"action": "create_task", "title": "Review the backup plan", "project_title": "Hades V1"},
        owner="alice",
    ))
    assert result["success"] is True
    assert result["verified"] is True
    assert result["data"]["status"] == "VERIFIED"
    assert result["data"]["task"]["title"] == "Review the backup plan"
    with session_factory() as db:
        tasks = WorkEngine(db).list_records("alice", __import__("core.work_models", fromlist=["WorkTask"]).WorkTask)
        assert [task["title"] for task in tasks] == ["Review the backup plan"]
    engine.dispose()
    tmpfile.close()


def test_work_project_mutation_uses_existing_engine_and_verifies_readback(monkeypatch):
    from core.database import Base
    from tests.helpers.sqlite_db import make_temp_sqlite
    from src.work_engine import WorkEngine
    session_factory, engine, tmpfile = make_temp_sqlite(Base.metadata)
    monkeypatch.setattr("core.database.SessionLocal", session_factory)

    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="manage_work",
        payload={"action": "create", "title": "Acceptance Infrastructure Migration", "domain": "general"},
        owner="alice",
    ))

    assert result["success"] is True
    assert result["verified"] is True
    assert result["data"]["status"] == "VERIFIED"
    assert result["data"]["project"]["title"] == "Acceptance Infrastructure Migration"
    with session_factory() as db:
        projects = WorkEngine(db).list_records("alice", __import__("core.work_models", fromlist=["WorkProject"]).WorkProject)
        assert [project["title"] for project in projects] == ["Acceptance Infrastructure Migration"]
    engine.dispose()
    tmpfile.close()


def test_registered_read_default_is_materialized_before_executor(monkeypatch):
    seen = []

    async def fake_executor(block, owner=None):
        seen.append(json.loads(block.content))
        return "read_work", {"exit_code": 0, "success": True, "output": "ok"}

    monkeypatch.setitem(tool_execution._CAPABILITY_V1_EXECUTORS, "read_work", fake_executor)
    result = asyncio.run(tool_execution.execute_tool_block(
        ToolBlock("read_work", "{}"),
        owner="alice",
    ))
    assert result[1]["success"] is True
    assert seen == [{"action": "overview"}]


def test_work_mission_and_watch_reads_are_owner_scoped(monkeypatch):
    from core.database import Base
    from core.persistent_agent_models import Monitor
    from tests.helpers.sqlite_db import make_temp_sqlite
    from src.mission_projection import MissionService
    from src.work_engine import WorkEngine
    session_factory, engine, tmpfile = make_temp_sqlite(Base.metadata)
    monkeypatch.setattr("core.database.SessionLocal", session_factory)
    with session_factory() as db:
        mission = MissionService(db).create("alice", {"title": "Night watch", "desired_outcome": "Finish the report"})
        db.add(Monitor(
            id="watch-alice", owner="alice", name="Build health", condition_type="health",
            source_domain="system", query={}, condition={}, consequence_tier=1,
            notification_policy={}, cooldown_seconds=3600,
        ))
        db.add(Monitor(
            id="watch-bob", owner="bob", name="Private watch", condition_type="health",
            source_domain="system", query={}, condition={}, consequence_tier=1,
            notification_policy={}, cooldown_seconds=3600,
        ))
        db.commit()

    mission_result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_work", payload={"action": "list_missions"}, owner="alice"))
    watch_result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_work", payload={"action": "list_watches"}, owner="alice"))
    assert mission_result["success"] is True
    assert mission_result["data"]["status"] == "SUCCESS"
    assert mission_result["data"]["missions"][0]["id"] == mission["id"]
    assert watch_result["success"] is True
    assert watch_result["data"]["status"] == "SUCCESS"
    assert [watch["id"] for watch in watch_result["data"]["watches"]] == ["watch-alice"]
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
    assert result["data"]["status"] == "SUCCESS_WITH_DATA"
    assert result["data"]["owner"] == "alice"
    assert result["data"]["secrets_exposed"] is False


def test_statusless_canonical_read_payload_distinguishes_empty_from_data():
    from src.tool_execution import _with_canonical_read_status

    assert _with_canonical_read_status({"items": []})["status"] == "SUCCESS_EMPTY"
    assert _with_canonical_read_status({"items": [{"id": "item-1"}]})["status"] == "SUCCESS_WITH_DATA"
    assert _with_canonical_read_status({"status": "DEGRADED", "items": []})["status"] == "DEGRADED"
    assert _with_canonical_read_status({"error": "provider unavailable"})["status"] == "FAILED"


def test_nested_unprojected_read_cannot_be_reported_as_empty_success():
    from src.tool_execution import _with_canonical_read_status

    result = _with_canonical_read_status({
        "email": {"accounts": []},
        "contacts": {"status": "NOT_PROJECTED", "reason": "owner boundary unavailable"},
    })
    assert result["status"] == "DEGRADED"
    assert result["degraded_reason"] == "NOT_PROJECTED"
    assert result["contacts"]["status"] == "NOT_PROJECTED"

    explicit = _with_canonical_read_status({
        "status": "SUCCESS_EMPTY",
        "email": {"accounts": []},
        "contacts": {"status": "NOT_PROJECTED"},
    })
    assert explicit["status"] == "DEGRADED"


def test_contacts_read_result_requires_typed_contacts_collection():
    from src.intent_contracts import validate_bound_result

    valid, reason = validate_bound_result(
        "read_communications", "contacts",
        {"status": "SUCCESS_EMPTY", "contacts": []},
    )
    assert valid is True
    assert reason == "SUCCESS_EMPTY"

    valid, reason = validate_bound_result(
        "read_communications", "contacts",
        {"status": "SUCCESS_WITH_DATA", "contacts": "not-a-list"},
    )
    assert valid is False
    assert reason == "INVALID_RESULT"


def test_contacts_read_fails_closed_for_non_single_user_owner(monkeypatch):
    import asyncio
    import src.tool_security as tool_security
    import src.tool_execution as tool_execution

    monkeypatch.setattr(tool_security, "owner_is_admin_or_single_user", lambda owner: False)
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_communications", payload={"action": "contacts"}, owner="alice",
    ))
    assert result["success"] is True
    assert result["data"]["status"] == "UNAVAILABLE"
    assert result["data"]["error_code"] == "OWNER_BOUNDARY_UNAVAILABLE"


def test_contacts_unavailable_result_is_not_rewritten_as_result_invalid():
    from src.intent_contracts import validate_bound_result

    valid, reason = validate_bound_result(
        "read_communications", "contacts", {
            "status": "UNAVAILABLE",
            "error_code": "OWNER_BOUNDARY_UNAVAILABLE",
            "contacts": [],
        },
    )
    assert valid is True
    assert reason == "UNAVAILABLE"


def test_communications_read_binding_requires_authenticated_owner():
    result = asyncio.run(tool_execution.execute_registered_binding(
        tool_name="read_communications", payload={"action": "overview"}, owner=None))
    assert result["success"] is False
    assert "owner" in result["error"].lower()


def test_generic_service_status_read_uses_runtime_health_not_container_systemd(monkeypatch):
    async def fake_health():
        return {
            "overall": "degraded",
            "services": [{"name": "chromadb", "status": "ok"}],
            "timestamp": "2026-08-26T00:00:00+00:00",
        }

    monkeypatch.setattr("src.service_health.collect_service_health", fake_health)
    result = asyncio.run(HomelabOperations().execute({"action": "service_status"}, owner="alice"))
    assert result["success"] is True
    assert result["status"] == "SUCCESS_WITH_DATA"
    assert result["target"] == "hades-runtime"
    assert result["source"] == "canonical_service_health"
    assert result["overall"] == "degraded"


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
