"""Generic schema-field resolution for canonical Action payloads.

Resolvers propose validated fields only. They never select capabilities,
authorize Actions, execute tools, or persist state.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable


FieldResolver = Callable[[str, Mapping[str, Any]], Mapping[str, Any] | None]


def _scheduled_task_fields(query: str, _frame: Mapping[str, Any]) -> Mapping[str, Any] | None:
    from src.intent_contracts import scheduled_task_create_payload

    return scheduled_task_create_payload(query)


def _recipe_fields(query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    from src.intent_contracts import recipe_create_payload, recipe_requested_name, recipe_source_url

    filters = frame.get("filters") if isinstance(frame.get("filters"), Mapping) else {}
    draft = recipe_create_payload(query)
    if draft:
        return draft
    url = str(filters.get("recipe_source_url") or "").strip() or recipe_source_url(query)
    name = str(filters.get("recipe_requested_name") or "").strip() or recipe_requested_name(query)
    if url:
        return {"action": "commit_import", "source_url": url, **({"requested_name": name} if name else {})}
    if action_id in {"add", "commit_import"}:
        return {
            "review_required": True, "source_text": query,
            **({"requested_name": name} if name else {}),
            "review_reason": "Recipe text needs review before saving; one or more ingredients has no exact amount. Nothing was saved.",
        }
    return None


def _reference_id(frame: Mapping[str, Any]) -> str | None:
    resolution = frame.get("reference_resolution")
    refs = resolution.get("refs") if isinstance(resolution, Mapping) else None
    return str(refs[0]).strip() if isinstance(refs, list) and len(refs) == 1 and str(refs[0]).strip() else None


def _inventory_fields(query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    from src.intent_contracts import inventory_add_item_payload, inventory_consume_stock_payload, inventory_move_item_payload

    ref = _reference_id(frame)
    resolver = {"add_item": inventory_add_item_payload, "consume_stock": inventory_consume_stock_payload, "move_item": inventory_move_item_payload}.get(action_id)
    if resolver is None:
        return None
    return resolver(query, item_reference=ref) if action_id != "add_item" else resolver(query)


def _domain_fields(query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    domain = str(frame.get("domain_concept") or "")
    if domain == "RECIPE" and action_id in {"add", "commit_import"}:
        return _recipe_fields(query, frame, action_id)
    if domain in {"HOUSEHOLD_ITEM", "INVENTORY_MUTATION"} and action_id in {"add_item", "consume_stock", "move_item"}:
        return _inventory_fields(query, frame, action_id)
    if domain == "PROJECT" and action_id == "create":
        from src.intent_contracts import work_project_create_payload
        return work_project_create_payload(query)
    if domain == "TASK" and action_id == "create_task":
        from src.intent_contracts import work_task_create_payload
        return work_task_create_payload(query)
    if domain == "MEMORY" and action_id in {"create", "update", "delete"}:
        from src.intent_contracts import memory_mutation_payload
        return memory_mutation_payload(query, action_id)
    if domain == "NOTES_MUTATION" and action_id in {"add", "update", "delete"}:
        from src.intent_contracts import note_mutation_payload
        fields = note_mutation_payload(query, action_id)
        if not fields and action_id in {"update", "delete"} and _reference_id(frame):
            return {"action": action_id, "id": _reference_id(frame)}
        if fields and action_id in {"update", "delete"} and _reference_id(frame):
            return {**fields, "id": _reference_id(frame)}
        return fields
    return None


FIELD_RESOLVERS: dict[tuple[str, str], FieldResolver] = {
    ("automation.task.manage", "create"): _scheduled_task_fields,
}


def resolve_action_fields(
    *,
    capability_id: str | None,
    action_id: str | None,
    query: str,
    frame: Mapping[str, Any],
) -> dict[str, Any]:
    key = (str(capability_id or ""), str(action_id or ""))
    resolver = FIELD_RESOLVERS.get(key)
    values = resolver(str(query or ""), frame) if resolver else _domain_fields(str(query or ""), frame, key[1])
    return dict(values or {})


def deterministic_action_for_contract(
    contract: Mapping[str, Any] | None,
    *,
    query: str,
    frame: Mapping[str, Any],
    disabled_tools: set[str],
) -> tuple[str, dict[str, Any]] | None:
    """Return a payload only when a registered schema resolver can fill it."""
    contract = contract if isinstance(contract, Mapping) else {}
    binding = str(contract.get("binding") or "")
    fields = resolve_action_fields(
        capability_id=contract.get("capability_id"),
        action_id=contract.get("action_id"),
        query=query,
        frame=frame,
    )
    if not binding or binding in disabled_tools or not fields:
        return None
    return binding, fields
