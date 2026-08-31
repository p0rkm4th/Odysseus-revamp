"""Grounded owner-facing renderers for scheduled reminders."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def canonical_scheduled_task_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render the existing scheduler list as a deterministic owner answer."""
    event = next(
        (item for item in reversed(tuple(tool_events or ()))
         if isinstance(item, Mapping) and str(item.get("tool") or "").strip() == "manage_tasks"),
        None,
    )
    if event is None or event.get("exit_code") not in (None, 0):
        return None
    try:
        request = json.loads(str(event.get("command") or "{}"))
    except (TypeError, ValueError):
        request = {}
    if not isinstance(request, Mapping) or str(request.get("action") or "").strip().lower() != "list":
        return None
    return str(event.get("output") or "").strip() or "No scheduled reminders found."


def canonical_scheduled_task_mutation_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render a successful scheduled reminder from the scheduler Result."""
    event = next(
        (item for item in reversed(tuple(tool_events or ()))
         if isinstance(item, Mapping) and str(item.get("tool") or "").strip() == "manage_tasks"),
        None,
    )
    if event is None or event.get("exit_code") not in (None, 0) or event.get("success") is False:
        return None
    try:
        request = json.loads(str(event.get("command") or "{}"))
    except (TypeError, ValueError):
        request = {}
    if not isinstance(request, Mapping) or str(request.get("action") or "").strip().lower() != "create":
        return None
    title = str(event.get("task_name") or request.get("name") or request.get("prompt") or "the reminder").strip()
    schedule = str(request.get("schedule") or "daily").strip()
    return f'Scheduled reminder: "{title}" ({schedule}, {request.get("scheduled_time", "09:00")}). It is saved.'
