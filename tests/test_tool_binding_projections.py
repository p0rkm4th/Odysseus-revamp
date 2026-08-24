from src.agent_tools import FUNCTION_TOOL_SCHEMAS, TOOL_TAGS
from src.agent_loop import TOOL_SECTIONS, _DOMAIN_TOOL_MAP
from src.capability_registry import capability_for_tool
from src.tool_bindings import TOOL_BINDINGS, binding_for_tool


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
    assert set(TOOL_BINDINGS) == {"manage_assets", "privileged_action", "manage_homelab", "manage_osint", "manage_security_assessment"}
    assert len({binding.capability_id for binding in TOOL_BINDINGS.values()}) == 5
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
