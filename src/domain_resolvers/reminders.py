from __future__ import annotations

import re
from typing import Any

def note_mutation_payload(query: str, action: str) -> dict[str, Any] | None:
    normalized_action = str(action or "").strip().casefold()
    if normalized_action == "update":
        correction = re.search(
            r"\b(?:actually|no|wait)\b.{0,48}\bmake\s+that\s+"
            r"(?P<when>.+?)\s+instead\b",
            str(query or "").strip(), re.IGNORECASE,
        )
        if correction:
            when = correction.group("when").strip(" .,:;\"'")
            if when and re.search(
                r"\b(?:today|tomorrow|tonight|morning|afternoon|evening|"
                r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
                r"hour|hours|minute|minutes|week|next\s+week)\b",
                when, re.IGNORECASE,
            ):
                return {"action": "update", "due_date": when[:200]}
        return None
    if normalized_action != "add":
        return None
    text = re.sub(r"\s+", " ", str(query or "").strip())
    match = re.search(
        r"\bremind\s+me\s+(?P<when>.+?)\s+to\s+(?P<title>.+?)\s*[.!?]?$",
        text, re.IGNORECASE,
    )
    if not match:
        return None
    when = match.group("when").strip(" .,:;")
    title = match.group("title").strip(" .:;\"'")
    if not title or not re.search(
        r"\b(?:today|tomorrow|tonight|morning|afternoon|evening|hour|hours|minute|minutes|day|days|week|weeks|at|on)\b",
        when, re.IGNORECASE,
    ):
        return None
    title = title[:500]
    title = title[:1].upper() + title[1:]
    return {"action": "add", "title": title, "due_date": when[:200]}

def scheduled_task_create_payload(query: str) -> dict[str, Any] | None:
    text = re.sub(r"\s+", " ", str(query or "").strip())
    match = re.search(
        r"\b(?:every|each)\s+(?P<period>morning|afternoon|evening|day|weekday|week)\b"
        r".{0,80}?\bremind\s+me\s+to\s+(?P<title>.+?)\s*[.!?]?$",
        text, re.IGNORECASE,
    )
    if not match:
        return None
    period = match.group("period").lower()
    title = match.group("title").strip(" .:;\"'")
    if not title:
        return None
    title = title[:500]
    title = title[:1].upper() + title[1:]
    return {
        "action": "create", "name": title, "prompt": title,
        "task_type": "llm", "trigger_type": "schedule",
        "schedule": "weekly" if period == "week" else "daily",
        "scheduled_time": "09:00",
    }
