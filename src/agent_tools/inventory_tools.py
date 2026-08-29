"""Owner-scoped native-tool adapters for inventory and recipes.

The persistence/transaction rules belong to :mod:`src.inventory_service`.
This module is deliberately narrow: validate the model-facing JSON envelope,
require an authenticated owner, then delegate to the service API.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any, Mapping

logger = logging.getLogger(__name__)

INVENTORY_ACTIONS = frozenset({
    "list", "search", "get", "add_item", "add_stock", "consume_stock",
    "adjust_stock", "get_components", "update_asset", "create_intake_draft",
})
RECIPE_ACTIONS = frozenset({
    "list", "search", "get", "can_make", "shopping_requirements", "scale",
    "expiring_candidates", "prepare_import", "add", "commit_import", "cook",
})


def _load_inventory_service():
    """Resolve the service lazily so startup does not initialize its database."""
    from src.inventory_service import get_inventory_service

    return get_inventory_service()


def _parse_request(content: str, *, actions: frozenset[str]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(content or "{}")
    except (json.JSONDecodeError, TypeError):
        return None, "arguments must be a valid JSON object"
    if not isinstance(value, dict):
        return None, "arguments must be a JSON object"
    action = value.get("action")
    if not isinstance(action, str) or action not in actions:
        return None, f"action must be one of: {', '.join(sorted(actions))}"
    return value, None


async def _call_service(method_name: str, args: Mapping[str, Any], owner: str) -> dict[str, Any]:
    service = _load_inventory_service()
    method = getattr(service, method_name)
    # SQLAlchemy's synchronous session work must never block chat streaming.
    # Async-compatible test/dummy services remain supported: a coroutine
    # returned by the worker is awaited back on this loop.
    value = await asyncio.to_thread(method, dict(args), owner=owner)
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, dict):
        raise TypeError("inventory service returned a non-object result")
    result = dict(value)
    result.setdefault("exit_code", 0 if "error" not in result else 1)
    return result


async def _execute(content: str, ctx: Mapping[str, Any], *, method: str, actions: frozenset[str]) -> dict[str, Any]:
    owner = str(ctx.get("owner") or "").strip()
    if not owner:
        return {"error": "Inventory tools require an authenticated owner.", "exit_code": 1}
    args, error = _parse_request(content, actions=actions)
    if error:
        return {"error": error, "exit_code": 1}
    try:
        if method == "manage_inventory" and (args or {}).get("action") == "create_intake_draft":
            return await _create_intake_draft(args or {}, owner)
        return await _call_service(method, args or {}, owner)
    except Exception as exc:
        # Do not log request payloads or exception text: both may contain
        # private inventory/recipe names supplied by the owner.
        logger.warning("%s service call failed (%s)", method, type(exc).__name__)
        return {
            "error": "The inventory service could not complete that request. No change was confirmed.",
            "exit_code": 1,
        }


async def _create_intake_draft(args: Mapping[str, Any], owner: str) -> dict[str, Any]:
    """Persist review-only candidates without applying inventory changes."""
    candidates = args.get("candidates")
    if not isinstance(candidates, list) or not candidates or len(candidates) > 256:
        raise ValueError("candidates must be a non-empty list of at most 256 objects")
    source_type = str(args.get("source_type") or "import").strip().casefold()
    if source_type not in {"import", "network_discovery"}:
        raise ValueError("source_type must be import or network_discovery")
    idempotency_key = str(args.get("idempotency_key") or "").strip()
    if not idempotency_key or len(idempotency_key) > 255:
        raise ValueError("idempotency_key is required and must be at most 255 characters")

    from core.database import SessionLocal
    from core.inventory_models import InventoryDraft
    from src.inventory_intake import build_inventory_intake_draft

    def persist() -> dict[str, Any]:
        db = SessionLocal()
        try:
            prior = db.query(InventoryDraft).filter_by(
                owner=owner, idempotency_key=idempotency_key,
            ).one_or_none()
            if prior:
                result = dict(prior.payload_json)
                result["revision"] = prior.updated_at.isoformat()
                return result
            draft = build_inventory_intake_draft(
                owner=owner, candidates=candidates,
                source_text=args.get("source_text"),
            )
            draft["source"] = dict(draft["source"])
            draft["source"]["type"] = source_type
            row = InventoryDraft(
                id=draft["draft_id"], owner=owner, source_type=source_type,
                source_ref=None, payload_json=draft, confidence_json={},
                image_refs_json=draft["source"]["attachment_ids"],
                status="pending", idempotency_key=idempotency_key,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            result = dict(row.payload_json)
            result["revision"] = row.updated_at.isoformat()
            return result
        finally:
            db.close()

    return await asyncio.to_thread(persist)


class ManageInventoryTool:
    async def execute(self, content: str, ctx: Mapping[str, Any]) -> dict[str, Any]:
        return await _execute(
            content, ctx, method="manage_inventory", actions=INVENTORY_ACTIONS,
        )


class ManageRecipesTool:
    async def execute(self, content: str, ctx: Mapping[str, Any]) -> dict[str, Any]:
        return await _execute(
            content, ctx, method="manage_recipes", actions=RECIPE_ACTIONS,
        )
