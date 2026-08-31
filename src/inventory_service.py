"""Transactional, owner-scoped inventory and recipe operations.

The service deliberately accepts a session factory rather than a live session:
every public mutation owns one database transaction, so callers cannot
accidentally commit half of a multi-lot consumption or recipe cook.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import ipaddress
import re
from typing import Any, Iterable, Iterator
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.inventory_models import (
    InventoryAssetDetail,
    InventoryItem,
    InventoryLocation,
    InventoryLot,
    InventoryMovement,
    InventoryRecipe,
    InventoryRecipeCook,
    InventoryRecipeIngredient,
    InventoryDraft,
)
from src.inventory_planning import (
    RecipeRequirement,
    RecipeStockPlan,
    StockLot,
    item_name_search_terms,
    normalize_item_name,
    plan_recipe_stock,
)
from src.inventory_units import UnitError, normalize_amount, parse_decimal


class InventoryError(ValueError):
    """Base error safe for presentation at an API boundary."""


class InventoryNotFound(InventoryError):
    """The requested owner-scoped resource does not exist."""


class InventoryConflict(InventoryError):
    """An identifier or idempotency key conflicts with an existing operation."""


class InsufficientStock(InventoryError):
    def __init__(self, plan: RecipeStockPlan):
        super().__init__("insufficient stock")
        self.plan = plan


_DOMAINS = frozenset({"it", "kitchen", "household"})
_KINDS = frozenset({"asset", "consumable", "ingredient"})
_QUANT = Decimal("0.000001")
_ASSET_STATUSES = frozenset({"in_stock", "deployed", "repair", "retired", "disposed", "lost"})
_MAC_ADDRESS = re.compile(r"^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$")
_UNSET = object()


def _required_text(value: Any, field: str, *, maximum: int = 500) -> str:
    result = " ".join(str(value or "").strip().split())
    if not result or len(result) > maximum:
        raise InventoryError(f"{field} must contain 1 to {maximum} characters")
    return result


def _optional_text(value: Any, field: str, *, maximum: int = 2000) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    if not result:
        return None
    if len(result) > maximum:
        raise InventoryError(f"{field} must contain at most {maximum} characters")
    return result


def _canonical_amount(quantity: Any, unit: Any, expected_unit: str) -> Decimal:
    try:
        amount = normalize_amount(quantity, unit)
        expected = normalize_amount(Decimal("1"), expected_unit)
    except UnitError as exc:
        raise InventoryError(str(exc)) from exc
    if amount.dimension != expected.dimension or amount.unit != expected.unit:
        raise InventoryError(f"quantity must be compatible with {expected.unit}")
    return amount.quantity


def _movement_key(operation_key: str, index: int) -> str:
    if index == 0:
        return operation_key
    digest = hashlib.sha256(operation_key.encode("utf-8")).hexdigest()[:24]
    return f"{digest}:{index}"


def _item_view(item: InventoryItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "owner": item.owner,
        "domain": item.domain,
        "item_kind": item.item_kind,
        "name": item.name,
        "category": item.category,
        "description": item.description,
        "brand": item.brand,
        "manufacturer": item.manufacturer,
        "model": item.model,
        "sku": item.sku,
        "barcode": item.barcode,
        "default_unit": item.default_unit,
        "reorder_point": item.reorder_point,
        "location_id": item.location_id,
        "metadata": dict(item.metadata_json or {}),
        "image_refs": list(item.image_refs_json or []),
        "archived": bool(item.archived),
    }


def _lot_view(lot: InventoryLot) -> dict[str, Any]:
    return {
        "id": lot.id,
        "owner": lot.owner,
        "item_id": lot.item_id,
        "location_id": lot.location_id,
        "quantity": lot.quantity,
        "unit": lot.unit,
        "expiry_date": lot.expiry_date,
        "opened_at": lot.opened_at,
        "purchase_date": lot.purchase_date,
        "unit_cost": lot.unit_cost,
        "currency": lot.currency,
        "lot_code": lot.lot_code,
    }


def _movement_view(movement: InventoryMovement) -> dict[str, Any]:
    return {
        "id": movement.id,
        "owner": movement.owner,
        "item_id": movement.item_id,
        "lot_id": movement.lot_id,
        "quantity_delta": movement.quantity_delta,
        "unit": movement.unit,
        "reason": movement.reason,
        "source_kind": movement.source_kind,
        "source_id": movement.source_id,
        "idempotency_key": movement.idempotency_key,
        "occurred_at": movement.occurred_at.isoformat() if movement.occurred_at else None,
    }


def _asset_view(detail: InventoryAssetDetail) -> dict[str, Any]:
    return {
        "item_id": detail.item_id,
        "serial_number": detail.serial_number,
        "asset_tag": detail.asset_tag,
        "status": detail.status,
        "condition": detail.condition,
        "acquired_at": detail.acquired_at,
        "purchase_price": detail.purchase_price,
        "currency": detail.currency,
        "warranty_expires_at": detail.warranty_expires_at,
        "hostname": detail.hostname,
        "mac_addresses": list(detail.mac_addresses_json or []),
        "ip_addresses": list(detail.ip_addresses_json or []),
        "specs": dict(detail.specs_json or {}),
        "assigned_to": detail.assigned_to,
        "parent_asset_id": detail.parent_asset_id,
    }


def _optional_date(value: Any, field: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise InventoryError(f"{field} must be an ISO date") from exc


class InventoryService:
    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        db = self._session_factory()
        try:
            with db.begin():
                yield db
        finally:
            db.close()

    @contextmanager
    def _read(self) -> Iterator[Session]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _item(db: Session, owner: str, item_id: str) -> InventoryItem:
        item = db.query(InventoryItem).filter_by(id=item_id, owner=owner).one_or_none()
        if item is None:
            raise InventoryNotFound("inventory item not found")
        return item

    @staticmethod
    def _lot(db: Session, owner: str, lot_id: str) -> InventoryLot:
        lot = db.query(InventoryLot).filter_by(id=lot_id, owner=owner).one_or_none()
        if lot is None:
            raise InventoryNotFound("inventory lot not found")
        return lot

    @staticmethod
    def _location(db: Session, owner: str, location_id: str | None) -> None:
        if location_id and not db.query(InventoryLocation.id).filter_by(
            id=location_id, owner=owner
        ).first():
            raise InventoryNotFound("inventory location not found")

    def create_item(
        self,
        owner: str,
        *,
        name: str,
        domain: str,
        item_kind: str,
        default_unit: str = "each",
        category: str | None = None,
        description: str | None = None,
        brand: str | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        sku: str | None = None,
        barcode: str | None = None,
        reorder_point: Any | None = None,
        location_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        image_refs: Iterable[str] | None = None,
        initial_quantity: Any | None = None,
        initial_unit: str | None = None,
    ) -> dict[str, Any]:
        owner = _required_text(owner, "owner", maximum=255)
        display_name = _required_text(name, "name", maximum=200)
        domain = str(domain).strip().casefold()
        item_kind = str(item_kind).strip().casefold()
        if domain not in _DOMAINS:
            raise InventoryError("unsupported inventory domain")
        if item_kind not in _KINDS:
            raise InventoryError("unsupported inventory item kind")
        try:
            canonical_unit = normalize_amount(1, default_unit).unit
        except UnitError as exc:
            raise InventoryError(str(exc)) from exc
        reorder = None
        if reorder_point is not None:
            reorder = _canonical_amount(reorder_point, default_unit, canonical_unit)
        with self._transaction() as db:
            self._location(db, owner, location_id)
            item = InventoryItem(
                id=str(uuid4()), owner=owner, domain=domain, item_kind=item_kind,
                name=display_name, normalized_name=normalize_item_name(display_name),
                category=_optional_text(category, "category"),
                description=_optional_text(description, "description", maximum=10000),
                brand=_optional_text(brand, "brand"),
                manufacturer=_optional_text(manufacturer, "manufacturer"),
                model=_optional_text(model, "model"), sku=_optional_text(sku, "sku"),
                barcode=_optional_text(barcode, "barcode"), default_unit=canonical_unit,
                reorder_point=reorder, location_id=location_id,
                metadata_json=dict(metadata or {}),
                image_refs_json=[str(ref) for ref in (image_refs or [])],
            )
            db.add(item)
            db.flush()
            if initial_quantity is not None:
                amount = _canonical_amount(
                    initial_quantity, initial_unit or default_unit, item.default_unit,
                )
                key = f"initial:{item.id}"
                lot = InventoryLot(
                    id=str(uuid4()), owner=owner, item_id=item.id,
                    location_id=item.location_id, quantity=amount,
                    unit=item.default_unit,
                )
                movement = InventoryMovement(
                    id=str(uuid4()), owner=owner, item_id=item.id, lot_id=lot.id,
                    quantity_delta=amount, unit=item.default_unit, reason="add",
                    source_kind="stock_add", source_id=key, idempotency_key=key,
                )
                db.add_all([lot, movement])
                db.flush()
            return _item_view(item)

    def get_item(self, owner: str, item_id: str) -> dict[str, Any]:
        with self._read() as db:
            item = self._item(db, owner, item_id)
            result = _item_view(item)
            location = db.query(InventoryLocation).filter_by(
                id=item.location_id, owner=owner,
            ).one_or_none() if item.location_id else None
            result["location_name"] = location.name if location else None
            return result

    @staticmethod
    def _require_asset(db: Session, owner: str, item_id: str) -> InventoryItem:
        item = InventoryService._item(db, owner, item_id)
        if item.domain != "it" or item.item_kind != "asset":
            raise InventoryError("asset details require an IT asset item")
        return item

    @staticmethod
    def _validate_parent_asset(
        db: Session, owner: str, item_id: str, parent_asset_id: str | None,
    ) -> None:
        current_id = parent_asset_id
        visited: set[str] = set()
        while current_id:
            if current_id == item_id or current_id in visited:
                raise InventoryConflict("asset component relationship would create a cycle")
            visited.add(current_id)
            InventoryService._require_asset(db, owner, current_id)
            parent_detail = db.get(InventoryAssetDetail, current_id)
            if parent_detail is not None and parent_detail.owner != owner:
                raise InventoryNotFound("parent asset not found")
            current_id = parent_detail.parent_asset_id if parent_detail else None

    def get_asset_detail(self, owner: str, item_id: str) -> dict[str, Any] | None:
        with self._read() as db:
            self._require_asset(db, owner, item_id)
            detail = db.get(InventoryAssetDetail, item_id)
            if detail is None:
                return None
            if detail.owner != owner:
                raise InventoryNotFound("asset detail not found")
            return _asset_view(detail)

    def list_asset_components(self, owner: str, parent_asset_id: str) -> list[dict[str, Any]]:
        with self._read() as db:
            self._require_asset(db, owner, parent_asset_id)
            rows = db.query(InventoryAssetDetail).filter_by(
                owner=owner, parent_asset_id=parent_asset_id,
            ).order_by(InventoryAssetDetail.item_id).all()
            return [{"item": _item_view(self._item(db, owner, row.item_id)),
                     "asset": _asset_view(row)} for row in rows]

    def update_asset_detail(
        self, owner: str, item_id: str, *, serial_number: Any = _UNSET,
        asset_tag: Any = _UNSET, status: Any = _UNSET, condition: Any = _UNSET,
        acquired_at: Any = _UNSET, purchase_price: Any = _UNSET, currency: Any = _UNSET,
        warranty_expires_at: Any = _UNSET, hostname: Any = _UNSET,
        mac_addresses: Any = _UNSET, ip_addresses: Any = _UNSET, specs: Any = _UNSET,
        assigned_to: Any = _UNSET, parent_asset_id: Any = _UNSET,
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._transaction() as db:
            item = self._require_asset(db, owner, item_id)
            detail = db.get(InventoryAssetDetail, item_id)
            if detail is not None and detail.owner != owner:
                raise InventoryNotFound("asset detail not found")
            if detail is None:
                detail = InventoryAssetDetail(
                    item_id=item_id, owner=owner, status="in_stock",
                    mac_addresses_json=[], ip_addresses_json=[], specs_json={},
                )
                db.add(detail)
            for field, value, maximum in (
                ("serial_number", serial_number, 160), ("asset_tag", asset_tag, 160),
                ("condition", condition, 80), ("hostname", hostname, 253),
                ("assigned_to", assigned_to, 255),
            ):
                if value is not _UNSET:
                    setattr(detail, field, _optional_text(value, field, maximum=maximum))
            if status is not _UNSET:
                normalized_status = str(status or "").strip().casefold()
                if normalized_status not in _ASSET_STATUSES:
                    raise InventoryError("unsupported asset status")
                detail.status = normalized_status
            if acquired_at is not _UNSET:
                detail.acquired_at = _optional_date(acquired_at, "acquired_at")
            if warranty_expires_at is not _UNSET:
                detail.warranty_expires_at = _optional_date(warranty_expires_at, "warranty_expires_at")
            if purchase_price is not _UNSET:
                price = None
                if purchase_price not in (None, ""):
                    try:
                        price = Decimal(str(purchase_price))
                    except Exception as exc:
                        raise InventoryError("purchase_price must be a number") from exc
                    if not price.is_finite() or price < 0:
                        raise InventoryError("purchase_price must be finite and nonnegative")
                detail.purchase_price = price
            if currency is not _UNSET:
                normalized_currency = str(currency or "").strip().upper() or None
                if normalized_currency is not None and (
                    len(normalized_currency) != 3 or not normalized_currency.isalpha()
                ):
                    raise InventoryError("currency must be a three-letter code")
                detail.currency = normalized_currency
            if mac_addresses is not _UNSET:
                normalized_macs = []
                for value in mac_addresses or []:
                    mac = str(value).strip().upper().replace("-", ":")
                    if not _MAC_ADDRESS.fullmatch(mac):
                        raise InventoryError("invalid MAC address")
                    normalized_macs.append(mac)
                detail.mac_addresses_json = normalized_macs
            if ip_addresses is not _UNSET:
                normalized_ips = []
                for value in ip_addresses or []:
                    try:
                        normalized_ips.append(str(ipaddress.ip_address(str(value).strip())))
                    except ValueError as exc:
                        raise InventoryError("invalid IP address") from exc
                detail.ip_addresses_json = normalized_ips
            if specs is not _UNSET:
                if specs is not None and not isinstance(specs, dict):
                    raise InventoryError("asset specs must be an object")
                detail.specs_json = dict(specs or {})
            if parent_asset_id is not _UNSET:
                parent_id = _optional_text(parent_asset_id, "parent_asset_id", maximum=255)
                self._validate_parent_asset(db, owner, item_id, parent_id)
                detail.parent_asset_id = parent_id
            if provenance:
                metadata = dict(item.metadata_json or {})
                history = list(metadata.get("provenance") or [])
                entry = dict(provenance)
                identity = (entry.get("source_kind"), entry.get("source_id"))
                if not any(
                    (prior.get("source_kind"), prior.get("source_id")) == identity
                    for prior in history if isinstance(prior, dict)
                ):
                    history.append(entry)
                metadata["provenance"] = history[-50:]
                item.metadata_json = metadata
            try:
                db.flush()
            except IntegrityError as exc:
                raise InventoryConflict("asset serial number or tag is already in use") from exc
            return _asset_view(detail)

    def list_items(
        self, owner: str, *, domain: str | None = None,
        include_archived: bool = False, limit: int = 100, offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        with self._read() as db:
            query = db.query(InventoryItem).filter(InventoryItem.owner == owner)
            if domain is not None:
                query = query.filter(InventoryItem.domain == str(domain).casefold())
            if not include_archived:
                query = query.filter(InventoryItem.archived.is_(False))
            items = query.order_by(InventoryItem.normalized_name, InventoryItem.id).offset(offset).limit(limit)
            return [_item_view(item) for item in items]

    def search_items(
        self, owner: str, query: str, *, domain: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        terms = item_name_search_terms(query)
        limit = max(1, min(int(limit), 200))
        with self._read() as db:
            statement = db.query(InventoryItem).filter(
                InventoryItem.owner == owner,
                InventoryItem.archived.is_(False),
                or_(*(InventoryItem.normalized_name.contains(term) for term in terms)),
            )
            if domain is not None:
                statement = statement.filter(InventoryItem.domain == str(domain).casefold())
            return [_item_view(item) for item in statement.order_by(
                InventoryItem.normalized_name, InventoryItem.id
            ).limit(limit)]

    def add_stock(
        self, owner: str, item_id: str, *, quantity: Any, unit: str,
        idempotency_key: str, location_id: str | None = None,
        location_name: str | None = None,
        expiry_date: date | None = None, opened_at: datetime | None = None,
        purchase_date: date | None = None, unit_cost: Any | None = None,
        currency: str | None = None, lot_code: str | None = None,
        actor: str | None = None, session_id: str | None = None,
    ) -> dict[str, Any]:
        key = _required_text(idempotency_key, "idempotency_key", maximum=255)
        with self._transaction() as db:
            prior = db.query(InventoryMovement).filter_by(owner=owner, idempotency_key=key).one_or_none()
            if prior is not None:
                expected = _canonical_amount(quantity, unit, prior.unit)
                if prior.reason != "add" or prior.item_id != item_id or prior.quantity_delta != expected:
                    raise InventoryConflict("idempotency key was already used for another operation")
                lot = self._lot(db, owner, prior.lot_id)
                return {"lot": _lot_view(lot), "movement": _movement_view(prior), "replayed": True}
            item = self._item(db, owner, item_id)
            if location_name and not location_id:
                normalized_location = normalize_item_name(location_name)
                location = db.query(InventoryLocation).filter_by(
                    owner=owner, normalized_name=normalized_location,
                ).one_or_none()
                if location is None:
                    location = InventoryLocation(
                        id=str(uuid4()), owner=owner,
                        name=_required_text(location_name, "location_name", maximum=200),
                        normalized_name=normalized_location,
                        normalized_path=normalized_location,
                    )
                    db.add(location)
                    db.flush()
                location_id = location.id
                # A stock addition to a named household location establishes
                # that location as the item's current owner-facing location.
                item.location_id = location_id
            self._location(db, owner, location_id)
            amount = _canonical_amount(quantity, unit, item.default_unit)
            cost = None
            if unit_cost is not None:
                try:
                    cost = parse_decimal(unit_cost, positive=False)
                except UnitError as exc:
                    raise InventoryError(str(exc)) from exc
                if cost < 0:
                    raise InventoryError("unit_cost must not be negative")
            lot = InventoryLot(
                id=str(uuid4()), owner=owner, item_id=item.id,
                location_id=location_id or item.location_id, quantity=amount,
                unit=item.default_unit, expiry_date=expiry_date, opened_at=opened_at,
                purchase_date=purchase_date, unit_cost=cost,
                currency=str(currency).upper() if currency else None,
                lot_code=_optional_text(lot_code, "lot_code"),
            )
            movement = InventoryMovement(
                id=str(uuid4()), owner=owner, item_id=item.id, lot_id=lot.id,
                quantity_delta=amount, unit=item.default_unit, reason="add",
                source_kind="stock_add", source_id=key, idempotency_key=key,
                actor=actor, session_id=session_id,
            )
            db.add_all([lot, movement])
            db.flush()
            return {"lot": _lot_view(lot), "movement": _movement_view(movement), "replayed": False}

    def consume_stock(
        self, owner: str, item_id: str, *, quantity: Any, unit: str,
        idempotency_key: str, reason: str = "consume", actor: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        key = _required_text(idempotency_key, "idempotency_key", maximum=255)
        if reason not in {"consume", "dispose"}:
            raise InventoryError("consume reason must be consume or dispose")
        with self._transaction() as db:
            prior = db.query(InventoryMovement).filter_by(
                owner=owner, source_kind="stock_consume", source_id=key
            ).order_by(InventoryMovement.idempotency_key).all()
            if prior:
                requested = _canonical_amount(quantity, unit, prior[0].unit)
                consumed = sum((-movement.quantity_delta for movement in prior), Decimal("0"))
                if any(m.item_id != item_id or m.reason != reason for m in prior) or consumed != requested:
                    raise InventoryConflict("idempotency key was already used for another operation")
                return {"movements": [_movement_view(m) for m in prior], "quantity": consumed, "replayed": True}
            item = self._item(db, owner, item_id)
            requested = _canonical_amount(quantity, unit, item.default_unit)
            lots = db.query(InventoryLot).filter(
                InventoryLot.owner == owner, InventoryLot.item_id == item.id,
                InventoryLot.quantity > 0,
            ).with_for_update().all()
            stock_lots = [StockLot(
                lot_id=lot.id, item_id=item.id, item_name=item.name,
                quantity=lot.quantity, unit=lot.unit, expires_on=lot.expiry_date,
            ) for lot in lots]
            plan = plan_recipe_stock(
                [RecipeRequirement(item.name, requested, item.default_unit)], stock_lots
            )
            if not plan.can_make:
                raise InsufficientStock(plan)
            by_id = {lot.id: lot for lot in lots}
            movements: list[InventoryMovement] = []
            for index, deduction in enumerate(plan.deductions):
                lot = by_id[deduction.lot_id]
                changed = db.query(InventoryLot).filter(
                    InventoryLot.id == lot.id, InventoryLot.owner == owner,
                    InventoryLot.item_id == item.id,
                    InventoryLot.quantity >= deduction.quantity,
                ).update(
                    {InventoryLot.quantity: InventoryLot.quantity - deduction.quantity},
                    synchronize_session=False,
                )
                if changed != 1:
                    # Another transaction consumed this balance after the
                    # plan. Raising rolls back all earlier legs as well.
                    raise InsufficientStock(plan)
                movement = InventoryMovement(
                    id=str(uuid4()), owner=owner, item_id=item.id, lot_id=lot.id,
                    quantity_delta=-deduction.quantity, unit=item.default_unit,
                    reason=reason, source_kind="stock_consume", source_id=key,
                    idempotency_key=_movement_key(key, index), actor=actor,
                    session_id=session_id,
                )
                db.add(movement)
                movements.append(movement)
            db.flush()
            return {"movements": [_movement_view(m) for m in movements], "quantity": requested, "replayed": False}

    def adjust_lot(
        self, owner: str, lot_id: str, *, quantity_delta: Any, unit: str,
        idempotency_key: str, note: str | None = None,
    ) -> dict[str, Any]:
        key = _required_text(idempotency_key, "idempotency_key", maximum=255)
        with self._transaction() as db:
            prior = db.query(InventoryMovement).filter_by(owner=owner, idempotency_key=key).one_or_none()
            if prior is not None:
                delta = normalize_amount(quantity_delta, unit, positive=False).quantity
                if prior.reason != "adjust" or prior.lot_id != lot_id or prior.quantity_delta != delta:
                    raise InventoryConflict("idempotency key was already used for another operation")
                return {"lot": _lot_view(self._lot(db, owner, lot_id)), "movement": _movement_view(prior), "replayed": True}
            lot = self._lot(db, owner, lot_id)
            try:
                delta = normalize_amount(quantity_delta, unit, positive=False)
                expected = normalize_amount(1, lot.unit)
            except UnitError as exc:
                raise InventoryError(str(exc)) from exc
            if delta.unit != expected.unit:
                raise InventoryError(f"quantity must be compatible with {lot.unit}")
            if delta.quantity == 0:
                raise InventoryError("quantity_delta must not be zero")
            filters = [
                InventoryLot.id == lot.id, InventoryLot.owner == owner,
                InventoryLot.quantity + delta.quantity >= 0,
            ]
            changed = db.query(InventoryLot).filter(*filters).update(
                {InventoryLot.quantity: InventoryLot.quantity + delta.quantity},
                synchronize_session=False,
            )
            if changed != 1:
                raise InsufficientStock(RecipeStockPlan((), ()))
            db.expire(lot, ["quantity"])
            movement = InventoryMovement(
                id=str(uuid4()), owner=owner, item_id=lot.item_id, lot_id=lot.id,
                quantity_delta=delta.quantity, unit=lot.unit, reason="adjust",
                source_kind="stock_adjust", source_id=key, idempotency_key=key,
                note=_optional_text(note, "note", maximum=10000),
            )
            db.add(movement)
            db.flush()
            return {"lot": _lot_view(lot), "movement": _movement_view(movement), "replayed": False}

    def move_item(
        self, owner: str, item_id: str, *, location_name: str,
        idempotency_key: str, actor: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Move an owner item and its stocked lots to one named location."""
        owner = _required_text(owner, "owner", maximum=255)
        item_id = _required_text(item_id, "item_id", maximum=255)
        name = _required_text(location_name, "location_name", maximum=200)
        key = _required_text(idempotency_key, "idempotency_key", maximum=255)
        normalized = normalize_item_name(name)
        with self._transaction() as db:
            prior = db.query(InventoryMovement).filter_by(
                owner=owner, source_kind="stock_move", source_id=key,
            ).order_by(InventoryMovement.id).first()
            item = self._item(db, owner, item_id)
            location = db.query(InventoryLocation).filter_by(
                owner=owner, parent_id=None, normalized_name=normalized,
            ).one_or_none()
            if location is None:
                location = InventoryLocation(
                    id=str(uuid4()), owner=owner, name=name,
                    normalized_name=normalized, normalized_path=normalized,
                )
                db.add(location)
                db.flush()
            if prior is not None:
                return {
                    "item": _item_view(item) | {"location_name": location.name},
                    "location": {"id": location.id, "name": location.name},
                    "moved_lots": 0, "replayed": True,
                }
            old_location_id = item.location_id
            item.location_id = location.id
            lots = db.query(InventoryLot).filter_by(
                owner=owner, item_id=item.id,
            ).with_for_update().all()
            moved_lots = 0
            for index, lot in enumerate(lots):
                if lot.location_id == location.id:
                    continue
                old_id = lot.location_id
                lot.location_id = location.id
                if lot.quantity <= 0:
                    continue
                moved_lots += 1
                out_key = _movement_key(key, index * 2)
                in_key = _movement_key(key, index * 2 + 1)
                db.add_all([
                    InventoryMovement(
                        id=str(uuid4()), owner=owner, item_id=item.id, lot_id=lot.id,
                        quantity_delta=-lot.quantity, unit=lot.unit,
                        reason="move_out", source_kind="stock_move", source_id=key,
                        idempotency_key=out_key, actor=actor, session_id=session_id,
                    ),
                    InventoryMovement(
                        id=str(uuid4()), owner=owner, item_id=item.id, lot_id=lot.id,
                        quantity_delta=lot.quantity, unit=lot.unit,
                        reason="move_in", source_kind="stock_move", source_id=key,
                        idempotency_key=in_key, actor=actor, session_id=session_id,
                    ),
                ])
            db.flush()
            return {
                "item": _item_view(item) | {"location_name": location.name},
                "location": {"id": location.id, "name": location.name},
                "moved_lots": moved_lots, "previous_location_id": old_location_id,
                "replayed": False,
            }

    def list_lots(self, owner: str, item_id: str) -> list[dict[str, Any]]:
        with self._read() as db:
            self._item(db, owner, item_id)
            lots = db.query(InventoryLot).filter_by(owner=owner, item_id=item_id).order_by(
                InventoryLot.expiry_date.is_(None), InventoryLot.expiry_date, InventoryLot.id
            ).all()
            location_ids = {lot.location_id for lot in lots if lot.location_id}
            locations = db.query(InventoryLocation).filter(
                InventoryLocation.owner == owner,
                InventoryLocation.id.in_(location_ids or ["__none__"]),
            ).all()
            location_by_id = {location.id: location for location in locations}
            return [
                _lot_view(lot) | {
                    "location_name": (
                        location_by_id[lot.location_id].name
                        if lot.location_id in location_by_id else None
                    ),
                }
                for lot in lots
            ]

    def household_overview(self, owner: str, *, expiry_days: int = 30) -> dict[str, Any]:
        """Return a read-only projection over canonical household inventory.

        This deliberately does not create a Household store.  Items, lots,
        immutable movements, recipes, and intake drafts remain authoritative;
        this method only assembles the owner-scoped view needed by the
        Household workspace.
        """
        owner = _required_text(owner, "owner", maximum=255)
        horizon = max(0, min(int(expiry_days), 365))
        today = date.today()
        with self._read() as db:
            items = db.query(InventoryItem).filter(
                InventoryItem.owner == owner,
                InventoryItem.domain.in_(("kitchen", "household")),
                InventoryItem.archived.is_(False),
            ).order_by(InventoryItem.normalized_name, InventoryItem.id).all()
            item_by_id = {item.id: item for item in items}
            locations = db.query(InventoryLocation).filter(
                InventoryLocation.owner == owner,
            ).order_by(InventoryLocation.normalized_path, InventoryLocation.id).all()
            location_by_id = {location.id: location for location in locations}
            lots = db.query(InventoryLot).filter(
                InventoryLot.owner == owner,
                InventoryLot.item_id.in_(list(item_by_id) or ["__none__"]),
                InventoryLot.quantity > 0,
            ).order_by(InventoryLot.expiry_date.is_(None), InventoryLot.expiry_date, InventoryLot.id).all()
            totals: dict[str, Decimal] = {}
            expiring = []
            for lot in lots:
                totals[lot.item_id] = totals.get(lot.item_id, Decimal("0")) + Decimal(str(lot.quantity))
                if lot.expiry_date is not None and lot.expiry_date <= today + timedelta(days=horizon):
                    expiring.append({
                        "lot": _lot_view(lot),
                        "item": _item_view(item_by_id[lot.item_id]),
                        "location_name": (
                            location_by_id[lot.location_id].name
                            if lot.location_id in location_by_id else None
                        ),
                        "status": "expired" if lot.expiry_date < today else "expiring",
                    })
            low_stock = []
            for item in items:
                total = totals.get(item.id, Decimal("0"))
                if item.reorder_point is not None and total <= Decimal(str(item.reorder_point)):
                    low_stock.append({
                        "item": _item_view(item),
                        "quantity": str(total),
                        "reorder_point": str(item.reorder_point),
                    })
            pending_drafts = db.query(InventoryDraft).filter_by(
                owner=owner, status="pending",
            ).order_by(InventoryDraft.updated_at.desc()).limit(20).all()
            recipe_count = db.query(InventoryRecipe).filter_by(
                owner=owner, archived=False,
            ).count()
            recent = self._history_rows(db, owner, item_by_id=item_by_id, limit=10)
            item_rows = []
            location_totals: dict[str, Decimal] = {}
            location_item_ids: dict[str, set[str]] = {}
            for item in items:
                location_id = item.location_id
                if location_id in location_by_id:
                    location_totals[location_id] = location_totals.get(
                        location_id, Decimal("0")
                    ) + totals.get(item.id, Decimal("0"))
                    location_item_ids.setdefault(location_id, set()).add(item.id)
                item_rows.append(_item_view(item) | {
                    "stock_quantity": str(totals.get(item.id, Decimal("0"))),
                    "location_name": (
                        location_by_id[location_id].name
                        if location_id in location_by_id else None
                    ),
                })
            location_rows = [{
                "id": location.id,
                "name": location.name,
                "item_count": len(location_item_ids.get(location.id, set())),
                "stock_quantity": str(location_totals.get(location.id, Decimal("0"))),
            } for location in locations if location.id in location_item_ids]
            return {
                "owner": owner,
                "canonical_store": "inventory_service",
                "scope": "kitchen_and_household",
                "item_count": len(items),
                "items": item_rows,
                "locations": location_rows,
                "low_stock": low_stock,
                "expiring_lots": expiring,
                "pending_intake": [{
                    "id": draft.id, "source_type": draft.source_type,
                    "status": draft.status, "updated_at": draft.updated_at.isoformat(),
                } for draft in pending_drafts],
                "recipe_count": recipe_count,
                "recent_activity": recent,
                "freshness": {"computed_at": datetime.now(timezone.utc).isoformat(), "expiry_horizon_days": horizon},
                "authority_unchanged": True,
            }

    @staticmethod
    def _history_rows(db: Session, owner: str, *, item_by_id: dict[str, InventoryItem] | None = None, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        rows = db.query(InventoryMovement).filter_by(owner=owner).order_by(
            InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc(),
        ).limit(limit).all()
        if item_by_id is None:
            ids = {row.item_id for row in rows}
            item_by_id = {item.id: item for item in db.query(InventoryItem).filter(
                InventoryItem.owner == owner, InventoryItem.id.in_(list(ids) or ["__none__"]),
            ).all()}
        return [{
            "movement": _movement_view(row),
            "item": _item_view(item_by_id[row.item_id]) if row.item_id in item_by_id else None,
            "provenance": {"source_kind": row.source_kind, "source_id": row.source_id},
        } for row in rows]

    def inventory_history(self, owner: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return the append-only, owner-scoped movement history."""
        owner = _required_text(owner, "owner", maximum=255)
        with self._read() as db:
            return self._history_rows(db, owner, limit=limit)


class RecipeService(InventoryService):
    @staticmethod
    def _recipe(db: Session, owner: str, recipe_id: str) -> InventoryRecipe:
        recipe = db.query(InventoryRecipe).filter_by(id=recipe_id, owner=owner).one_or_none()
        if recipe is None:
            # Owner-facing references commonly use the title returned by a
            # preceding list/read turn. Resolve only a unique active recipe
            # within the canonical owner scope; never guess between copies.
            normalized = normalize_item_name(recipe_id)
            matches = db.query(InventoryRecipe).filter(
                InventoryRecipe.owner == owner,
                InventoryRecipe.normalized_name == normalized,
                InventoryRecipe.archived.is_(False),
            ).order_by(InventoryRecipe.id).all()
            if len(matches) == 1:
                recipe = matches[0]
        if recipe is None:
            raise InventoryNotFound("recipe not found")
        return recipe

    @staticmethod
    def _recipe_view(db: Session, recipe: InventoryRecipe) -> dict[str, Any]:
        ingredients = db.query(InventoryRecipeIngredient).filter_by(
            owner=recipe.owner, recipe_id=recipe.id
        ).order_by(InventoryRecipeIngredient.sort_order, InventoryRecipeIngredient.id).all()
        return {
            "id": recipe.id, "owner": recipe.owner, "name": recipe.name,
            "instructions": recipe.instructions, "servings": recipe.servings,
            "notes": recipe.notes,
            "source_url": recipe.source_url, "tags": list(recipe.tags_json or []),
            "image_refs": list(recipe.image_refs_json or []), "archived": bool(recipe.archived),
            "ingredients": [{
                "id": ingredient.id, "item_id": ingredient.item_id,
                "name": ingredient.ingredient_name, "quantity": ingredient.quantity,
                "unit": ingredient.unit, "optional": bool(ingredient.optional),
                "amount_kind": ingredient.amount_kind or "EXACT",
                "quantity_min": ingredient.quantity_min, "quantity_max": ingredient.quantity_max,
                "modifier": ingredient.modifier, "source_text": ingredient.source_text,
                "substitution_group": ingredient.substitution_group,
                "preparation": ingredient.preparation,
            } for ingredient in ingredients],
        }

    def create_recipe(
        self, owner: str, *, name: str, servings: Any,
        ingredients: Iterable[dict[str, Any]], instructions: str = "",
        notes: str | None = None,
        source_url: str | None = None, tags: Iterable[str] | None = None,
        image_refs: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        display_name = _required_text(name, "name", maximum=200)
        try:
            serving_count = parse_decimal(servings)
        except UnitError as exc:
            raise InventoryError(str(exc)) from exc
        specs = list(ingredients)
        if not specs:
            raise InventoryError("recipe must have at least one ingredient")
        with self._transaction() as db:
            recipe = InventoryRecipe(
                id=str(uuid4()), owner=_required_text(owner, "owner", maximum=255),
                name=display_name, normalized_name=normalize_item_name(display_name),
                instructions=str(instructions or ""), servings=serving_count,
                notes=_optional_text(notes, "notes", maximum=10000),
                source_url=_optional_text(source_url, "source_url", maximum=4000),
                tags_json=[str(tag) for tag in (tags or [])],
                image_refs_json=[str(ref) for ref in (image_refs or [])],
            )
            db.add(recipe)
            for index, spec in enumerate(specs):
                item_id = spec.get("item_id")
                item = self._item(db, owner, item_id) if item_id else None
                ingredient_name = item.name if item else _required_text(spec.get("name"), "ingredient name", maximum=200)
                amount_kind = str(spec.get("amount_kind") or "EXACT").strip().upper()
                allowed_kinds = {"EXACT", "APPROXIMATE", "RANGE", "TO_TASTE", "AS_NEEDED", "OPTIONAL", "UNSPECIFIED", "NOMINAL"}
                if amount_kind not in allowed_kinds:
                    raise InventoryError("unsupported recipe amount kind")
                raw_quantity = spec.get("quantity")
                raw_unit = spec.get("unit")
                expected_unit = None
                quantity = quantity_min = quantity_max = None
                if amount_kind in {"EXACT", "APPROXIMATE"}:
                    if raw_quantity is None or not raw_unit:
                        raise InventoryError("exact recipe ingredients need a quantity and unit")
                    expected_unit = item.default_unit if item else normalize_amount(1, raw_unit).unit
                    quantity = _canonical_amount(raw_quantity, raw_unit, expected_unit)
                elif amount_kind == "RANGE":
                    if not raw_unit or spec.get("quantity_min") is None or spec.get("quantity_max") is None:
                        raise InventoryError("range recipe ingredients need minimum, maximum, and unit")
                    expected_unit = item.default_unit if item else normalize_amount(1, raw_unit).unit
                    quantity_min = _canonical_amount(spec["quantity_min"], raw_unit, expected_unit)
                    quantity_max = _canonical_amount(spec["quantity_max"], raw_unit, expected_unit)
                    if quantity_min > quantity_max:
                        raise InventoryError("recipe ingredient range must be ordered")
                db.add(InventoryRecipeIngredient(
                    id=str(uuid4()), owner=owner, recipe_id=recipe.id,
                    item_id=item.id if item else None, ingredient_name=ingredient_name,
                    quantity=quantity, unit=expected_unit, amount_kind=amount_kind,
                    quantity_min=quantity_min, quantity_max=quantity_max,
                    modifier=_optional_text(spec.get("modifier"), "modifier", maximum=200),
                    source_text=_optional_text(spec.get("source_text") or spec.get("name"), "source_text", maximum=500),
                    optional=bool(spec.get("optional", False)),
                    substitution_group=_optional_text(spec.get("substitution_group"), "substitution_group"),
                    preparation=_optional_text(spec.get("preparation"), "preparation"),
                    sort_order=index,
                ))
            db.flush()
            return self._recipe_view(db, recipe)

    def get_recipe(self, owner: str, recipe_id: str) -> dict[str, Any]:
        with self._read() as db:
            return self._recipe_view(db, self._recipe(db, owner, recipe_id))

    def list_recipes(self, owner: str, *, include_archived: bool = False) -> list[dict[str, Any]]:
        with self._read() as db:
            query = db.query(InventoryRecipe).filter_by(owner=owner)
            if not include_archived:
                query = query.filter(InventoryRecipe.archived.is_(False))
            recipes = query.order_by(InventoryRecipe.normalized_name, InventoryRecipe.id).all()
            return [self._recipe_view(db, recipe) for recipe in recipes]

    def _stock_plan(self, db: Session, owner: str, recipe: InventoryRecipe, servings: Any) -> RecipeStockPlan:
        requested = parse_decimal(servings)
        multiplier = requested / recipe.servings
        ingredients = db.query(InventoryRecipeIngredient).filter_by(
            owner=owner, recipe_id=recipe.id
        ).order_by(InventoryRecipeIngredient.sort_order).all()
        requirements: list[RecipeRequirement] = []
        candidate_items: dict[str, tuple[InventoryItem, str]] = {}
        for ingredient in ingredients:
            item_query = db.query(InventoryItem).filter(
                InventoryItem.owner == owner, InventoryItem.archived.is_(False)
            )
            if ingredient.item_id:
                item_query = item_query.filter(InventoryItem.id == ingredient.item_id)
            else:
                item_query = item_query.filter(
                    InventoryItem.normalized_name == normalize_item_name(ingredient.ingredient_name)
                )
            items = item_query.all()
            requirements.append(RecipeRequirement(
                ingredient.ingredient_name, ingredient.quantity, ingredient.unit,
                bool(ingredient.optional), ingredient.amount_kind or "EXACT",
                ingredient.quantity_min, ingredient.quantity_max, ingredient.modifier,
            ))
            for item in items:
                # A repeated ingredient must share one stock balance rather
                # than duplicating the same lots in the planner input.
                candidate_items[item.id] = (item, ingredient.ingredient_name)
        lots: list[StockLot] = []
        for item, ingredient_name in candidate_items.values():
            for lot in db.query(InventoryLot).filter(
                InventoryLot.owner == owner, InventoryLot.item_id == item.id,
                InventoryLot.quantity > 0,
            ).with_for_update().all():
                lots.append(StockLot(
                    lot.id, item.id, ingredient_name,
                    lot.quantity, lot.unit, lot.expiry_date,
                ))
        return plan_recipe_stock(requirements, lots, servings_multiplier=multiplier)

    def can_make(self, owner: str, recipe_id: str, *, servings: Any | None = None) -> RecipeStockPlan:
        with self._read() as db:
            recipe = self._recipe(db, owner, recipe_id)
            return self._stock_plan(db, owner, recipe, servings if servings is not None else recipe.servings)

    def shopping_requirements(self, owner: str, recipe_id: str, *, servings: Any | None = None) -> dict[str, Any]:
        """Return deterministic missing ingredients for one canonical recipe.

        This is a read-only projection over the same stock planner used by
        ``can_make``.  It deliberately creates no shopping-list state and
        never treats a recipe suggestion as proof of possession.
        """
        recipe = self.get_recipe(owner, recipe_id)
        requested = servings if servings is not None else recipe["servings"]
        plan = self.can_make(owner, recipe_id, servings=requested)
        return {
            "status": "SUCCESS",
            "result_type": "recipe_shopping_requirements",
            "operation": "shopping_requirements",
            "canonical_store": "inventory_service",
            "recipe_id": recipe["id"],
            "recipe_name": recipe["name"],
            "servings": requested,
            "can_make": plan.can_make,
            "missing_ingredients": [{
                "name": row.name, "quantity": row.missing,
                "unit": row.unit, "optional": row.optional,
                "amount_kind": row.amount_kind, "modifier": row.modifier,
                "quantity_min": row.quantity_min, "quantity_max": row.quantity_max,
            } for row in plan.shortages],
        }

    def expiring_recipe_candidates(self, owner: str, *, expiry_days: Any = 30) -> dict[str, Any]:
        """Compose expiring canonical stock with deterministic recipe coverage.

        This is a read-only projection over the Inventory Service.  It does
        not claim that a recipe is available merely because an ingredient is
        expiring: each candidate is checked against the complete canonical
        stock plan and reports any shortages explicitly.
        """
        owner = _required_text(owner, "owner", maximum=255)
        try:
            horizon = max(0, min(int(expiry_days), 365))
        except (TypeError, ValueError) as exc:
            raise InventoryError("expiry_days must be an integer") from exc
        today = date.today()
        cutoff = today + timedelta(days=horizon)
        with self._read() as db:
            items = db.query(InventoryItem).filter(
                InventoryItem.owner == owner,
                InventoryItem.domain.in_(("kitchen", "household")),
                InventoryItem.archived.is_(False),
            ).all()
            item_by_id = {item.id: item for item in items}
            lots = db.query(InventoryLot).filter(
                InventoryLot.owner == owner,
                InventoryLot.item_id.in_(list(item_by_id) or ["__none__"]),
                InventoryLot.quantity > 0,
                InventoryLot.expiry_date.is_not(None),
                InventoryLot.expiry_date <= cutoff,
            ).order_by(InventoryLot.expiry_date, InventoryLot.id).all()
            expiring_by_id: dict[str, list[dict[str, Any]]] = {}
            for lot in lots:
                item = item_by_id[lot.item_id]
                expiring_by_id.setdefault(item.id, []).append({
                    "item_id": item.id,
                    "name": item.name,
                    "quantity": lot.quantity,
                    "unit": lot.unit,
                    "expiry_date": lot.expiry_date,
                    "status": "expired" if lot.expiry_date < today else "expiring",
                })
            candidates = []
            recipes = db.query(InventoryRecipe).filter_by(
                owner=owner, archived=False,
            ).order_by(InventoryRecipe.normalized_name, InventoryRecipe.id).all()
            for recipe in recipes:
                ingredients = db.query(InventoryRecipeIngredient).filter_by(
                    owner=owner, recipe_id=recipe.id,
                ).all()
                related = []
                for ingredient in ingredients:
                    if ingredient.item_id in expiring_by_id:
                        related.extend(expiring_by_id[ingredient.item_id])
                        continue
                    normalized = normalize_item_name(ingredient.ingredient_name)
                    related.extend(
                        entry for item_id, entries in expiring_by_id.items()
                        if normalize_item_name(item_by_id[item_id].name) == normalized
                        for entry in entries
                    )
                if not related:
                    continue
                plan = self._stock_plan(db, owner, recipe, recipe.servings)
                candidates.append({
                    "recipe_id": recipe.id,
                    "recipe_name": recipe.name,
                    "can_make": plan.can_make,
                    "expiring_ingredients": related,
                    "shortages": [{
                        "name": row.name, "missing": row.missing,
                        "unit": row.unit, "optional": row.optional,
                        "amount_kind": row.amount_kind, "modifier": row.modifier,
                        "quantity_min": row.quantity_min, "quantity_max": row.quantity_max,
                    } for row in plan.shortages],
                })
            return {
                "status": "SUCCESS",
                "result_type": "recipe_expiring_candidates",
                "operation": "expiring_candidates",
                "candidates": candidates,
                "expiry_days": horizon,
                "freshness": {"computed_at": datetime.now(timezone.utc).isoformat()},
                "canonical_store": "inventory_service",
                "owner_scope": owner,
            }

    def pantry_recipe_candidates(self, owner: str) -> dict[str, Any]:
        """Check every recorded recipe against current stock without writing.

        This is the canonical projection for owner requests such as "what can
        I make with what I have?". Suggestions remain honest: every recipe
        includes its deterministic coverage result and any shortages.
        """
        owner = _required_text(owner, "owner", maximum=255)
        with self._read() as db:
            recipes = db.query(InventoryRecipe).filter_by(
                owner=owner, archived=False,
            ).order_by(InventoryRecipe.normalized_name, InventoryRecipe.id).all()
            candidates = []
            for recipe in recipes:
                plan = self._stock_plan(db, owner, recipe, recipe.servings)
                candidates.append({
                    "recipe_id": recipe.id,
                    "recipe_name": recipe.name,
                    "can_make": plan.can_make,
                    "shortages": [{
                        "name": row.name, "missing": row.missing,
                        "unit": row.unit, "optional": row.optional,
                        "amount_kind": row.amount_kind, "modifier": row.modifier,
                        "quantity_min": row.quantity_min, "quantity_max": row.quantity_max,
                    } for row in plan.shortages],
                })
            return {
                "status": "SUCCESS",
                "result_type": "recipe_pantry_candidates",
                "operation": "pantry_candidates",
                "candidates": candidates,
                "freshness": {"computed_at": datetime.now(timezone.utc).isoformat()},
                "canonical_store": "inventory_service",
                "owner_scope": owner,
            }

    def cook(
        self, owner: str, recipe_id: str, *, servings: Any | None = None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        key = _required_text(idempotency_key, "idempotency_key", maximum=255)
        with self._transaction() as db:
            prior = db.query(InventoryRecipeCook).filter_by(owner=owner, idempotency_key=key).one_or_none()
            if prior is not None:
                requested = parse_decimal(servings if servings is not None else prior.servings)
                if prior.recipe_id != recipe_id or prior.servings != requested:
                    raise InventoryConflict("idempotency key was already used for another cook")
                return {"id": prior.id, "recipe_id": prior.recipe_id, "servings": prior.servings,
                        "movement_ids": list(prior.movement_ids_json or []), "replayed": True}
            recipe = self._recipe(db, owner, recipe_id)
            try:
                requested = parse_decimal(servings if servings is not None else recipe.servings)
            except UnitError as exc:
                raise InventoryError(str(exc)) from exc
            cook = InventoryRecipeCook(
                id=str(uuid4()), owner=owner, recipe_id=recipe.id,
                servings=requested, idempotency_key=key, status="pending",
                movement_ids_json=[],
            )
            db.add(cook)
            db.flush()
            plan = self._stock_plan(db, owner, recipe, requested)
            if not plan.can_make:
                raise InsufficientStock(plan)
            lots = {lot.id: lot for lot in db.query(InventoryLot).filter(
                InventoryLot.owner == owner,
                InventoryLot.id.in_([deduction.lot_id for deduction in plan.deductions]),
            ).with_for_update().all()}
            movement_ids: list[str] = []
            for index, deduction in enumerate(plan.deductions):
                lot = lots[deduction.lot_id]
                changed = db.query(InventoryLot).filter(
                    InventoryLot.id == lot.id, InventoryLot.owner == owner,
                    InventoryLot.item_id == deduction.item_id,
                    InventoryLot.quantity >= deduction.quantity,
                ).update(
                    {InventoryLot.quantity: InventoryLot.quantity - deduction.quantity},
                    synchronize_session=False,
                )
                if changed != 1:
                    raise InsufficientStock(plan)
                movement = InventoryMovement(
                    id=str(uuid4()), owner=owner, item_id=deduction.item_id,
                    lot_id=lot.id, quantity_delta=-deduction.quantity,
                    unit=deduction.unit, reason="recipe", source_kind="recipe_cook",
                    source_id=cook.id, idempotency_key=f"cook:{cook.id}:{index}",
                )
                db.add(movement)
                movement_ids.append(movement.id)
            cook.movement_ids_json = movement_ids
            cook.status = "completed"
            db.flush()
            return {"id": cook.id, "recipe_id": recipe.id, "servings": requested,
                    "movement_ids": movement_ids, "replayed": False}

    def manage_inventory(self, args: dict[str, Any], *, owner: str) -> dict[str, Any]:
        """Dispatch the narrow model-facing inventory action vocabulary."""
        action = str(args.get("action") or "")
        if action == "list":
            return {"items": self.list_items(
                owner, domain=args.get("domain"),
                include_archived=bool(args.get("include_archived", False)),
            )}
        if action == "search":
            return {"items": self.search_items(
                owner, args.get("query"), domain=args.get("domain"),
            )}
        if action == "get":
            item = self.get_item(owner, _required_text(args.get("item_id"), "item_id"))
            result = {"item": item, "lots": self.list_lots(owner, item["id"])}
            if item["domain"] == "it" and item["item_kind"] == "asset":
                result["asset"] = self.get_asset_detail(owner, item["id"])
            return result
        if action == "get_components":
            item_id = _required_text(args.get("item_id"), "item_id")
            return {"components": self.list_asset_components(owner, item_id)}
        if action == "add_item":
            item = self.create_item(
                owner, name=args.get("name"), domain=args.get("domain"),
                item_kind=args.get("item_kind"),
                default_unit=args.get("default_unit") or args.get("unit") or "each",
                category=args.get("category"), description=args.get("description"),
                brand=args.get("brand"), manufacturer=args.get("manufacturer"),
                model=args.get("model"), sku=args.get("sku"), barcode=args.get("barcode"),
                location_id=args.get("location_id"),
                initial_quantity=args.get("initial_quantity"),
                initial_unit=args.get("initial_unit") or args.get("unit"),
            )
            return {"item": item}
        if action == "add_stock":
            kwargs: dict[str, Any] = {}
            if args.get("expiry_date"):
                try:
                    kwargs["expiry_date"] = date.fromisoformat(str(args["expiry_date"]))
                except ValueError as exc:
                    raise InventoryError("expiry_date must be an ISO date") from exc
            return self.add_stock(
                owner, _required_text(args.get("item_id"), "item_id"),
                quantity=args.get("quantity"), unit=args.get("unit"),
                idempotency_key=args.get("idempotency_key"),
                location_id=args.get("location_id"),
                location_name=args.get("location_name"), **kwargs,
            )
        if action == "update_asset":
            item_id = _required_text(args.get("item_id"), "item_id")
            allowed = {
                "serial_number", "asset_tag", "status", "condition", "acquired_at",
                "purchase_price", "currency", "warranty_expires_at", "hostname",
                "mac_addresses", "ip_addresses", "specs", "assigned_to", "parent_asset_id",
            }
            return {"asset": self.update_asset_detail(
                owner, item_id, **{key: args[key] for key in allowed if key in args},
            )}
        if action == "consume_stock":
            return self.consume_stock(
                owner, _required_text(args.get("item_id"), "item_id"),
                quantity=args.get("quantity"), unit=args.get("unit"),
                idempotency_key=args.get("idempotency_key"),
            )
        if action == "adjust_stock":
            return self.adjust_lot(
                owner, _required_text(args.get("lot_id"), "lot_id"),
                quantity_delta=args.get("quantity_delta"), unit=args.get("unit"),
                idempotency_key=args.get("idempotency_key"), note=args.get("notes"),
            )
        if action == "move_item":
            return self.move_item(
                owner, _required_text(args.get("item_id"), "item_id"),
                location_name=args.get("location_name"),
                idempotency_key=args.get("idempotency_key"),
            )
        if action in {"update_item", "move_stock", "archive_item"}:
            raise InventoryError(f"{action} is not available in this service version")
        raise InventoryError("unsupported inventory action")

    def recipe_cooking_history(self, owner: str) -> dict[str, Any]:
        """Return the bounded history projection owned by the recipe service.

        Recipe preparation events are not yet recorded as canonical state. An
        explicit empty projection lets the owner receive an honest answer
        instead of having a recipe list mistaken for cooking history.
        """
        return {
            "status": "SUCCESS_EMPTY",
            "result_type": "recipe_cooking_history",
            "operation": "cooking_history",
            "events": [],
            "canonical_store": "inventory_service",
            "owner_scope": owner,
        }

    def manage_recipes(self, args: dict[str, Any], *, owner: str) -> dict[str, Any]:
        """Dispatch the narrow model-facing recipe action vocabulary."""
        action = str(args.get("action") or "")
        if action == "prepare_import":
            from src.intent_contracts import (
                recipe_import_draft, recipe_import_review, recipe_import_review_draft,
                apply_recipe_owner_transformations,
            )
            draft = recipe_import_draft(
                args.get("source_text"),
                source_url=args.get("source_url"),
                requested_name=args.get("requested_name"),
            )
            if draft is None:
                review = recipe_import_review(
                    args.get("source_text"), source_url=args.get("source_url")
                )
                requested_name = str(args.get("requested_name") or "").strip()
                if requested_name:
                    review["requested_name"] = requested_name[:200]
                editable = recipe_import_review_draft(
                    args.get("source_text"),
                    source_url=args.get("source_url"),
                    requested_name=requested_name,
                )
                if editable is not None:
                    review = {**review, **editable.get("review", {})}
                    return {
                        "status": "NEEDS_REVIEW", "draft": editable,
                        "source_url": args.get("source_url"),
                        "message": (
                            "I found a recipe draft, but some ingredient amounts "
                            "need your review before anything can be saved."
                        ),
                        "review": review,
                    }
                return {
                    "status": "NEEDS_REVIEW", "draft": None,
                    "source_url": args.get("source_url"),
                    "message": "The source did not contain enough verified recipe structure to prepare a draft.",
                    "review": review,
                }
            draft = apply_recipe_owner_transformations(draft, args.get("owner_transformations"))
            return {"status": "READY_FOR_REVIEW", "draft": draft.as_payload()}
        if action == "list":
            return {
                "status": "SUCCESS",
                "result_type": "recipe_list",
                "operation": "list",
                "canonical_store": "inventory_service",
                "recipes": self.list_recipes(
                    owner, include_archived=bool(args.get("include_archived", False))
                ),
            }
        if action == "search":
            query = normalize_item_name(args.get("query"))
            return {
                "status": "SUCCESS",
                "result_type": "recipe_search",
                "operation": "search",
                "canonical_store": "inventory_service",
                "query": query,
                "recipes": [recipe for recipe in self.list_recipes(owner)
                            if query in normalize_item_name(recipe["name"])],
            }
        if action == "get":
            return {
                "status": "SUCCESS",
                "result_type": "recipe_detail",
                "operation": "get",
                "canonical_store": "inventory_service",
                "recipe": self.get_recipe(
                    owner, _required_text(args.get("recipe_id"), "recipe_id")
                ),
            }
        if action == "can_make":
            plan = self.can_make(
                owner, _required_text(args.get("recipe_id"), "recipe_id"),
                servings=args.get("servings"),
            )
            recipe = self.get_recipe(owner, _required_text(args.get("recipe_id"), "recipe_id"))
            return {
                "status": "SUCCESS",
                "result_type": "recipe_pantry_coverage",
                "operation": "can_make",
                "canonical_store": "inventory_service",
                "recipe_id": recipe["id"], "recipe_name": recipe["name"],
                "can_make": plan.can_make,
                "availability_status": "AVAILABLE" if plan.can_make else "MISSING_INGREDIENTS",
                "deductions": [{
                    "lot_id": row.lot_id, "item_id": row.item_id,
                    "quantity": row.quantity, "unit": row.unit,
                } for row in plan.deductions],
                "shortages": [{
                    "name": row.name, "missing": row.missing,
                    "unit": row.unit, "optional": row.optional,
                    "amount_kind": row.amount_kind, "modifier": row.modifier,
                    "quantity_min": row.quantity_min, "quantity_max": row.quantity_max,
                } for row in plan.shortages],
            }
        if action == "shopping_requirements":
            return self.shopping_requirements(
                owner, _required_text(args.get("recipe_id"), "recipe_id"),
                servings=args.get("servings"),
            )
        if action == "scale":
            recipe = self.get_recipe(owner, _required_text(args.get("recipe_id"), "recipe_id"))
            requested = parse_decimal(args.get("servings"))
            base = parse_decimal(recipe.get("servings"))
            multiplier = requested / base
            return {
                "status": "SUCCESS",
                "result_type": "recipe_scaled_quantities",
                "operation": "scale",
                "canonical_store": "inventory_service",
                "recipe_id": recipe["id"], "recipe_name": recipe["name"],
                "servings": requested,
                "scaled_ingredients": [{
                    "name": ingredient["name"],
                    "quantity": (parse_decimal(ingredient["quantity"]) * multiplier) if ingredient.get("quantity") is not None else None,
                    "quantity_min": (parse_decimal(ingredient["quantity_min"]) * multiplier) if ingredient.get("quantity_min") is not None else None,
                    "quantity_max": (parse_decimal(ingredient["quantity_max"]) * multiplier) if ingredient.get("quantity_max") is not None else None,
                    "unit": ingredient["unit"],
                    "optional": ingredient["optional"],
                    "amount_kind": ingredient.get("amount_kind", "EXACT"),
                    "modifier": ingredient.get("modifier"),
                    "source_text": ingredient.get("source_text"),
                } for ingredient in recipe.get("ingredients", [])],
            }
        if action == "expiring_candidates":
            return self.expiring_recipe_candidates(
                owner, expiry_days=args.get("expiry_days", 30),
            )
        if action == "pantry_candidates":
            return self.pantry_recipe_candidates(owner)
        if action == "add":
            return {"recipe": self.create_recipe(
                owner, name=args.get("name"), servings=args.get("servings") or "1",
                ingredients=args.get("ingredients") or [],
                instructions=args.get("instructions") or "",
                source_url=args.get("source_url"), tags=args.get("tags"),
                image_refs=args.get("image_refs"),
            )}
        if action == "commit_import":
            from src.intent_contracts import RecipeDraft, apply_recipe_owner_transformations
            draft = RecipeDraft.from_payload(args.get("draft") or args)
            draft = apply_recipe_owner_transformations(draft, args.get("owner_transformations"))
            # Import commits can be replayed when an approval stream is
            # resumed.  Treat the source URL plus owner-visible recipe name
            # as the import identity so a successful retry cannot create a
            # second canonical row.
            if draft.source_url:
                with self._read() as db:
                    existing = db.query(InventoryRecipe).filter(
                        InventoryRecipe.owner == owner,
                        InventoryRecipe.source_url == draft.source_url,
                        InventoryRecipe.normalized_name == normalize_item_name(draft.name),
                        InventoryRecipe.archived.is_(False),
                    ).order_by(InventoryRecipe.id).first()
                    if existing is not None:
                        readback = self._recipe_view(db, existing)
                        return {
                            "success": True, "recipe": readback,
                            "deduplicated": True,
                            "verification": {"status": "VERIFIED", "recipe_id": readback["id"]},
                            "source": draft.provenance,
                        }
            recipe = self.create_recipe(
                owner, name=draft.name, servings=draft.servings,
                ingredients=draft.ingredients, instructions=draft.instructions,
                notes=draft.notes,
                source_url=draft.source_url, tags=args.get("tags"), image_refs=args.get("image_refs"),
            )
            readback = self.get_recipe(owner, recipe["id"])
            if readback.get("id") != recipe.get("id"):
                raise InventoryError("recipe import readback did not match the committed recipe")
            return {"success": True, "recipe": readback,
                    "verification": {"status": "VERIFIED", "recipe_id": readback["id"]},
                    "source": draft.provenance}
        if action == "cook":
            return {"cook": self.cook(
                owner, _required_text(args.get("recipe_id"), "recipe_id"),
                servings=args.get("servings"),
                idempotency_key=args.get("idempotency_key"),
            )}
        if action in {"update", "archive"}:
            raise InventoryError(f"{action} is not available in this service version")
        raise InventoryError("unsupported recipe action")


def get_inventory_service(session_factory=SessionLocal) -> RecipeService:
    """Return the combined inventory/recipe facade used by narrow adapters."""
    return RecipeService(session_factory)
