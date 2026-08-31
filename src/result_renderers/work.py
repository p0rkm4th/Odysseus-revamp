"""Grounded owner-facing renderers for canonical Work Results.

These functions only project verified executor output.  They do not select
Actions, mutate state, or infer success from model prose.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def canonical_work_mutation_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render only a verified Work mutation; model prose is not evidence."""
    event = next(
        (item for item in reversed(tuple(tool_events or ()))
         if isinstance(item, Mapping) and str(item.get("tool") or "").strip() == "manage_work"),
        None,
    )
    if event is None or event.get("exit_code") not in (None, 0) or event.get("success") is not True:
        return None
    try:
        payload = json.loads(str(event.get("output") or ""))
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping) or payload.get("status") != "VERIFIED":
        return None
    project = payload.get("project")
    if isinstance(project, Mapping) and project.get("id"):
        title = str(project.get("title") or "the project").strip()
        return f"Created project {title!r}; the canonical Work readback is verified."
    task = payload.get("task")
    if isinstance(task, Mapping) and task.get("id"):
        title = str(task.get("title") or "the task").strip()
        project_title = str(payload.get("project_title") or "the named project").strip()
        return f"Created task {title!r} in project {project_title!r}; the canonical Work readback is verified."
    return None


def canonical_work_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render a bounded structured Work read without model synthesis."""
    event = next(
        (item for item in reversed(tuple(tool_events or ()))
         if isinstance(item, Mapping) and str(item.get("tool") or "").strip() == "read_work"),
        None,
    )
    if event is None or event.get("exit_code") not in (None, 0):
        return None
    projection = event.get("result_projection")
    if isinstance(projection, Mapping) and isinstance(projection.get("collections"), Mapping):
        status = str(projection.get("status") or "").strip().upper()
        if status in {"FAILED", "UNAVAILABLE", "INVALID_RESULT", "ERROR"}:
            return None
        counts = {str(key): int(value or 0) for key, value in projection["collections"].items()}
        work_counts = {
            key: value for key, value in counts.items()
            if key in {"goals", "projects", "tasks", "commitments"}
        }
        if work_counts:
            counts = work_counts
        total = sum(counts.values())
        if total == 0:
            return "No outstanding work is recorded for this owner."
        labels = ", ".join(
            f"{key.replace('_', ' ')}={value}"
            for key, value in sorted(counts.items()) if value
        )
        lines = [f"I found {total} work record{'s' if total != 1 else ''} ({labels})."]
        items = projection.get("items")
        if isinstance(items, Mapping):
            for key in sorted(items):
                for item in items[key] if isinstance(items[key], list) else ():
                    if not isinstance(item, Mapping) or not str(item.get("title") or "").strip():
                        continue
                    status = str(item.get("status") or "").strip()
                    lines.append(f"- {item['title']}" + (f" ({status})" if status else ""))
        return "\n".join(lines)
    try:
        payload = json.loads(str(event.get("output") or ""))
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping):
        return None
    status = str(payload.get("status") or "").strip().upper()
    if status in {"FAILED", "UNAVAILABLE", "INVALID_RESULT", "ERROR"}:
        return None
    collections = {str(key): value for key, value in payload.items() if isinstance(value, list)}
    if not collections:
        return None
    # The overview binding includes durable execution Runs. An outstanding
    # work read must not present execution history as owner work.
    work_collections = {
        key: value for key, value in collections.items()
        if key in {"goals", "projects", "tasks", "commitments"}
    }
    if work_collections:
        collections = work_collections
    total = sum(len(value) for value in collections.values())
    if total == 0:
        return "No outstanding work is recorded for this owner."
    labels = ", ".join(
        f"{key.replace('_', ' ')}={len(value)}"
        for key, value in sorted(collections.items()) if value
    )
    return f"I found {total} work record{'s' if total != 1 else ''} ({labels})."

