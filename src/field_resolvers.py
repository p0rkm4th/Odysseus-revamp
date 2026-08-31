from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable


FieldResolver = Callable[[str, Mapping[str, Any], str], Mapping[str, Any] | None]


def _scheduled_task_fields(query: str, _frame: Mapping[str, Any], _action_id: str) -> Mapping[str, Any] | None:
    from src.intent_contracts import scheduled_task_create_payload

    return scheduled_task_create_payload(query)


def _recipe_fields(query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    from src.intent_contracts import recipe_create_payload, recipe_requested_name, recipe_source_url

    filters = frame.get("filters") if isinstance(frame.get("filters"), Mapping) else {}
    draft = recipe_create_payload(query)
    if draft:
        if action_id in {"add", "commit_import"} and filters.get("recipe_import") is True:
            draft = {**draft, "action": "commit_import", "source_text": query}
        return draft
    url = str(filters.get("recipe_source_url") or "").strip() or recipe_source_url(query)
    name = str(filters.get("recipe_requested_name") or "").strip() or recipe_requested_name(query)
    if url:
        return {"action": action_id, "source_url": url, **({"requested_name": name} if name else {})}
    if action_id == "prepare_import":
        return None
    if action_id in {"add", "commit_import"}:
        return {
            "review_required": True, "source_text": query,
            **({"requested_name": name} if name else {}),
            "review_reason": "Recipe text needs review before saving; one or more ingredients has no exact amount. Nothing was saved.",
        }
    return None


def _network_fields(query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    cidr = str(frame.get("network_cidr") or frame.get("cidr") or "").strip()
    return {"action": action_id, "cidr": cidr} if cidr else None


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


def _work_project_fields(query: str, _frame: Mapping[str, Any], _action_id: str) -> Mapping[str, Any] | None:
    from src.intent_contracts import work_project_create_payload
    return work_project_create_payload(query)


def _work_task_fields(query: str, _frame: Mapping[str, Any], _action_id: str) -> Mapping[str, Any] | None:
    from src.intent_contracts import work_task_create_payload
    return work_task_create_payload(query)


def _memory_fields(query: str, _frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    from src.intent_contracts import memory_mutation_payload
    return memory_mutation_payload(query, action_id)


def _notes_fields(query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    from src.intent_contracts import note_mutation_payload
    fields = note_mutation_payload(query, action_id)
    ref = _reference_id(frame)
    if not fields and action_id in {"update", "delete"} and ref:
        return {"action": action_id, "id": ref}
    if fields and action_id in {"update", "delete"} and ref:
        return {**fields, "id": ref}
    return fields


# The resolver name is declared by ActionSpec.  This table is intentionally
# about field semantics only; it cannot select capabilities or execute work.
FIELD_RESOLVERS: dict[str, FieldResolver] = {
    "scheduled_task": _scheduled_task_fields,
    "recipe": _recipe_fields,
    "inventory": _inventory_fields,
    "network": _network_fields,
    "work_project": _work_project_fields,
    "work_task": _work_task_fields,
    "memory": _memory_fields,
    "notes": _notes_fields,
}


def resolve_action_fields(
    *,
    capability_id: str | None,
    action_id: str | None,
    binding: str | None = None,
    query: str,
    frame: Mapping[str, Any],
) -> dict[str, Any]:
    capability = str(capability_id or "")
    action = str(action_id or "")
    if not capability and binding:
        from src.capability_registry import capability_for_tool
        spec = capability_for_tool(str(binding))
        capability = spec.capability_id if spec else ""
    from src.capability_registry import capability_for_id
    spec = capability_for_id(capability)
    action_spec = spec.actions.get(action) if spec else None
    resolver = FIELD_RESOLVERS.get(action_spec.field_resolver) if action_spec else None
    values = resolver(str(query or ""), frame, action) if resolver else None
    return dict(values or {})


def deterministic_action_for_contract(
    contract: Mapping[str, Any] | None,
    *,
    query: str,
    frame: Mapping[str, Any],
    disabled_tools: set[str],
) -> tuple[str, dict[str, Any]] | None:
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
