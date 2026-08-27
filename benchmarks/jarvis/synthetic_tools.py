"""Non-persistent tool backend for synthetic Jarvis benchmark execution."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
import json
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
        response.setdefault("success", not bool(response.get("error")))
        return f"{name}: synthetic fixture", response


def fixtures_for_case(case: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build the minimum allowlisted fixture set declared by a suite case."""
    expected = case.get("expected", {})
    names = set(expected.get("required_tools", []))
    names.update(
        item.get("name") for item in expected.get("tool_args", [])
        if isinstance(item, Mapping) and item.get("name")
    )
    # Older imported ACI/metamorphic cases describe the semantic owner in
    # ``family``/``concept`` rather than carrying an explicit tool fixture.
    # Keep that legacy contract equivalent to the newer typed fixture shape:
    # a canonical Work read gets a structured, empty Work Result instead of
    # falling through to the unknown-tool failure fixture.  This is evaluator
    # plumbing only; production Action selection and policy remain unchanged.
    concept = str(expected.get("concept") or "").strip().upper()
    family = str(case.get("family") or "").strip().casefold()
    if concept == "WORK" or family == "work":
        names.add("read_work")
    fixtures: dict[str, list[dict[str, Any]]] = {}
    for name in names:
        tool = str(name)
        # Canonical owner reads must exercise the same structured-result
        # contract as production. A prose placeholder would make the real
        # renderer (correctly) reject the fixture and turn a valid empty read
        # into a misleading completion failure.
        if tool == "read_memory":
            fixtures[tool] = [{
                "data": {
                    "status": "zero_result", "query_type": "summary",
                    "records": [], "retrieved_count": 0,
                },
                "output": "{}", "exit_code": 0, "success": True,
            }]
        elif tool == "read_work":
            fixtures[tool] = [{
                "data": {
                    "status": "SUCCESS_EMPTY", "goals": [], "projects": [],
                    "tasks": [], "runs": [], "commitments": [],
                },
                "output": json.dumps({
                    "status": "SUCCESS_EMPTY", "goals": [], "projects": [],
                    "tasks": [], "runs": [], "commitments": [],
                }, sort_keys=True),
                "exit_code": 0, "success": True,
            }]
        elif tool == "manage_assets":
            fixtures[tool] = [{
                "output": json.dumps({
                    "status": "OK", "assets": [],
                }, sort_keys=True),
                "exit_code": 0, "success": True,
            }]
        else:
            fixtures[tool] = [{
                "output": "Synthetic tool result.", "exit_code": 0, "success": True,
            }]
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
