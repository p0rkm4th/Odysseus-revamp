"""Bounded field extraction for canonical Memory mutations."""

from __future__ import annotations

import re
from typing import Any


def memory_mutation_payload(query: str, action: str) -> dict[str, Any] | None:
    """Project owner memory wording into fields; never resolve or mutate state."""
    text = re.sub(r"\s+", " ", str(query or "").strip())
    operation = str(action or "").strip().casefold()
    if operation == "add":
        match = re.search(r"\bremember(?:\s+that)?\s+(.+?)\s*[.!?]?$", text, re.IGNORECASE)
        value = match.group(1).strip() if match else ""
        return {"action": "add", "text": value[:5000], "category": "fact"} if value else None
    if operation != "delete":
        return None
    match = re.search(r"\b(?:forget|delete|remove)\s+(?:my|the|this|that)?\s*(.+?)\s*[.!?]?$", text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
    else:
        property_match = re.search(
            r"\bwhat(?:'s|\s+is)\s+(?:my|our)\s+([a-z][a-z0-9 _-]{1,80}?)(?:\s+now)?\s*[?!.]",
            text, re.IGNORECASE,
        ) or re.search(
            r"\bremember(?:\s+that)?\s+(?:my|our)\s+([a-z][a-z0-9 _-]{1,80}?)\s+is\b",
            text, re.IGNORECASE,
        )
        value = property_match.group(1).strip() if property_match else ""
    return {"action": "delete", "query": value[:200]} if value else None
