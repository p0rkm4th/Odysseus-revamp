"""Guard the production ACI strangler boundary.

Compatibility tests may still call ``agent_loop.stream_agent_loop`` directly.
This check intentionally scans only runtime packages, excluding the canonical
ACI seam and the compatibility implementation itself.
"""

import ast
from pathlib import Path


def _runtime_call_nodes(function_name: str):
    calls = []
    repo = Path(__file__).parents[1]
    for root_name in ("routes", "src", "core", "services"):
        root = repo / root_name
        for path in root.rglob("*.py"):
            if path.name in {"agent_loop.py", "aci.py"}:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                name = (
                    function.id
                    if isinstance(function, ast.Name)
                    else function.attr
                    if isinstance(function, ast.Attribute)
                    else ""
                )
                if name == function_name:
                    calls.append((path.relative_to(repo), node))
    return calls


def _runtime_calls(function_name: str):
    return [f"{path}:{node.lineno}" for path, node in _runtime_call_nodes(function_name)]


def test_production_runtime_has_no_direct_legacy_stream_callers():
    assert _runtime_calls("stream_agent_loop") == []


def test_production_runtime_does_not_import_legacy_stream_function():
    repo = Path(__file__).parents[1]
    imports = []
    for root_name in ("routes", "src", "core", "services"):
        root = repo / root_name
        for path in root.rglob("*.py"):
            if path.name in {"agent_loop.py", "aci.py"}:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and any(
                    alias.name == "stream_agent_loop" for alias in node.names
                ):
                    imports.append(f"{path.relative_to(repo)}:{node.lineno}")
                if isinstance(node, ast.Import) and any(
                    alias.name.endswith(".stream_agent_loop") for alias in node.names
                ):
                    imports.append(f"{path.relative_to(repo)}:{node.lineno}")
    assert imports == []


def test_legacy_runtime_imports_are_limited_to_owner_facing_tool_metadata():
    """The compatibility module cannot become a hidden production entrypoint."""
    repo = Path(__file__).parents[1]
    imports = []
    for root_name in ("routes", "src", "core", "services"):
        for path in (repo / root_name).rglob("*.py"):
            if path.name in {"agent_loop.py", "aci.py"}:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.module != "src.agent_loop":
                    continue
                imports.extend(
                    (path.relative_to(repo), alias.name)
                    for alias in node.names
                )
    assert imports
    assert {
        (path, name)
        for path, name in imports
    } == {(Path("routes/skills_routes.py"), "TOOL_SECTIONS")}


def test_production_runtime_has_canonical_aci_stream_callers():
    calls = _runtime_calls("stream_aci_turn")
    assert len(calls) >= 6, calls


def test_aci_runtime_does_not_call_retained_compatibility_aliases():
    """Compatibility exports must not become a second runtime authority."""
    repo = Path(__file__).parents[1]
    tree = ast.parse(
        (repo / "src" / "agent_loop.py").read_text(encoding="utf-8"),
        filename=str(repo / "src" / "agent_loop.py"),
    )
    runtime = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "stream_aci_runtime"
    )
    retained_aliases = {
        "_strip_agent_injected_messages",
        "_strip_think_blocks",
        "_empty_response_fallback",
        "_run_verifier_subagent",
        "_privileged_action_requires_exact_approval",
        "_usage_bucket_summary",
        "_build_actions_snapshot",
        "_prepend_agent_directive",
    }
    calls = {
        node.func.id
        for node in ast.walk(runtime)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }
    assert not (calls & retained_aliases)


def test_every_production_aci_stream_call_explicitly_selects_aci_mode():
    """Prevent a future caller from silently selecting the compatibility default."""
    missing = []
    for path, node in _runtime_call_nodes("stream_aci_turn"):
        selected = {
            keyword.arg: keyword.value.value
            for keyword in node.keywords
            if keyword.arg == "aci_mode"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        }
        if selected.get("aci_mode") != "aci":
            missing.append(f"{path}:{node.lineno}")
    assert missing == []


def test_foreground_chat_route_has_no_legacy_stream_injection_seam():
    """The owner-facing route cannot be redirected around the ACI seam."""
    repo = Path(__file__).parents[1]
    path = repo / "routes" / "chat_routes.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    legacy_bindings = []
    aci_entrypoint_calls = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(node, ast.AugAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id == "stream_agent_loop":
                    legacy_bindings.append(node.lineno)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = node.names
            if any(alias.name == "stream_agent_loop" for alias in names):
                legacy_bindings.append(node.lineno)
        if isinstance(node, ast.Call):
            function = node.func
            name = (
                function.id
                if isinstance(function, ast.Name)
                else function.attr
                if isinstance(function, ast.Attribute)
                else ""
            )
            if name == "stream_aci_turn":
                aci_entrypoint_calls.append(node.lineno)

    assert legacy_bindings == []
    assert aci_entrypoint_calls, "foreground route must call the canonical ACI stream"
