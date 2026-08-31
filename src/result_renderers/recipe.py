"""Grounded owner-facing Recipe Result rendering."""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

def canonical_recipe_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render recipe/stock-coverage reads from Inventory Service evidence."""
    event = next(
        (item for item in reversed(tuple(tool_events or ()))
         if isinstance(item, Mapping) and str(item.get("tool") or "").strip() == "read_recipes"),
        None,
    )
    if event is None or event.get("exit_code") not in (None, 0):
        return None
    try:
        payload = json.loads(str(event.get("output") or ""))
        command = json.loads(str(event.get("command") or "{}"))
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping):
        return None
    status = str(payload.get("status") or "").strip().upper()
    if status in {"FAILED", "UNAVAILABLE", "INVALID_RESULT", "ERROR"}:
        return None
    action = str(command.get("action") or "list").strip().casefold() if isinstance(command, Mapping) else "list"
    if action == "prepare_import":
        if status == "NEEDS_REVIEW":
            review = payload.get("review") if isinstance(payload.get("review"), Mapping) else {}
            missing = review.get("missing_fields") if isinstance(review.get("missing_fields"), list) else []
            suffix = f" Missing or ambiguous: {', '.join(str(item) for item in missing[:5])}." if missing else ""
            return "I found the recipe source, but it needs review before anything can be saved." + suffix
        draft = payload.get("draft")
        if not isinstance(draft, Mapping):
            return None
        name = str(draft.get("name") or "the recipe").strip()
        ingredients = draft.get("ingredients") if isinstance(draft.get("ingredients"), list) else []
        return f"Prepared {name!r} as an unpersisted draft with {len(ingredients)} ingredient(s). Review it before committing."
    if action == "get":
        recipe = payload.get("recipe")
        if not isinstance(recipe, Mapping):
            return None
        name = str(recipe.get("name") or "the recipe").strip()
        lines = [f"{name} ({recipe.get('servings', 1)} servings):"]
        ingredients = recipe.get("ingredients") if isinstance(recipe.get("ingredients"), list) else []
        if ingredients:
            lines.append("Ingredients:")
            for item in ingredients[:100]:
                if not isinstance(item, Mapping):
                    continue
                kind = str(item.get("amount_kind") or "EXACT").upper()
                source = str(item.get("source_text") or "").strip()
                if kind in {"TO_TASTE", "AS_NEEDED", "OPTIONAL", "UNSPECIFIED", "NOMINAL"}:
                    amount = source or str(item.get("modifier") or kind.lower().replace("_", " "))
                    line = f"- {amount}"
                    if source and str(item.get("name") or "").casefold() not in source.casefold():
                        line += f" {item.get('name')}"
                elif kind == "RANGE" and item.get("quantity_min") is not None:
                    line = f"- {item.get('quantity_min')}-{item.get('quantity_max')} {item.get('unit') or ''} {item.get('name') or 'ingredient'}"
                else:
                    line = f"- {item.get('quantity')} {item.get('unit') or ''} {item.get('name') or 'ingredient'}"
                lines.append(line.strip())
        notes = str(recipe.get("notes") or "").strip()
        if notes:
            lines.extend(["Notes:", notes])
        instructions = str(recipe.get("instructions") or "").strip()
        if instructions:
            lines.extend(["Instructions:", instructions])
        return "\n".join(lines)
    if action == "can_make":
        can_make = payload.get("can_make")
        shortages = payload.get("shortages") if isinstance(payload.get("shortages"), list) else []
        if can_make is True:
            return "The canonical pantry check says this recipe can be made with the recorded stock."
        names = [str(item.get("name") or "ingredient") for item in shortages if isinstance(item, Mapping)]
        suffix = f" Missing: {', '.join(names[:20])}." if names else ""
        return "The canonical pantry check says this recipe cannot be made from the recorded stock." + suffix
    if action == "shopping_requirements":
        missing = payload.get("missing_ingredients")
        if not isinstance(missing, list):
            return None
        recipe_name = str(payload.get("recipe_name") or "this recipe").strip()
        if not missing:
            return f"You have the recorded ingredients needed for {recipe_name}. Nothing needs to be added to the shopping list."
        lines = [f"For {recipe_name}, you still need:"]
        for item in missing[:50]:
            if isinstance(item, Mapping):
                quantity = item.get("quantity")
                unit = str(item.get("unit") or "").strip()
                name = str(item.get("name") or "ingredient").strip()
                kind = str(item.get("amount_kind") or "EXACT").upper()
                if kind in {"TO_TASTE", "AS_NEEDED", "OPTIONAL", "UNSPECIFIED", "NOMINAL"}:
                    amount = str(item.get("modifier") or kind.lower().replace("_", " "))
                elif kind == "RANGE" and item.get("quantity_min") is not None and item.get("quantity_max") is not None:
                    amount = f"{item['quantity_min']}-{item['quantity_max']} {unit}".strip()
                else:
                    amount = f"{quantity} {unit}".strip()
                    if kind == "APPROXIMATE": amount = f"about {amount}"
                lines.append(f"- {name} — {amount}".strip())
        return "\n".join(lines)
    if action == "scale":
        ingredients = payload.get("scaled_ingredients")
        if not isinstance(ingredients, list) or not payload.get("servings"):
            return None
        lines = [f"Scaled {str(payload.get('recipe_name') or 'recipe')} to {payload['servings']} servings:"]
        for ingredient in ingredients[:100]:
            if isinstance(ingredient, Mapping):
                kind = str(ingredient.get("amount_kind") or "EXACT").upper()
                name = str(ingredient.get("name") or "ingredient").strip()
                source = str(ingredient.get("source_text") or "").strip()
                if kind in {"TO_TASTE", "AS_NEEDED", "OPTIONAL", "UNSPECIFIED", "NOMINAL"}:
                    amount = source or str(ingredient.get("modifier") or kind.lower().replace("_", " "))
                elif kind == "RANGE" and ingredient.get("quantity_min") is not None and ingredient.get("quantity_max") is not None:
                    amount = f"{ingredient['quantity_min']}-{ingredient['quantity_max']} {ingredient.get('unit') or ''}".strip()
                else:
                    amount = f"{ingredient.get('quantity')} {ingredient.get('unit') or ''}".strip()
                    if kind == "APPROXIMATE": amount = f"about {amount}"
                lines.append(f"- {amount} {name}".strip())
        return "\n".join(lines)
    if action == "expiring_candidates":
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            return None
        if not candidates:
            return "No recorded recipes use ingredients that expire within the requested window."
        lines = ["Recipes using ingredients that are expiring soon:"]
        for candidate in candidates[:50]:
            if not isinstance(candidate, Mapping):
                continue
            name = str(candidate.get("recipe_name") or "Unnamed recipe")
            status = "can make" if candidate.get("can_make") is True else "missing ingredients"
            lines.append(f"- {name} ({status})")
            shortages = candidate.get("shortages")
            if isinstance(shortages, list) and shortages:
                missing = ", ".join(
                    str(row.get("name") or "ingredient")
                    for row in shortages[:12] if isinstance(row, Mapping)
                )
                if missing:
                    lines.append(f"  Missing: {missing}")
        return "\n".join(lines)
    if action == "pantry_candidates":
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            return None
        if not candidates:
            return "No recorded recipes are available to check against your current stock."
        makeable = [item for item in candidates if isinstance(item, Mapping) and item.get("can_make") is True]
        lines = [f"I checked {len(candidates)} recorded recipe{'s' if len(candidates) != 1 else ''} against your current stock."]
        if makeable:
            lines.append("You can make:")
            for candidate in makeable[:20]:
                lines.append(f"- {str(candidate.get('recipe_name') or 'Unnamed recipe')}")
        missing = [item for item in candidates if isinstance(item, Mapping) and item.get("can_make") is not True]
        if missing:
            if makeable:
                lines.append("")
            lines.append("Needs ingredients:")
            for candidate in missing[:20]:
                name = str(candidate.get("recipe_name") or "Unnamed recipe")
                shortages = candidate.get("shortages") if isinstance(candidate.get("shortages"), list) else []
                names = ", ".join(str(row.get("name") or "ingredient") for row in shortages[:8] if isinstance(row, Mapping))
                lines.append(f"- {name}" + (f" (missing: {names})" if names else ""))
        return "\n".join(lines)
    if action == "cooking_history":
        events = payload.get("events")
        if not isinstance(events, list):
            return None
        if not events:
            return "I don't have any recorded cooking history, so I can't identify a recipe cooked last night."
        return f"I found {len(events)} recorded cooking event{'s' if len(events) != 1 else ''}."
    recipes = payload.get("recipes")
    if not isinstance(recipes, list):
        recipe = payload.get("recipe")
        recipes = [recipe] if isinstance(recipe, Mapping) else None
    if recipes is None:
        return None
    if not recipes:
        return "No recipes are recorded for this owner."
    lines = [f"I found {len(recipes)} recorded recipe{'s' if len(recipes) != 1 else ''}:"]
    for recipe in recipes[:50]:
        if not isinstance(recipe, Mapping):
            continue
        name = str(recipe.get("name") or "Unnamed recipe").strip()
        servings = recipe.get("servings")
        suffix = f" ({servings} servings)" if servings not in (None, "") else ""
        lines.append(f"- {name}{suffix}")
    return "\n".join(lines)




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
