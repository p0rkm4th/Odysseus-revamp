from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def _registry_dump():
    script = """
      import { WORKSPACE_DEFINITIONS, MODULE_DEFINITIONS } from './static/js/workspaceRegistry.js';
      console.log(JSON.stringify({workspaces: WORKSPACE_DEFINITIONS, modules: MODULE_DEFINITIONS}));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    import json
    return json.loads(result.stdout)


def test_workspace_registry_has_unique_first_class_destinations_and_icons():
    data = _registry_dump()
    workspaces = data["workspaces"]
    modules = data["modules"]
    assert 8 <= len(workspaces) <= 10
    assert len({entry["id"] for entry in workspaces}) == len(workspaces)
    assert all(entry["label"] and entry["icon"] and entry["modules"] for entry in workspaces)
    assert len({entry[0] for entry in modules}) == len(modules)
    assert all(entry[0] and entry[1] and entry[2] for entry in modules)


def test_every_workspace_member_is_declared_once_as_a_module_identity():
    data = _registry_dump()
    modules = {entry[0]: entry for entry in data["modules"]}
    referenced = [module_id for workspace in data["workspaces"] for module_id in workspace["modules"]]
    assert set(referenced) <= set(modules)
    assert all(modules[module_id][1] and modules[module_id][2] for module_id in referenced)


def test_workspace_projection_has_explicit_virtual_or_legacy_navigation_binding():
    data = _registry_dump()
    modules = {entry[0]: entry for entry in data["modules"]}
    for workspace in data["workspaces"]:
        for module_id in workspace["modules"]:
            # null is intentional for a contextual/search-only module; it must
            # still have canonical label and icon metadata above.
            assert module_id in modules
            assert len(modules[module_id]) == 4


def test_workspace_registry_projects_the_observed_compact_navigation_defect():
    data = _registry_dump()
    workspace_ids = {entry["id"] for entry in data["workspaces"]}
    assert {"hades", "today", "research", "infrastructure", "home", "communications", "work", "knowledge", "system"} <= workspace_ids
    module_ids = {entry[0] for entry in data["modules"]}
    assert {"hades", "household", "assets", "network", "developer", "homelab", "worldModel", "controlCenter", "osint"} <= module_ids
