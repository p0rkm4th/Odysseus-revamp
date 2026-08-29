"""Owner-scoped inventory, recipe, and reviewable intake APIs."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import json
import logging
import re
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Query, Request

from core.database import SessionLocal
from core.inventory_models import InventoryDraft
from src.auth_helpers import require_user
from src.inventory_intake import build_inventory_intake_draft
from src.inventory_multimodal import InventoryExtractionError, extract_inventory_candidates
from src.inventory_planning import normalize_item_name
from src.inventory_service import (
    InsufficientStock,
    InventoryConflict,
    InventoryError,
    InventoryNotFound,
    get_inventory_service,
)
from src.owner_identity import effective_storage_owner


_SOURCE_TYPES = frozenset({
    "natural_language", "photo", "voice", "telegram", "import", "network_discovery",
})
_UPLOAD_ID_RE = re.compile(r"^[0-9a-fA-F]{32}(?:\.[A-Za-z0-9]+)?$")
logger = logging.getLogger(__name__)


def _owner(request: Request) -> str:
    """Authenticate first, then select the stable single-user storage owner."""
    owner = effective_storage_owner(require_user(request))
    if not owner:
        raise HTTPException(401, "An authenticated inventory owner is required")
    return owner


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InventoryNotFound):
        return HTTPException(404, str(exc))
    if isinstance(exc, InventoryConflict):
        return HTTPException(409, str(exc))
    if isinstance(exc, InsufficientStock):
        shortages = [
            {"name": row.name, "missing": str(row.missing), "unit": row.unit}
            for row in exc.plan.shortages
        ]
        return HTTPException(409, {"message": "insufficient stock", "shortages": shortages})
    return HTTPException(400, str(exc))


def setup_inventory_routes(
    upload_handler, *, session_factory=SessionLocal, service=None,
    extraction_service=extract_inventory_candidates,
):
    router = APIRouter(prefix="/api", tags=["inventory"])
    inventory = service or get_inventory_service(session_factory)

    async def call(method, *args, **kwargs):
        try:
            return await asyncio.to_thread(method, *args, **kwargs)
        except InventoryError as exc:
            raise _http_error(exc) from exc

    @router.get("/inventory/items")
    async def list_items(
        request: Request, domain: str | None = None,
        include_archived: bool = False, limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        return {"items": await call(
            inventory.list_items, _owner(request), domain=domain,
            include_archived=include_archived, limit=limit, offset=offset,
        )}

    @router.get("/inventory/overview")
    async def inventory_overview(request: Request, expiry_days: int = Query(30, ge=0, le=365)):
        """Canonical Household/Inventory read projection for the workspace."""
        return await call(inventory.household_overview, _owner(request), expiry_days=expiry_days)

    @router.get("/inventory/history")
    async def inventory_history(request: Request, limit: int = Query(50, ge=1, le=200)):
        return {"history": await call(inventory.inventory_history, _owner(request), limit=limit)}

    @router.get("/inventory/items/search")
    async def search_items(
        request: Request, q: str = Query(..., min_length=1, max_length=200),
        domain: str | None = None, limit: int = Query(50, ge=1, le=200),
    ):
        return {"items": await call(
            inventory.search_items, _owner(request), q, domain=domain, limit=limit,
        )}

    @router.get("/inventory/items/{item_id}")
    async def get_item(request: Request, item_id: str):
        owner = _owner(request)
        item = await call(inventory.get_item, owner, item_id)
        lots = await call(inventory.list_lots, owner, item_id)
        asset = None
        components = []
        if item["domain"] == "it" and item["item_kind"] == "asset":
            asset = await call(inventory.get_asset_detail, owner, item_id)
            components = await call(inventory.list_asset_components, owner, item_id)
        return {"item": item, "lots": lots, "asset": asset, "components": components}

    @router.put("/inventory/assets/{item_id}")
    async def update_asset(request: Request, item_id: str, payload: dict[str, Any] = Body(...)):
        allowed = {
            "serial_number", "asset_tag", "status", "condition", "acquired_at",
            "purchase_price", "currency", "warranty_expires_at", "hostname",
            "mac_addresses", "ip_addresses", "specs", "assigned_to", "parent_asset_id",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise HTTPException(400, "unsupported asset fields: " + ", ".join(sorted(unknown)))
        return {"asset": await call(
            inventory.update_asset_detail, _owner(request), item_id, **payload,
        )}

    @router.post("/inventory/items", status_code=201)
    async def create_item(request: Request, payload: dict[str, Any] = Body(...)):
        if "image_refs" in payload:
            raise HTTPException(400, "attach images through the owner-checked intake API")
        allowed = {
            "name", "domain", "item_kind", "default_unit", "category", "description",
            "brand", "manufacturer", "model", "sku", "barcode", "reorder_point",
            "location_id", "metadata", "image_refs",
        }
        return {"item": await call(
            inventory.create_item, _owner(request),
            **{key: value for key, value in payload.items() if key in allowed},
        )}

    @router.post("/inventory/items/{item_id}/stock", status_code=201)
    async def add_stock(request: Request, item_id: str, payload: dict[str, Any] = Body(...)):
        allowed = {"quantity", "unit", "idempotency_key", "location_id", "expiry_date",
                   "opened_at", "purchase_date", "unit_cost", "currency", "lot_code"}
        values = {key: value for key, value in payload.items() if key in allowed}
        try:
            for field in ("expiry_date", "purchase_date"):
                if values.get(field) is not None and not isinstance(values[field], date):
                    values[field] = date.fromisoformat(str(values[field]))
            if values.get("opened_at") is not None and not isinstance(values["opened_at"], datetime):
                values["opened_at"] = datetime.fromisoformat(str(values["opened_at"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(400, "stock dates must use ISO-8601 format") from exc
        return await call(
            inventory.add_stock, _owner(request), item_id,
            **values,
        )

    @router.post("/inventory/items/{item_id}/consume")
    async def consume_stock(request: Request, item_id: str, payload: dict[str, Any] = Body(...)):
        allowed = {"quantity", "unit", "idempotency_key", "reason"}
        return await call(
            inventory.consume_stock, _owner(request), item_id,
            **{key: value for key, value in payload.items() if key in allowed},
        )

    @router.post("/inventory/lots/{lot_id}/adjust")
    async def adjust_lot(request: Request, lot_id: str, payload: dict[str, Any] = Body(...)):
        allowed = {"quantity_delta", "unit", "idempotency_key", "note"}
        return await call(
            inventory.adjust_lot, _owner(request), lot_id,
            **{key: value for key, value in payload.items() if key in allowed},
        )

    @router.get("/recipes")
    async def list_recipes(request: Request, include_archived: bool = False):
        return {"recipes": await call(
            inventory.list_recipes, _owner(request), include_archived=include_archived,
        )}

    @router.get("/recipes/{recipe_id}")
    async def get_recipe(request: Request, recipe_id: str):
        return {"recipe": await call(inventory.get_recipe, _owner(request), recipe_id)}

    @router.post("/recipes", status_code=201)
    async def create_recipe(request: Request, payload: dict[str, Any] = Body(...)):
        if "image_refs" in payload:
            raise HTTPException(400, "attach images through the owner-checked intake API")
        allowed = {"name", "servings", "ingredients", "instructions", "source_url", "tags", "image_refs"}
        return {"recipe": await call(
            inventory.create_recipe, _owner(request),
            **{key: value for key, value in payload.items() if key in allowed},
        )}

    @router.post("/recipes/import/prepare")
    async def prepare_recipe_import(request: Request, payload: dict[str, Any] = Body(...)):
        """Prepare an unpersisted RecipeDraft from owner-supplied evidence."""
        owner = _owner(request)
        source_url = str(payload.get("source_url") or "").strip() or None
        source_text = str(payload.get("source_text") or "").strip() or None
        attachment_ids = payload.get("attachment_ids")
        if not source_url and not source_text and not attachment_ids:
            raise HTTPException(400, "source_url, source_text, or an image attachment is required")
        if source_url and not re.match(r"^https?://", source_url, re.IGNORECASE):
            raise HTTPException(400, "source_url must use http or https")
        if attachment_ids:
            resolved = await asyncio.to_thread(resolve_attachments, owner, attachment_ids)
            if len(resolved) != 1:
                raise HTTPException(400, "recipe image preparation requires exactly one image attachment")
            image = resolved[0]
            mime = str(image.get("mime") or image.get("content_type") or "")
            path = image.get("path")
            if not mime.startswith("image/") or not isinstance(path, str) or not path:
                raise HTTPException(400, "recipe preparation attachment must be an available image")
            from src.document_processor import analyze_image_with_vl
            image_text = await asyncio.to_thread(
                analyze_image_with_vl, path, owner,
                "If this is a recipe, return JSON only with name, servings, ingredients, and instructions. "
                "Each ingredient needs name, numeric quantity, and unit. Do not guess missing values. "
                "If it is not a complete recipe, describe only the visible evidence.",
            )
            source_text = "\n\n".join(part for part in (source_text, image_text) if part)
        if source_url and not source_text:
            from src.recipe_import_sources import fetch_recipe_source
            source_text, error = await fetch_recipe_source(source_url, owner=owner)
            if error:
                return {"status": "NEEDS_REVIEW", "draft": None, "source_url": source_url,
                        "message": error}
        return await call(
            inventory.manage_recipes,
            {"action": "prepare_import", "source_text": source_text, "source_url": source_url},
            owner=owner,
        )

    @router.post("/recipes/import/commit", status_code=201)
    async def commit_recipe_import(request: Request, payload: dict[str, Any] = Body(...)):
        """Commit only a validated RecipeDraft through the canonical owner."""
        owner = _owner(request)
        draft = payload.get("draft")
        if not isinstance(draft, dict):
            raise HTTPException(400, "a validated draft is required")
        return await call(
            inventory.manage_recipes,
            {"action": "commit_import", "draft": draft}, owner=owner,
        )

    @router.get("/recipes/{recipe_id}/can-make")
    async def can_make(request: Request, recipe_id: str, servings: str | None = None):
        plan = await call(inventory.can_make, _owner(request), recipe_id, servings=servings)
        return {
            "can_make": plan.can_make,
            "deductions": [vars(row) for row in plan.deductions],
            "shortages": [vars(row) for row in plan.shortages],
        }

    @router.post("/recipes/{recipe_id}/cook")
    async def cook(request: Request, recipe_id: str, payload: dict[str, Any] = Body(...)):
        return {"cook": await call(
            inventory.cook, _owner(request), recipe_id,
            servings=payload.get("servings"), idempotency_key=payload.get("idempotency_key"),
        )}

    def resolve_attachments(owner: str, attachment_ids: Any) -> list[dict[str, Any]]:
        if not isinstance(attachment_ids, list) or len(attachment_ids) > 20:
            raise HTTPException(400, "attachment_ids must be a list of at most 20 upload IDs")
        resolved = []
        for attachment_id in attachment_ids:
            # Never accept paths or URLs here. The upload store is the sole resolver.
            if not isinstance(attachment_id, str) or not _UPLOAD_ID_RE.fullmatch(attachment_id):
                raise HTTPException(400, "attachment IDs must be opaque upload IDs")
            metadata = upload_handler.resolve_upload(
                attachment_id, owner=owner, auth_manager=None, allow_admin=False,
            )
            if not metadata:
                raise HTTPException(404, "attachment not found")
            metadata = dict(metadata)
            metadata["id"] = attachment_id
            metadata["owner"] = owner
            resolved.append(metadata)
        return resolved

    def persist_draft(*, owner: str, source_type: str, idempotency_key: str,
                      draft: dict[str, Any]) -> dict[str, Any]:
        db = session_factory()
        try:
            prior = db.query(InventoryDraft).filter_by(
                owner=owner, idempotency_key=idempotency_key,
            ).one_or_none()
            if prior:
                result = dict(prior.payload_json)
                result["revision"] = prior.updated_at.isoformat()
                return result
            draft = dict(draft)
            draft["source"] = dict(draft["source"])
            draft["source"]["type"] = source_type
            db.add(InventoryDraft(
                id=draft["draft_id"], owner=owner, source_type=source_type,
                source_ref=None, payload_json=draft, confidence_json={},
                image_refs_json=draft["source"]["attachment_ids"], status="pending",
                idempotency_key=idempotency_key,
            ))
            db.commit()
            row = db.query(InventoryDraft).filter_by(id=draft["draft_id"], owner=owner).one()
            result = dict(row.payload_json)
            result["revision"] = row.updated_at.isoformat()
            return result
        finally:
            db.close()

    @router.post("/inventory/intake/drafts", status_code=201)
    async def create_draft(request: Request, payload: dict[str, Any] = Body(...)):
        owner = _owner(request)
        source_type = str(payload.get("source_type") or "natural_language").casefold()
        if source_type not in _SOURCE_TYPES:
            raise HTTPException(400, "unsupported intake source_type")
        idempotency_key = str(payload.get("idempotency_key") or "").strip()
        if not idempotency_key or len(idempotency_key) > 255:
            raise HTTPException(400, "idempotency_key is required")
        resolved = await asyncio.to_thread(resolve_attachments, owner, payload.get("attachment_ids", []))
        try:
            draft = build_inventory_intake_draft(
                owner=owner, candidates=payload.get("candidates", []),
                resolved_attachments=resolved, source_text=payload.get("source_text"),
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        return await asyncio.to_thread(
            persist_draft, owner=owner, source_type=source_type,
            idempotency_key=idempotency_key, draft=draft,
        )

    @router.post("/inventory/intake/extract", status_code=201)
    async def extract_draft(request: Request, payload: dict[str, Any] = Body(...)):
        """Turn managed image observations or an STT transcript into a review draft."""
        owner = _owner(request)
        source_type = str(payload.get("source_type") or "natural_language").casefold()
        if source_type not in {"natural_language", "photo", "voice"}:
            raise HTTPException(400, "extraction source_type must be natural_language, photo, or voice")
        idempotency_key = str(payload.get("idempotency_key") or "").strip()
        if not idempotency_key or len(idempotency_key) > 255:
            raise HTTPException(400, "idempotency_key is required")
        source_text = payload.get("source_text")
        if source_text is not None and not isinstance(source_text, str):
            raise HTTPException(400, "source_text must be a string")
        if isinstance(source_text, str) and len(source_text) > 12_000:
            raise HTTPException(400, "source_text exceeds the 12000 character limit")
        resolved = await asyncio.to_thread(
            resolve_attachments, owner, payload.get("attachment_ids", []),
        )
        if len(resolved) > 5:
            raise HTTPException(400, "at most five images can be analyzed per draft")
        image_paths = []
        for attachment in resolved:
            mime = str(attachment.get("mime") or attachment.get("content_type") or "")
            if not mime.startswith("image/"):
                raise HTTPException(400, "inventory extraction attachments must be images")
            path = attachment.get("path")
            if not isinstance(path, str) or not path:
                raise HTTPException(400, "managed image is unavailable")
            image_paths.append(path)
        if source_type == "photo" and not image_paths:
            raise HTTPException(400, "photo extraction requires a managed image upload")
        if source_type == "voice" and not (source_text or "").strip():
            raise HTTPException(400, "voice extraction requires a transcript from the STT endpoint")
        try:
            candidates = await asyncio.to_thread(
                extraction_service, owner=owner, source_text=source_text,
                image_paths=image_paths,
            )
            draft = build_inventory_intake_draft(
                owner=owner, candidates=candidates, resolved_attachments=resolved,
                source_text=source_text,
            )
        except (InventoryExtractionError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            logger.error("Inventory extraction failed", exc_info=True)
            raise HTTPException(503, "inventory extraction is temporarily unavailable") from exc
        return await asyncio.to_thread(
            persist_draft, owner=owner, source_type=source_type,
            idempotency_key=idempotency_key, draft=draft,
        )

    @router.get("/inventory/intake/drafts/{draft_id}")
    async def get_draft(request: Request, draft_id: str):
        owner = _owner(request)
        def load():
            db = session_factory()
            try:
                row = db.query(InventoryDraft).filter_by(id=draft_id, owner=owner).one_or_none()
                if not row:
                    raise HTTPException(404, "inventory intake draft not found")
                result = dict(row.payload_json)
                result["commit_status"] = row.status
                result["revision"] = row.updated_at.isoformat()
                return result
            finally:
                db.close()
        return await asyncio.to_thread(load)

    @router.put("/inventory/intake/drafts/{draft_id}")
    async def correct_draft(request: Request, draft_id: str, payload: dict[str, Any] = Body(...)):
        owner = _owner(request)
        unknown = set(payload) - {"expected_revision", "source_text", "candidates"}
        if unknown:
            raise HTTPException(400, "unsupported correction fields: " + ", ".join(sorted(unknown)))
        expected = str(payload.get("expected_revision") or "")
        if not expected:
            raise HTTPException(400, "expected_revision is required")
        if not isinstance(payload.get("candidates"), list):
            raise HTTPException(400, "candidates must be a list")

        def correct():
            db = session_factory()
            try:
                row = db.query(InventoryDraft).filter_by(id=draft_id, owner=owner).one_or_none()
                if not row:
                    raise HTTPException(404, "inventory intake draft not found")
                if row.status != "pending":
                    raise HTTPException(409, "only pending drafts can be corrected")
                if row.updated_at.isoformat() != expected:
                    raise HTTPException(409, "draft changed; reload before correcting it")
                previous = dict(row.payload_json)
                resolved = [
                    {"id": attachment_id, "owner": owner}
                    for attachment_id in previous["source"].get("attachment_ids", [])
                ]
                try:
                    corrected = build_inventory_intake_draft(
                        owner=owner, candidates=payload["candidates"],
                        resolved_attachments=resolved,
                        source_text=payload.get("source_text", previous["source"].get("text")),
                        draft_id=draft_id,
                    )
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                corrected["source"]["type"] = row.source_type
                revised_at = datetime.now(timezone.utc).replace(tzinfo=None)
                changed = db.query(InventoryDraft).filter(
                    InventoryDraft.id == draft_id, InventoryDraft.owner == owner,
                    InventoryDraft.status == "pending", InventoryDraft.updated_at == row.updated_at,
                ).update({
                    InventoryDraft.payload_json: corrected,
                    InventoryDraft.updated_at: revised_at,
                }, synchronize_session=False)
                if changed != 1:
                    db.rollback()
                    raise HTTPException(409, "draft changed; reload before correcting it")
                db.commit()
                result = dict(corrected)
                result["revision"] = revised_at.isoformat()
                return result
            finally:
                db.close()
        return await asyncio.to_thread(correct)

    @router.post("/inventory/intake/drafts/{draft_id}/confirm")
    async def confirm_draft(request: Request, draft_id: str, payload: dict[str, Any] = Body(...)):
        owner = _owner(request)
        if payload.get("confirm") is not True:
            raise HTTPException(400, "confirm must be exactly true")
        resume = payload.get("resume") is True
        expected_revision = str(payload.get("expected_revision") or "")

        def mark_confirmed():
            db = session_factory()
            try:
                row = db.query(InventoryDraft).filter_by(id=draft_id, owner=owner).one_or_none()
                if not row:
                    raise HTTPException(404, "inventory intake draft not found")
                draft = dict(row.payload_json)
                if row.status == "applied":
                    return draft, True
                if draft.get("status") != "ready_for_confirmation":
                    raise HTTPException(409, "draft still requires review")
                if row.status == "confirmed":
                    if not resume:
                        raise HTTPException(409, "draft confirmation is already in progress; use resume=true to retry a failed attempt")
                elif row.status == "pending":
                    if not expected_revision:
                        raise HTTPException(400, "expected_revision is required")
                    if row.updated_at.isoformat() != expected_revision:
                        raise HTTPException(409, "draft changed; reload before confirming it")
                    claimed = db.query(InventoryDraft).filter(
                        InventoryDraft.id == draft_id, InventoryDraft.owner == owner,
                        InventoryDraft.status == "pending", InventoryDraft.updated_at == row.updated_at,
                    ).update({InventoryDraft.status: "confirmed"}, synchronize_session=False)
                    db.commit()
                    if claimed != 1:
                        raise HTTPException(409, "draft confirmation is already in progress")
                else:
                    raise HTTPException(409, "draft cannot be confirmed in its current state")
                return draft, False
            finally:
                db.close()

        draft, applied = await asyncio.to_thread(mark_confirmed)
        if applied:
            return {
                "draft_id": draft_id, "status": "applied", "replayed": True,
                "receipt": draft.get("receipt"),
            }

        results = []
        changed_item_ids = []
        movement_ids = []
        for index, operation in enumerate(draft["operations"]):
            item_data = operation["item"]
            matches = await call(
                inventory.search_items, owner, item_data["name"],
                domain=operation["domain"], limit=20,
            )
            matches = [item for item in matches if normalize_item_name(item["name"]) == normalize_item_name(item_data["name"])]
            if operation["action"] == "add" and not matches:
                kind = "asset" if operation["domain"] == "it" else (
                    "ingredient" if operation["domain"] == "kitchen" else "consumable"
                )
                item = await call(
                    inventory.create_item, owner, name=item_data["name"],
                    domain=operation["domain"], item_kind=kind,
                    default_unit=operation["unit"], category=item_data.get("category"),
                    brand=item_data.get("brand"), manufacturer=item_data.get("manufacturer"),
                    model=item_data.get("model"),
                    metadata={},
                    image_refs=draft["source"]["attachment_ids"],
                )
            elif len(matches) == 1:
                item = matches[0]
            else:
                raise HTTPException(409, "intake item match is missing or ambiguous")
            if operation["domain"] == "it":
                await call(
                    inventory.update_asset_detail, owner, item["id"],
                    serial_number=item_data.get("serial_number"),
                    condition=item_data.get("condition"),
                    hostname=item_data.get("hostname"),
                    mac_addresses=item_data.get("mac_addresses"),
                    ip_addresses=item_data.get("ip_addresses"),
                    specs={
                        key: value for key, value in item_data.items()
                        if key in {"part_number", "notes"}
                    },
                    provenance={
                        "source_kind": draft["source"]["type"],
                        "source_id": draft_id,
                        "attachment_ids": list(draft["source"]["attachment_ids"]),
                    },
                )
            key = f"intake:{draft_id}:{index}"
            if operation["action"] == "add":
                result = await call(
                    inventory.add_stock, owner, item["id"], quantity=operation["quantity"],
                    unit=operation["unit"], idempotency_key=key,
                )
            else:
                result = await call(
                    inventory.consume_stock, owner, item["id"], quantity=operation["quantity"],
                    unit=operation["unit"], idempotency_key=key,
                )
            results.append(result)
            changed_item_ids.append(item["id"])
            if isinstance(result.get("movement"), dict):
                movement_ids.append(result["movement"].get("id"))
            movement_ids.extend(
                movement.get("id") for movement in result.get("movements", [])
                if isinstance(movement, dict)
            )

        receipt = {
            "id": f"inventory:{draft_id}",
            "authority": "explicit_confirmation",
            "source_type": draft["source"].get("type", "natural_language"),
            "source_id": draft_id,
            "item_ids": list(dict.fromkeys(changed_item_ids)),
            "movement_ids": [value for value in movement_ids if value],
            "operation_count": len(results),
            "recovery": "Inventory movements are immutable; append a compensating adjustment.",
        }

        def mark_applied():
            db = session_factory()
            try:
                row = db.query(InventoryDraft).filter_by(id=draft_id, owner=owner, status="confirmed").one_or_none()
                if not row:
                    raise HTTPException(409, "draft confirmation state changed")
                stored = dict(row.payload_json)
                stored["receipt"] = receipt
                row.payload_json = stored
                row.status = "applied"
                db.commit()
            finally:
                db.close()
        await asyncio.to_thread(mark_applied)
        return {
            "draft_id": draft_id, "status": "applied", "replayed": False,
            "results": results, "receipt": receipt,
        }

    return router
