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


def test_production_runtime_has_canonical_aci_stream_callers():
    calls = _runtime_calls("stream_aci_turn")
    assert len(calls) >= 6, calls


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
