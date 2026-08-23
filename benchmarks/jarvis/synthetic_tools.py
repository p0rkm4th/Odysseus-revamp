"""Non-persistent tool backend for synthetic Jarvis benchmark execution."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any


class SyntheticToolExecutor:
    """Return controlled fixtures without importing or touching app stores.

    The callable matches ``execute_tool_block``. Unknown tools fail closed so a
    newly introduced capability cannot silently become active in benchmarks.
    Per-tool response lists enable deterministic transient-failure scenarios.
    """

    def __init__(self, responses: Mapping[str, list[Mapping[str, Any]]]):
        self._responses = {
            str(name): [dict(item) for item in items]
            for name, items in responses.items()
        }
        self.calls: list[dict[str, str]] = []
        self._counts: Counter[str] = Counter()

    async def __call__(self, block: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        name = str(getattr(block, "tool_type", "") or "")
        content = str(getattr(block, "content", "") or "")
        self.calls.append({"name": name, "content": content})
        index = self._counts[name]
        self._counts[name] += 1
        fixtures = self._responses.get(name)
        if not fixtures:
            return (
                f"{name}: BLOCKED",
                {
                    "error": "Tool is unavailable in this synthetic benchmark fixture.",
                    "exit_code": 1,
                    "blocked": True,
                    "policy": "synthetic_fixture_allowlist",
                },
            )
        response = dict(fixtures[min(index, len(fixtures) - 1)])
        response.setdefault("exit_code", 0 if not response.get("error") else 1)
        return f"{name}: synthetic fixture", response


def fixtures_for_case(case: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build the minimum allowlisted fixture set declared by a suite case."""
    expected = case.get("expected", {})
    names = set(expected.get("required_tools", []))
    names.update(
        item.get("name") for item in expected.get("tool_args", [])
        if isinstance(item, Mapping) and item.get("name")
    )
    fixtures = {
        str(name): [{"output": "Synthetic tool result.", "exit_code": 0}]
        for name in names
    }
    if expected.get("requires_recovery"):
        # Recovery cases may select different read tools. The suite driver must
        # explicitly name its fixture tool instead of gaining broad authority.
        recovery_tool = case.get("fixture_tool")
        if recovery_tool:
            fixtures[str(recovery_tool)] = [
                {"error": "Synthetic transient timeout.", "exit_code": 1},
                {"output": "Synthetic retry succeeded.", "exit_code": 0},
            ]
    return fixtures
