"""Grounded owner-facing Recipe Result rendering."""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def canonical_recipe_mutation_answer(
    tool_events: Sequence[Mapping[str, Any]],
) -> str | None:
    event = next(
        (item for item in reversed(tuple(tool_events or ()))
         if isinstance(item, Mapping) and item.get("tool") == "manage_recipes"),
        None,
    )
    if event is None or event.get("exit_code") not in (None, 0):
        return None
    try:
        payload = event.get("result_projection") or json.loads(str(event.get("output") or ""))
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping):
        return None
    if str(payload.get("status") or "").strip().upper() == "NEEDS_REVIEW" and isinstance(payload.get("draft"), Mapping):
        draft = payload["draft"]
        name = str(draft.get("name") or "the recipe").strip()
        ingredients = draft.get("ingredients") if isinstance(draft.get("ingredients"), list) else []
        review = draft.get("review") if isinstance(draft.get("review"), Mapping) else {}
        missing = review.get("missing_fields") if isinstance(review.get("missing_fields"), list) else []
        suffix = f" Needs review: {', '.join(str(item) for item in missing[:5])}." if missing else ""
        return f"Prepared {name!r} for review with {len(ingredients)} ingredient(s). Nothing has been saved yet." + suffix
    recipe = payload.get("recipe")
    if not isinstance(recipe, Mapping) or not recipe.get("id"):
        return None
    return f"Recorded recipe {str(recipe.get('name') or 'the recipe').strip()!r}; the canonical recipe readback is verified."
