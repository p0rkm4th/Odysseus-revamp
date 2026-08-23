"""Deterministic, synthetic conversation fixtures for Jarvis cases."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from benchmarks.jarvis.core import BenchmarkFormatError


def build_case_messages(case: Mapping[str, Any]) -> list[dict[str, str]]:
    fixture = case.get("context_fixture")
    if fixture is None:
        return [{"role": "user", "content": str(case["prompt"])}]
    if not isinstance(fixture, Mapping):
        raise BenchmarkFormatError("context_fixture must be an object")
    fixture_type = fixture.get("type")
    if fixture_type != "latest_constraint":
        raise BenchmarkFormatError(f"unsupported context fixture: {fixture_type!r}")

    old = str(fixture.get("superseded") or "").strip()
    latest = str(fixture.get("latest") or "").strip()
    filler_turns = fixture.get("filler_turns", 32)
    if not old or not latest:
        raise BenchmarkFormatError("latest_constraint fixture needs superseded and latest")
    if not isinstance(filler_turns, int) or not 1 <= filler_turns <= 200:
        raise BenchmarkFormatError("context_fixture.filler_turns must be 1..200")

    messages = [
        {"role": "user", "content": f"For the final check, the code word is {old}."},
        {"role": "assistant", "content": f"Understood. The current code word is {old}."},
    ]
    for index in range(filler_turns):
        messages.extend([
            {
                "role": "user",
                "content": (
                    f"Synthetic planning note {index + 1}: item {(index % 7) + 1} "
                    "is informational and does not change the final-check constraint."
                ),
            },
            {
                "role": "assistant",
                "content": f"Noted synthetic planning item {index + 1}.",
            },
        ])
    messages.extend([
        {
            "role": "user",
            "content": f"Correction: replace the earlier code word. The latest code word is {latest}.",
        },
        {"role": "assistant", "content": f"Understood. I will use {latest}."},
        {"role": "user", "content": str(case["prompt"])},
    ])
    return messages
