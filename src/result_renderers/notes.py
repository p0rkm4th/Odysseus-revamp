"""Grounded owner-facing Notes and reminder Result rendering."""
from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence


def note_list_summary_from_tool_output(raw: str, max_items: int = 20) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return ""
    titles: list[str] = []
    for line in raw.splitlines():
        match = re.match(r"^\s*-\s+\[[^\]]+\]\s+\*\*(.*?)\*\*(.*)$", line)
        if not match:
            continue
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        suffix = re.sub(r"\s+", " ", match.group(2) or "").strip()
        label = f"{title} {suffix}".strip()
        if label:
            titles.append(label)
        if len(titles) >= max_items:
            break
    if not titles:
        if re.search(r"\b(no notes|0 notes|found 0)\b", raw, re.IGNORECASE):
            return "No notes found."
        return ""
    total = len(re.findall(r"^\s*-\s+\[[^\]]+\]\s+\*\*", raw, re.MULTILINE))
    heading_count = total or len(titles)
    lines = [f"Here are your notes ({heading_count}):"]
    lines.extend(f"- {title}" for title in titles)
    if total and total > len(titles):
        lines.append(f"- ...and {total - len(titles)} more")
    return "\n".join(lines)


def _latest_notes_event(tool_events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    return next(
        (item for item in reversed(tuple(tool_events or ()))
         if isinstance(item, Mapping) and str(item.get("tool") or "").strip() == "manage_notes"),
        None,
    )


def canonical_notes_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    event = _latest_notes_event(tool_events)
    if event is None or event.get("exit_code") not in (None, 0):
        return None
    try:
        request = json.loads(str(event.get("command") or "{}"))
    except (TypeError, ValueError):
        request = {}
    if not isinstance(request, Mapping) or str(request.get("action") or "").strip().lower() not in {"list", "search", "find", "view"}:
        return None
    return note_list_summary_from_tool_output(str(event.get("output") or "").strip()) or "No notes found."


def canonical_notes_mutation_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    event = _latest_notes_event(tool_events)
    if event is None or event.get("exit_code") not in (None, 0) or not event.get("note_id"):
        return None
    try:
        request = json.loads(str(event.get("command") or "{}"))
    except (TypeError, ValueError):
        request = {}
    action = str(request.get("action") or "").strip().lower() if isinstance(request, Mapping) else ""
    title = str(event.get("note_title") or "").strip()
    due = str(event.get("due_date") or "").strip()
    if isinstance(request, Mapping):
        title = title or str(request.get("title") or "").strip()
        due = due or str(request.get("due_date") or "").strip()
    if action == "add" and title:
        suffix = f" for {due}" if due else ""
        return f'Reminder created: "{title}"{suffix}. It is saved.'
    if action == "update" and title:
        suffix = f" for {due}" if due else ""
        return f'Reminder updated: "{title}"{suffix}. It is saved.'
    if action == "delete":
        return "Reminder deleted."
    return None
