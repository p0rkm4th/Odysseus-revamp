import json

from src.capability_registry import (
    ApprovalMode,
    action_for_tool,
    canonicalize_action_content,
    capability_for_tool,
    requires_exact_approval,
)
from src.tool_capabilities import ToolEffect, capabilities_for_action
from src.tool_bindings import projected_contracts, projected_schemas


def test_custom_capabilities_have_stable_ids_and_unique_actions():
    inventory = capability_for_tool("manage_assets")
    privileged = capability_for_tool("privileged_action")
    assert inventory and inventory.capability_id == "inventory.manage"
    assert privileged and privileged.capability_id == "system.privileged_diagnostics"
    assert len(inventory.actions) == len(set(inventory.actions))
    assert len(privileged.actions) == len(set(privileged.actions))


def test_mutation_field_resolution_is_declared_by_action_metadata():
    recipe = capability_for_tool("manage_recipes")
    inventory = capability_for_tool("manage_assets")
    memory = capability_for_tool("manage_memory")
    assert recipe.actions["add"].field_resolver == "recipe"
    assert recipe.actions["commit_import"].field_resolver == "recipe"
    assert inventory.actions["add_item"].field_resolver == "inventory"
    assert inventory.actions["consume_stock"].field_resolver == "inventory"
    assert memory.actions["add"].field_resolver == "memory"


def test_privileged_action_metadata_is_action_aware():
    status = action_for_tool("privileged_action", json.dumps({"action": "status"}))
    install = action_for_tool("privileged_action", {"action": "install_packages"})
    assert status and status.approval is ApprovalMode.NONE
    assert status.effects == ()
    assert install and install.approval is ApprovalMode.EXACT
    assert "admin_change" in install.effects
    assert requires_exact_approval("privileged_action", {"action": "status"}) is False
    assert requires_exact_approval("privileged_action", {"action": "install_packages"}) is True


def test_unknown_privileged_action_fails_closed():
    unknown = action_for_tool("privileged_action", {"action": "reboot"})
    assert unknown and unknown.known is False
    assert requires_exact_approval("privileged_action", {"action": "reboot"}) is True
    classified = capabilities_for_action("privileged_action", {"action": "reboot"})
    assert classified.known is False


def test_first_class_read_defaults_are_safe_and_canonical():
    action = action_for_tool("read_work", {})
    assert action.action_id == "overview"
    assert action.known is True
    assert requires_exact_approval("read_work", {}) is False
    assert canonicalize_action_content("read_work", "{}") == '{"action": "overview"}'


def test_recipe_pantry_candidates_is_a_known_safe_read_action():
    action = action_for_tool("read_recipes", {"action": "pantry_candidates"})
    assert action and action.action_id == "pantry_candidates"
    assert action.known is True
    assert action.approval is ApprovalMode.NONE


def test_consequential_actions_have_no_implicit_default():
    action = action_for_tool("privileged_action", {})
    assert action.known is False
    assert requires_exact_approval("privileged_action", {}) is True


def test_network_discovery_is_host_brokered_and_private_scope_bound():
    capability = capability_for_tool("manage_homelab")
    assert capability and capability.capability_id == "homelab.manage"
    action = capability.actions["execute_network_discovery"]
    assert action.executor_key == "manage_homelab"
    assert action.approval is ApprovalMode.EXACT
    assert action.execution_location == "host_broker"
    assert action.target_scope == "private_network"
    assert action.requires_direct_container_access is False
    assert action.target_resources == ("network:private_scope",)
    assert action.locks == ("network:private_scope",)
    assert action.risk_level == "high"
    assert action.idempotency == "replay_safe"
    assert action.verification == ("observations_persisted", "network_map_reconciled")


def test_network_service_enumeration_is_a_distinct_bounded_host_broker_action():
    capability = capability_for_tool("manage_homelab")
    action = capability.actions["execute_network_service_enumeration"]
    assert action.executor_key == "manage_homelab"
    assert action.approval is ApprovalMode.EXACT
    assert action.execution_location == "host_broker"
    assert action.target_scope == "private_network"
    assert action.requires_direct_container_access is False
    assert action.target_resources == ("network:private_scope",)
    assert action.locks == ("network:private_scope",)
    assert action.precheck_actions == ("plan_network_service_enumeration",)
    assert action.verification == ("service_observations_persisted", "network_map_reconciled")


def test_security_classifier_projects_status_and_install_effects():
    status = capabilities_for_action("privileged_action", {"action": "status"})
    install = capabilities_for_action("privileged_action", {"action": "install_packages"})
    assert status.known and not status.effects
    assert install.known and ToolEffect.ADMIN_CHANGE in install.effects


def test_network_binding_projection_is_provider_independent():
    schemas = {schema["function"]["name"]: schema for schema in projected_schemas()}
    assert "manage_homelab" in schemas
    action_enum = schemas["manage_homelab"]["function"]["parameters"]["properties"]["action"]["enum"]
    assert "plan_network_discovery" in action_enum
    assert "execute_network_discovery" in action_enum
    assert "plan_network_service_enumeration" in action_enum
    assert "execute_network_service_enumeration" in action_enum
    contract = projected_contracts()["manage_homelab"]
    assert "plan_network_service_enumeration" in contract
    assert "execute_network_service_enumeration" in contract
