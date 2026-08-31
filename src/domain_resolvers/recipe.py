"""Bounded owner-facing recipe field extraction.

These helpers extract evidence for recipe import and naming.  They do not
select capabilities, validate a draft, persist a recipe, or execute work.
"""

from __future__ import annotations

import re
from typing import Any, Mapping


def apply_owner_transformations(draft: Any, transformations: Any) -> Any:
    if not isinstance(transformations, list):
        return draft
    ingredients = [dict(item) for item in draft.ingredients]
    notes, name, servings = draft.notes, draft.name, draft.servings
    def targets(value: Any) -> set[str]:
        text = re.sub(r"\s+", " ", str(value or "").strip().casefold())
        return {part.strip(" .\"'") for part in re.split(r"\s+and\s+|\s*,\s*|\s*&\s*", text) if part.strip()}
    def matches(item: Mapping[str, Any], wanted: set[str]) -> bool:
        current = re.sub(r"\s+", " ", str(item.get("name") or "").strip().casefold())
        return current in wanted or any(current.startswith(f"{v} ") or v.startswith(f"{current} ") for v in wanted)

    for transformation in transformations:
        if not isinstance(transformation, Mapping):
            continue
        operation = str(transformation.get("operation") or transformation.get("type") or "").strip().casefold().replace("-", "_")
        wanted = targets(transformation.get("ingredient") or transformation.get("ingredients"))
        if operation in {"exclude", "remove", "omit"} and wanted:
            ingredients = [item for item in ingredients if not matches(item, wanted)]
        elif operation in {"optional", "mark_optional"} and wanted:
            for item in ingredients:
                if matches(item, wanted):
                    item.update(optional=True, amount_kind="OPTIONAL", quantity=None, unit=None)
        elif operation in {"replace", "substitute"} and wanted:
            replacement = str(transformation.get("replacement") or transformation.get("with") or "").strip()[:200]
            if replacement:
                for item in ingredients:
                    if matches(item, wanted):
                        item["name"] = replacement
                        item["source_text"] = item.get("source_text") or replacement
        elif operation in {"add_note", "note", "move_to_note"}:
            note = str(transformation.get("note") or transformation.get("text") or "").strip()
            if note and note.casefold() not in (notes or "").casefold():
                notes = f"{notes}\n{note}".strip() if notes else note
        elif operation in {"rename", "change_name"}:
            value = str(transformation.get("name") or transformation.get("value") or "").strip()
            if value:
                name = value[:200]
        elif operation in {"change_servings", "servings"}:
            try:
                value = float(transformation.get("servings") or transformation.get("value"))
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                servings = int(value) if value.is_integer() else value
    if not ingredients:
        raise ValueError("owner transformations removed every recipe ingredient")
    return draft.__class__(name, servings, tuple(ingredients), draft.instructions,
                           notes, draft.source_url, draft.provenance)


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
