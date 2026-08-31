"""Bounded owner-facing recipe field extraction.

These helpers extract evidence for recipe import and naming.  They do not
select capabilities, validate a draft, persist a recipe, or execute work.
"""

from __future__ import annotations

import re


def requested_name(query: str) -> str | None:
    """Extract an explicit owner naming override for an import proposal."""
    text = str(query or "")
    patterns = (
        r"(?mi)^\s*video\s+title\s*:\s*(?P<name>[^\n]{1,200})\s*$",
        r"\bas\s+[\"'](?P<name>[^\"']{1,200})[\"']\s*[:.]?",
        r"\bas\s+(?P<name>(?!(?:needed|desired|necessary)\b)[A-Z][^\.\n]{1,200})\s*\.",
        r"\bfor\s+the\s+name\s*,?\s*use\s+[\"'](?P<name>[^\"']{1,200})[\"']",
        r"\b(?:called|named)\s+[\"']?(?P<name>[^\"'\n:.]{1,200})[\"']?\s*[:.]",
        r"\b(?:add|save|create)\s+(?:a\s+)?recipe\s+(?P<name>[^\n:.]{1,200})\s*\."
        r"(?=\s*(?:ingredients?|instructions?)\b)",
        r"\brecipe\b(?:\s+(?:to\s+)?(?:my\s+)?recipes?)?\s*:\s*"
        r"(?P<name>.+?)(?=\.\s*ingredients\s*:|\s+ingredients\s*:|\n\s*ingredients\s*:)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            name = " ".join(match.group("name").strip().strip("\"'").split())
            if name:
                return name[:200]
    return None


def source_url(query: str) -> str | None:
    """Extract the bounded public source URL from a recipe request."""
    match = re.search(r"https?://[^\s)>]+", str(query or ""), re.IGNORECASE)
    return match.group(0).rstrip(".,") if match else None
