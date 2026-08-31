from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any, Callable


FieldResolver = Callable[[str, Mapping[str, Any], str], Mapping[str, Any] | None]


def canonical_asset_read_payload(frame: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project bounded Asset read fields from the resolved semantic frame."""
    frame = frame if isinstance(frame, Mapping) else {}
    reference = str(frame.get("entity_reference") or "").strip()
    if reference:
        return {"action": "get", "asset": reference}
    filters = frame.get("filters") if isinstance(frame.get("filters"), Mapping) else {}
    payload: dict[str, Any] = {"action": "list"}
    if not filters.get("asset_property") and filters.get("asset_projection") not in {"count", "property", "filter"}:
        payload["limit"] = 500
    if filters.get("asset_query"):
        payload["query"] = str(filters["asset_query"])[:120]
    if filters.get("asset_property") and filters.get("asset_projection") != "count":
        payload["asset_property"] = str(filters["asset_property"])[:40]
        payload["result_projection"] = "property"
    elif filters.get("asset_projection") == "count":
        payload["result_projection"] = "count"
    elif filters.get("asset_projection") == "filter":
        payload["result_projection"] = "filter"
    return payload


def _asset_read_fields(query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    payload = canonical_asset_read_payload(frame)
    payload["action"] = action_id
    if action_id in {"list", "search"} and payload.get("query") and re.search(
        r"\bhow\s+many\b", str(query or ""), re.IGNORECASE
    ):
        payload["result_projection"] = "count"
    return payload


def _recipe_read_fields(_query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    filters = frame.get("filters") if isinstance(frame.get("filters"), Mapping) else {}
    reference = str(frame.get("entity_reference") or "").strip()
    payload: dict[str, Any] = {"action": action_id}
    if reference and action_id in {"get", "can_make", "shopping_requirements", "scale"}:
        payload["recipe_id"] = reference[:500]
    recipe_query = str(filters.get("recipe_query") or "").strip()
    if recipe_query and action_id == "search":
        payload["query"] = recipe_query[:200]
    servings = str(filters.get("servings") or "").strip()
    if servings and action_id == "scale":
        payload["servings"] = servings[:20]
    if filters.get("recipe_expiring") is True and action_id == "expiring_candidates":
        payload["expiry_days"] = 30
    return payload


def _developer_read_fields(query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    text = str(query or "").strip()
    filters = frame.get("filters") if isinstance(frame.get("filters"), Mapping) else {}
    payload: dict[str, Any] = {"action": action_id}
    if action_id == "search_code":
        match = re.search(r"\b(?:for|called|named)\s+(.+)$", text, re.IGNORECASE)
        payload["query"] = (match.group(1).strip() if match else text)[:400]
    elif action_id == "view_file_region":
        match = re.search(r"(?:^|\s)([A-Za-z0-9_./-]+\.(?:py|js|ts|tsx|jsx|json|md|css|html|yaml|yml|toml|sh))(?:\s|$)", text, re.IGNORECASE)
        payload["path"] = match.group(1) if match else ""
    elif str(filters.get("view") or "") == "map":
        payload["query"] = "**/*"
    return payload


def _scheduled_task_fields(query: str, _frame: Mapping[str, Any], _action_id: str) -> Mapping[str, Any] | None:
    from src.domain_resolvers.reminders import scheduled_task_create_payload

    return scheduled_task_create_payload(query)


def _recipe_fields(query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    from src.domain_resolvers.recipe import requested_name, source_url
    from src.intent_contracts import recipe_create_payload

    filters = frame.get("filters") if isinstance(frame.get("filters"), Mapping) else {}
    draft = recipe_create_payload(query)
    if draft:
        if action_id in {"add", "commit_import"} and filters.get("recipe_import") is True:
            draft = {**draft, "action": "commit_import", "source_text": query}
        return draft
    url = str(filters.get("recipe_source_url") or "").strip() or source_url(query)
    name = str(filters.get("recipe_requested_name") or "").strip() or requested_name(query)
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
    from src.domain_resolvers.inventory import (
        inventory_add_item_payload,
        inventory_consume_stock_payload,
        inventory_move_item_payload,
    )

    ref = _reference_id(frame)
    resolver = {"add_item": inventory_add_item_payload, "consume_stock": inventory_consume_stock_payload, "move_item": inventory_move_item_payload}.get(action_id)
    if resolver is None:
        return None
    return resolver(query, item_reference=ref) if action_id != "add_item" else resolver(query)


def _work_project_fields(query: str, _frame: Mapping[str, Any], _action_id: str) -> Mapping[str, Any] | None:
    from src.domain_resolvers.work import work_project_create_payload
    return work_project_create_payload(query)


def _work_task_fields(query: str, _frame: Mapping[str, Any], _action_id: str) -> Mapping[str, Any] | None:
    from src.domain_resolvers.work import work_task_create_payload
    return work_task_create_payload(query)


def _memory_fields(query: str, _frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    from src.domain_resolvers.memory import memory_mutation_payload
    return memory_mutation_payload(query, action_id)


def _query_fields(query: str, _frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    value = query.strip() or ("what do you remember about me" if action_id == "summarize_owner_memory" else "")
    return {"url" if action_id == "fetch" else "query": value} if value else None


def _notes_fields(query: str, frame: Mapping[str, Any], action_id: str) -> Mapping[str, Any] | None:
    from src.domain_resolvers.reminders import note_mutation_payload
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
    "asset_read": _asset_read_fields,
    "recipe_read": _recipe_read_fields,
    "developer_read": _developer_read_fields,
    "scheduled_task": _scheduled_task_fields,
    "recipe": _recipe_fields,
    "inventory": _inventory_fields,
    "network": _network_fields,
    "work_project": _work_project_fields,
    "work_task": _work_task_fields,
    "memory": _memory_fields,
    "query": _query_fields,
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
