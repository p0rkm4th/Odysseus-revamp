"""Guard the production ACI strangler boundary.

Compatibility tests may still call ``agent_loop.stream_agent_loop`` directly.
This check intentionally scans only runtime packages, excluding the canonical
ACI seam and the compatibility implementation itself.
"""

import ast
import inspect
from pathlib import Path

from src.aci import (
    classify_no_action_reason,
    expects_canonical_action,
    is_canonical_read_contract,
)


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


def test_production_runtime_does_not_import_legacy_contract_modules():
    """Legacy projections stay behind the loop compatibility boundary."""
    repo = Path(__file__).parents[1]
    forbidden = {"src.legacy_domain_contract", "src.legacy_agent_loop"}
    imports = []
    for root_name in ("routes", "src", "core", "services"):
        for path in (repo / root_name).rglob("*.py"):
            if path.name in {"agent_loop.py", "aci.py", "legacy_agent_loop.py", "legacy_domain_contract.py"}:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                    imports.append(f"{path.relative_to(repo)}:{node.lineno}")
                elif isinstance(node, ast.Import):
                    imports.extend(
                        f"{path.relative_to(repo)}:{node.lineno}"
                        for alias in node.names
                        if alias.name in forbidden
                    )
    assert imports == []


def test_canonical_action_expectation_is_owned_by_aci():
    assert expects_canonical_action(
        answer_only=False, clarification_only=False,
        asset_read_explicit=True, read_binding="manage_assets",
        read_action="list", operation_class="READ",
    ) is True


def test_no_action_failure_classification_is_owned_by_aci():
    base = {
        "expected": True,
        "read_binding": "manage_assets",
        "operation_class": "READ",
        "disabled_tools": (),
    }
    assert classify_no_action_reason(**base, tool_events=[]) == "MODEL_PROSE_ONLY"
    assert classify_no_action_reason(
        **base, tool_events=[{"approval_required": True}]
    ) == "APPROVAL_REQUIRED"
    assert classify_no_action_reason(
        **base, tool_events=[{"blocked": True}]
    ) == "POLICY_DENIED"
    assert classify_no_action_reason(
        **base, tool_events=[{"exit_code": 1}]
    ) == "EXECUTION_FAILED"
    assert classify_no_action_reason(
        **base, tool_events=[{"exit_code": 0, "success": True}]
    ) is None


def test_canonical_read_contract_eligibility_is_owned_by_aci():
    frame = {"operation_class": "READ", "read_explicit": True}
    contract = {"binding": "manage_assets", "action_id": "list"}
    assert is_canonical_read_contract(frame, contract) is True
    assert is_canonical_read_contract(frame, {"binding": "", "action_id": "list"}) is False
    assert is_canonical_read_contract(
        {"operation_class": "EXECUTE", "read_explicit": True}, contract
    ) is False


def test_canonical_runtime_defaults_to_aci_and_historical_name_is_compatibility_adapter():
    from src import agent_loop

    parameter = inspect.signature(agent_loop.stream_aci_runtime).parameters["aci_mode"]
    assert parameter.default == "aci"
    assert agent_loop.stream_agent_loop is not agent_loop.stream_aci_runtime
    assert agent_loop.stream_agent_loop.__name__ == "stream_agent_loop"
    assert expects_canonical_action(
        answer_only=True, clarification_only=False,
        asset_read_explicit=True, read_binding="manage_assets",
        read_action="list", operation_class="EXECUTE",
    ) is False
    assert expects_canonical_action(
        answer_only=False, clarification_only=False,
        asset_read_explicit=False, read_binding=None, read_action=None,
        operation_class="RESEARCH",
    ) is True


def test_legacy_runtime_imports_are_limited_to_owner_facing_tool_metadata():
    """Production runtime must not import descriptive metadata from the loop."""
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
    assert imports == []


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
        "_run_verifier_subagent",
        "_usage_bucket_summary",
        "_build_actions_snapshot",
        "_prepend_agent_directive",
        "_asset_read_request",
        "_looks_like_local_computer_request",
        "_minimal_odysseus_doc_messages",
        "_detect_admin_intent",
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
