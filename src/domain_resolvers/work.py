"""Bounded field extraction for canonical Work project/task Actions."""

from __future__ import annotations

import re
from typing import Any


def work_project_create_payload(query: str) -> dict[str, Any] | None:
    """Project only an explicit Work project title into Action fields."""
    text = re.sub(r"\s+", " ", str(query or "").strip())
    match = re.search(
        r"\b(?:create|start|begin)\s+(?:a\s+)?project\s+(?:called|named|for|about)\s+(.+)$",
        text, re.IGNORECASE,
    )
    if not match:
        return None
    title = match.group(1).strip(" .:;\"'")
    return {"action": "create", "title": title, "domain": "general"} if 1 <= len(title) <= 300 else None


def work_task_create_payload(query: str) -> dict[str, Any] | None:
    """Project an explicit task title and optional project reference."""
    text = re.sub(r"\s+", " ", str(query or "").strip())
    match = re.search(
        r"\b(?:create|add|make)\s+(?:a\s+)?task\s+(?:called|named)\s+(.+?)\s+"
        r"(?:in|for)\s+(?:the\s+)?project\s+(.+)$", text, re.IGNORECASE,
    )
    if match:
        title, project = (part.strip(" .:;\"'") for part in match.groups())
        if 1 <= len(title) <= 300 and 1 <= len(project) <= 300:
            return {"action": "create_task", "title": title, "project_title": project}
        return None
    match = re.search(
        r"\b(?:create|add|make)\s+(?:a\s+)?task\s+(?:to|for|about)\s+(.+)$",
        text, re.IGNORECASE,
    )
    if not match:
        return None
    title = match.group(1).strip(" .:;\"'")
    return {"action": "create_task", "title": title} if 1 <= len(title) <= 300 else None
