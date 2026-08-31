"""Contract tests for the small Hades kernel module lifecycle."""

from __future__ import annotations

from src.aci import project_action_selection
from src.module_manager import ModuleManager, ModuleSpec, ModuleState


def _recipe_intent(action: str = "add") -> dict:
    return {
        "intent_frame": {"domain_concept": "RECIPE", "operation_class": "CREATE"},
        "resolved_contract": {
            "capability_id": "recipe.manage",
            "binding": "manage_recipes",
            "action_id": action,
        },
    }


def test_recipe_is_available_but_disabled_capabilities_are_not_projected():
    manager = ModuleManager(enabled_modules={"core", "legacy-capabilities"})

    assert manager.state("recipes") is ModuleState.AVAILABLE
    assert "recipe.manage" not in manager.enabled_capability_ids()
    assert "manage_recipes" in manager.disabled_tool_names()

    projection = project_action_selection(
        intent=_recipe_intent(), relevant_tools=["manage_recipes"],
        disabled_tools=set(), owner="owner", active_run=None,
        query="add a recipe", module_manager=manager,
    )
    assert projection.choice_map == {}
    assert manager.active_module_ids() == frozenset()


def test_enabled_recipe_stays_inactive_until_recipe_capability_is_selected():
    manager = ModuleManager(enabled_modules={"core", "recipes", "legacy-capabilities"})

    unrelated = {
        "intent_frame": {"domain_concept": "NETWORK", "operation_class": "READ"},
        "resolved_contract": {
            "capability_id": "homelab.manage",
            "binding": "manage_homelab",
            "action_id": "read_network_context",
        },
    }
    project_action_selection(
        intent=unrelated, relevant_tools=["manage_homelab"], disabled_tools=set(),
        owner="owner", active_run=None, query="what network am i on",
        module_manager=manager,
    )
    assert manager.state("recipes") is ModuleState.ENABLED
    assert "recipes" not in manager.active_module_ids()


def test_recipe_activation_is_lazy_and_request_scoped():
    manager = ModuleManager(enabled_modules={"core", "recipes", "legacy-capabilities"})
    assert manager.state("recipes") is ModuleState.ENABLED

    project_action_selection(
        intent=_recipe_intent(), relevant_tools=["manage_recipes"],
        disabled_tools=set(), owner="owner", active_run=None,
        query="add a recipe called Test Recipe", module_manager=manager,
    )
    assert manager.state("recipes") is ModuleState.ACTIVE
    assert manager.active_module_ids() == frozenset({"recipes"})


def test_module_entrypoint_imports_only_on_activation(monkeypatch):
    calls: list[str] = []

    class FakeModule:
        pass

    def fake_import(name: str):
        calls.append(name)
        return FakeModule()

    monkeypatch.setattr("src.module_manager.importlib.import_module", fake_import)
    manager = ModuleManager({
        "demo": ModuleSpec("demo", ("demo.capability",), "feature.demo"),
    }, enabled_modules={"demo"})

    assert calls == []
    assert manager.state("demo") is ModuleState.ENABLED
    manager.activate_for_capability("demo.capability")
    assert calls == ["feature.demo"]
    assert manager.state("demo") is ModuleState.ACTIVE
