"""Grounded owner-facing renderers for canonical Memory Results."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def canonical_memory_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render a protected Memory projection without exposing its telemetry."""
    event = next(
        (item for item in reversed(tuple(tool_events or ()))
         if isinstance(item, Mapping) and str(item.get("tool") or "").strip() == "read_memory"),
        None,
    )
    if event is None:
        return None
    projection = event.get("result_projection")
    if not isinstance(projection, Mapping):
        return None
    status = str(projection.get("status") or "retrieval_failed").strip().casefold()
    if status == "retrieval_failed":
        return "I couldn't retrieve your remembered information, so I won't infer any personal facts."
    if status == "owner_required":
        return "I need your authenticated owner session to retrieve remembered information."
    records = [record for record in (projection.get("records") or []) if isinstance(record, Mapping)]
    if status == "zero_result" or not records:
        return "I don't have any applicable memories recorded for you."
    lines = ["Here's what I remember:"]
    for record in records[:100]:
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        marker = "Previously recorded" if str(record.get("epistemic_type") or "").upper() == "HISTORICAL" else "Remembered"
        lines.append(f"- {marker}: {text}")
    omitted = int(projection.get("omitted_count") or 0)
    if omitted:
        lines.append(f"- {omitted} more remembered item{'s' if omitted != 1 else ''} are available.")
    return "\n".join(lines) if len(lines) > 1 else "I don't have any applicable memories recorded for you."


def canonical_memory_mutation_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render one verified, human-readable owner Memory mutation answer."""
    event = next(
        (item for item in reversed(tuple(tool_events or ()))
         if isinstance(item, Mapping) and str(item.get("tool") or "").strip() == "manage_memory"),
        None,
    )
    if event is None or event.get("exit_code") not in (None, 0):
        return None
    try:
        request = json.loads(str(event.get("command") or "{}"))
    except (TypeError, ValueError):
        request = {}
    payload = event.get("result_projection")
    if not isinstance(payload, Mapping):
        try:
            payload = json.loads(str(event.get("output") or "{}"))
        except (TypeError, ValueError):
            payload = {}
    if not isinstance(request, Mapping) or not isinstance(payload, Mapping):
        return None
    if event.get("success") is False or payload.get("success") is False:
        return None
    verification = payload.get("verification")
    if not isinstance(verification, Mapping) or verification.get("status") != "VERIFIED":
        return None
    action = str(request.get("action") or "").strip().lower()
    if action == "add":
        return "Remembered that for you; the canonical Memory readback is verified."
    if action == "edit":
        return "Updated that memory; the canonical Memory readback is verified."
    if action == "delete":
        return "Removed that memory; the canonical Memory readback is verified."
    return None

