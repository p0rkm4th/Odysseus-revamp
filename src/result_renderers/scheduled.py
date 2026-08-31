from __future__ import annotations
import json
from typing import Any, Mapping, Sequence

def _event(tool_events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    event = next((item for item in reversed(tuple(tool_events or ())) if isinstance(item, Mapping) and item.get("tool") == "manage_tasks"), None)
    return event if event and event.get("exit_code") in (None, 0) else None

def _request(event: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        value = json.loads(str(event.get("command") or "{}"))
    except (TypeError, ValueError):
        value = {}
    return value if isinstance(value, Mapping) else {}

def canonical_scheduled_task_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    event = _event(tool_events)
    request = _request(event) if event else {}
    if str(request.get("action") or "").strip().lower() != "list":
        return None
    return str(event.get("output") or "").strip() or "No scheduled reminders found."

def canonical_scheduled_task_mutation_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    event = _event(tool_events)
    if event is None or event.get("success") is False:
        return None
    request = _request(event)
    if str(request.get("action") or "").strip().lower() != "create":
        return None
    title = str(event.get("task_name") or request.get("name") or request.get("prompt") or "the reminder").strip()
    schedule = str(request.get("schedule") or "daily").strip()
    return f'Scheduled reminder: "{title}" ({schedule}, {request.get("scheduled_time", "09:00")}). It is saved.'
