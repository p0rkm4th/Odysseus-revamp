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
    InventorySharePolicy,
)
from core.finance_models import Household, HouseholdMembership
from src.inventory_planning import (
    RecipeRequirement,
    RecipeStockPlan,
    StockLot,
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
_RECIPE_LIKE_GROCERY_NAME = re.compile(
    r"\b(?:everything|all)\s+(?:that\s+is\s+)?needed\s+to\s+make\b|"
    r"\b(?:ingredients?|items?)\s+(?:needed\s+)?for\b",
    re.IGNORECASE,
)
_NON_ITEM_GROCERY_NAME = re.compile(
    # Conversational models sometimes echo the owner's request fragment as a
    # fourth "item" (for example, "the ingredients I am missing").  A
    # grocery record must be a concrete thing to buy, never that placeholder.
    r"^(?:the\s+|those\s+|these\s+|my\s+|some\s+|all\s+)?(?:ingredients?|items?)\b",
    re.IGNORECASE,
)
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


def _validate_grocery_name(name: str, shopping_list: bool) -> None:
    """Reject recipe placeholders at every grocery write boundary."""
    if not shopping_list:
        return
    if _RECIPE_LIKE_GROCERY_NAME.search(name):
        raise InventoryError(
            "this describes a recipe rather than one grocery item; "
            "no grocery change was made"
        )
    # The expression intentionally matches a conversational suffix as well;
    # ``ingredients I am missing`` is still a placeholder, not an item.
    if _NON_ITEM_GROCERY_NAME.match(name.strip()):
        raise InventoryError(
            "please provide the individual grocery items or a saved recipe; "
            "no grocery change was made"
        )


def _is_grocery_placeholder(name: str) -> bool:
    return bool(
        _RECIPE_LIKE_GROCERY_NAME.search(name)
        or _NON_ITEM_GROCERY_NAME.match(name.strip())
    )


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
        "shopping_list": bool(item.shopping_list),
        "storage_area": item.storage_area,
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

    @staticmethod
    def _shared_owner_ids(
        db: Session, actor: str, resource: str = "kitchen_inventory",
    ) -> set[str]:
        """Return owners whose resource is explicitly shared with ``actor``."""
        rows = db.query(InventorySharePolicy.household_id).join(
            HouseholdMembership,
            HouseholdMembership.household_id == InventorySharePolicy.household_id,
        ).filter(
            HouseholdMembership.user_id == actor,
            InventorySharePolicy.resource == resource,
            InventorySharePolicy.enabled.is_(True),
        ).all()
        household_ids = {row[0] for row in rows}
        if not household_ids:
            return {actor}
        members = db.query(HouseholdMembership.user_id).filter(
            HouseholdMembership.household_id.in_(household_ids),
        ).all()
        return {actor, *(row[0] for row in members)}

    @classmethod
    def _item_for_actor(cls, db: Session, actor: str, item_id: str) -> InventoryItem:
        item = db.query(InventoryItem).filter_by(id=item_id).one_or_none()
        if item is None:
            raise InventoryNotFound("inventory item not found")
        if item.owner == actor:
            return item
        if item.domain in {"kitchen", "household"} and item.owner in cls._shared_owner_ids(db, actor):
            return item
        raise InventoryNotFound("inventory item not found")

    @classmethod
    def _member_mutation_allowed(cls, db: Session, actor: str, resource_owner: str) -> bool:
        if actor == resource_owner:
            return True
        policies = db.query(InventorySharePolicy).join(
            HouseholdMembership,
            HouseholdMembership.household_id == InventorySharePolicy.household_id,
        ).filter(
            HouseholdMembership.user_id == actor,
            InventorySharePolicy.resource == "kitchen_inventory",
            InventorySharePolicy.enabled.is_(True),
            InventorySharePolicy.allow_member_mutation.is_(True),
        ).all()
        household_ids = {policy.household_id for policy in policies}
        if not household_ids:
            return False
        return db.query(HouseholdMembership.id).filter(
            HouseholdMembership.household_id.in_(household_ids),
            HouseholdMembership.user_id == resource_owner,
        ).first() is not None

    @classmethod
    def _mutable_item_for_actor(cls, db: Session, actor: str, item_id: str) -> InventoryItem:
        item = cls._item_for_actor(db, actor, item_id)
        if not cls._member_mutation_allowed(db, actor, item.owner):
            raise InventoryNotFound("inventory item not found")
        return item

    @classmethod
    def _mutable_lot_for_actor(cls, db: Session, actor: str, lot_id: str) -> InventoryLot:
        lot = db.query(InventoryLot).filter_by(id=lot_id).one_or_none()
        if lot is None:
            raise InventoryNotFound("inventory lot not found")
        cls._mutable_item_for_actor(db, actor, lot.item_id)
        return lot

    def list_sharing(self, actor: str) -> list[dict[str, Any]]:
        """Return household memberships and explicit inventory policies."""
        with self._read() as db:
            memberships = db.query(HouseholdMembership, Household).join(
                Household, Household.id == HouseholdMembership.household_id,
            ).filter(HouseholdMembership.user_id == actor).order_by(
                HouseholdMembership.created_at.asc(), Household.id,
            ).all()
            result = []
            for membership, household in memberships:
                policies = db.query(InventorySharePolicy).filter_by(
                    household_id=household.id,
                ).all()
                by_resource = {policy.resource: {
                    "enabled": bool(policy.enabled),
                    "allow_member_mutation": bool(policy.allow_member_mutation),
                } for policy in policies}
                result.append({
                    "household_id": household.id,
                    "household_name": household.name,
                    "role": membership.role,
                    "can_manage": household.owner == actor,
                    "resources": {resource: by_resource.get(resource, {
                        "enabled": False, "allow_member_mutation": False,
                    }) for resource in ("kitchen_inventory", "recipes")},
                })
            return result

    def configure_sharing(
        self, actor: str, household_id: str, *, resource: str,
        enabled: bool, allow_member_mutation: bool = False,
    ) -> dict[str, Any]:
        resource = str(resource or "").strip().casefold()
        if resource not in {"kitchen_inventory", "recipes"}:
            raise InventoryError("unsupported household sharing resource")
        if allow_member_mutation and resource != "kitchen_inventory":
            raise InventoryError("member mutation is only available for kitchen inventory")
        with self._transaction() as db:
            household = db.get(Household, household_id)
            membership = db.query(HouseholdMembership).filter_by(
                household_id=household_id, user_id=actor,
            ).one_or_none()
            if household is None or household.owner != actor or membership is None:
                raise InventoryNotFound("household sharing configuration not found")
            if allow_member_mutation and not enabled:
                raise InventoryError("member mutation requires shared inventory to be enabled")
            policy = db.query(InventorySharePolicy).filter_by(
                household_id=household_id, resource=resource,
            ).one_or_none()
            if policy is None:
                policy = InventorySharePolicy(
                    id=str(uuid4()), household_id=household_id, resource=resource,
                )
                db.add(policy)
            policy.enabled = bool(enabled)
            policy.allow_member_mutation = bool(allow_member_mutation)
            db.flush()
            return {"household_id": household_id, "resource": resource,
                    "enabled": bool(policy.enabled),
                    "allow_member_mutation": bool(policy.allow_member_mutation)}

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
        shopping_list: bool = False,
        storage_area: str | None = None,
        location_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        image_refs: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        owner = _required_text(owner, "owner", maximum=255)
        display_name = _required_text(name, "name", maximum=200)
        domain = str(domain).strip().casefold()
        item_kind = str(item_kind).strip().casefold()
        if domain not in _DOMAINS:
            raise InventoryError("unsupported inventory domain")
        if item_kind not in _KINDS:
            raise InventoryError("unsupported inventory item kind")
        _validate_grocery_name(display_name, bool(shopping_list))
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
                shopping_list=bool(shopping_list),
                storage_area=self._storage_area(storage_area),
                metadata_json=dict(metadata or {}),
                image_refs_json=[str(ref) for ref in (image_refs or [])],
            )
            db.add(item)
            db.flush()
            return _item_view(item)

    def update_item(
        self, owner: str, item_id: str, *, name: Any = _UNSET,
        category: Any = _UNSET, description: Any = _UNSET,
        default_unit: Any = _UNSET, reorder_point: Any = _UNSET,
        shopping_list: Any = _UNSET, storage_area: Any = _UNSET,
    ) -> dict[str, Any]:
        """Update human-facing pantry/grocery metadata, never stock implicitly."""
        with self._transaction() as db:
            item = self._mutable_item_for_actor(db, owner, item_id)
            next_name = item.name if name is _UNSET else _required_text(name, "name", maximum=200)
            next_shopping_list = item.shopping_list if shopping_list is _UNSET else bool(shopping_list)
            _validate_grocery_name(next_name, next_shopping_list)
            if name is not _UNSET:
                item.name = next_name
                item.normalized_name = normalize_item_name(next_name)
            if category is not _UNSET:
                item.category = _optional_text(category, "category")
            if description is not _UNSET:
                item.description = _optional_text(description, "description", maximum=10000)
            if default_unit is not _UNSET:
                try:
                    item.default_unit = normalize_amount(1, default_unit).unit
                except UnitError as exc:
                    raise InventoryError(str(exc)) from exc
            if reorder_point is not _UNSET:
                item.reorder_point = None if reorder_point in (None, "") else _canonical_amount(reorder_point, item.default_unit, item.default_unit)
            if shopping_list is not _UNSET:
                item.shopping_list = next_shopping_list
            if storage_area is not _UNSET:
                item.storage_area = self._storage_area(storage_area)
            db.flush()
            return _item_view(item)

    def archive_item(self, owner: str, item_id: str) -> dict[str, Any]:
        with self._transaction() as db:
            item = self._mutable_item_for_actor(db, owner, item_id)
            item.archived = True
            db.flush()
            return _item_view(item)

    def get_item(self, owner: str, item_id: str) -> dict[str, Any]:
        with self._read() as db:
            return _item_view(self._item_for_actor(db, owner, item_id))

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
        self, owner: str, *, domain: str | None = None, list_name: str | None = None,
        include_archived: bool = False, limit: int = 100, offset: int = 0,
        include_stock: bool = False,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        with self._read() as db:
            owners = self._shared_owner_ids(db, owner)
            query = db.query(InventoryItem).filter(InventoryItem.owner.in_(owners))
            normalized_list = str(list_name).strip().casefold() if list_name else ""
            if domain is not None:
                query = query.filter(InventoryItem.domain == str(domain).casefold())
            if list_name:
                if normalized_list == "grocery":
                    query = query.filter(InventoryItem.shopping_list.is_(True))
                elif normalized_list in {"pantry", "fridge", "freezer"}:
                    query = query.filter(InventoryItem.storage_area == normalized_list)
                else:
                    raise InventoryError("list_name must be grocery, pantry, fridge, or freezer")
            if not include_archived:
                query = query.filter(InventoryItem.archived.is_(False))
            items = list(query.order_by(InventoryItem.normalized_name, InventoryItem.id).offset(offset).limit(limit))
            views = [_item_view(item) for item in items]
            # Storage-list reads must expose the same canonical lot balance
            # used by consume_stock and household_overview.  Grocery is a
            # missing/to-buy projection and intentionally has no stock total.
            if (include_stock or normalized_list in {"pantry", "fridge", "freezer"}) and items:
                item_ids = [item.id for item in items]
                lots = db.query(InventoryLot).filter(
                    InventoryLot.owner.in_(owners),
                    InventoryLot.item_id.in_(item_ids),
                    InventoryLot.quantity > 0,
                ).all()
                totals: dict[str, Decimal] = {}
                for lot in lots:
                    totals[lot.item_id] = totals.get(lot.item_id, Decimal("0")) + Decimal(str(lot.quantity))
                for item, view in zip(items, views):
                    view["stock_quantity"] = str(totals.get(item.id, Decimal("0")))
            return views

    def search_items(
        self, owner: str, query: str, *, domain: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        term = normalize_item_name(query)
        limit = max(1, min(int(limit), 200))
        with self._read() as db:
            owners = self._shared_owner_ids(db, owner)
            statement = db.query(InventoryItem).filter(
                InventoryItem.owner.in_(owners),
                InventoryItem.archived.is_(False),
                InventoryItem.normalized_name.contains(term),
            )
            if domain is not None:
                statement = statement.filter(InventoryItem.domain == str(domain).casefold())
            return [_item_view(item) for item in statement.order_by(
                InventoryItem.normalized_name, InventoryItem.id
            ).limit(limit)]

    def add_stock(
        self, owner: str, item_id: str, *, quantity: Any, unit: str,
        idempotency_key: str, location_id: str | None = None,
        expiry_date: date | None = None, opened_at: datetime | None = None,
        purchase_date: date | None = None, unit_cost: Any | None = None,
        currency: str | None = None, lot_code: str | None = None,
        actor: str | None = None, session_id: str | None = None,
    ) -> dict[str, Any]:
        key = _required_text(idempotency_key, "idempotency_key", maximum=255)
        with self._transaction() as db:
            item = self._mutable_item_for_actor(db, owner, item_id)
            resource_owner = item.owner
            prior = db.query(InventoryMovement).filter_by(
                owner=resource_owner, idempotency_key=key,
            ).one_or_none()
            if prior is not None:
                expected = _canonical_amount(quantity, unit, prior.unit)
                if prior.reason != "add" or prior.item_id != item_id or prior.quantity_delta != expected:
                    raise InventoryConflict("idempotency key was already used for another operation")
                lot = self._lot(db, resource_owner, prior.lot_id)
                return {"lot": _lot_view(lot), "movement": _movement_view(prior), "replayed": True}
            self._location(db, resource_owner, location_id)
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
                id=str(uuid4()), owner=resource_owner, item_id=item.id,
                location_id=location_id or item.location_id, quantity=amount,
                unit=item.default_unit, expiry_date=expiry_date, opened_at=opened_at,
                purchase_date=purchase_date, unit_cost=cost,
                currency=str(currency).upper() if currency else None,
                lot_code=_optional_text(lot_code, "lot_code"),
            )
            movement = InventoryMovement(
                id=str(uuid4()), owner=resource_owner, item_id=item.id, lot_id=lot.id,
                quantity_delta=amount, unit=item.default_unit, reason="add",
                source_kind="stock_add", source_id=key, idempotency_key=key,
                actor=actor or owner, session_id=session_id,
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
            item = self._mutable_item_for_actor(db, owner, item_id)
            resource_owner = item.owner
            prior = db.query(InventoryMovement).filter_by(
                owner=resource_owner, source_kind="stock_consume", source_id=key
            ).order_by(InventoryMovement.idempotency_key).all()
            if prior:
                requested = _canonical_amount(quantity, unit, prior[0].unit)
                consumed = sum((-movement.quantity_delta for movement in prior), Decimal("0"))
                if any(m.item_id != item_id or m.reason != reason for m in prior) or consumed != requested:
                    raise InventoryConflict("idempotency key was already used for another operation")
                return {"movements": [_movement_view(m) for m in prior], "quantity": consumed, "replayed": True}
            requested = _canonical_amount(quantity, unit, item.default_unit)
            lots = db.query(InventoryLot).filter(
                InventoryLot.owner == resource_owner, InventoryLot.item_id == item.id,
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
                    InventoryLot.id == lot.id, InventoryLot.owner == resource_owner,
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
                    id=str(uuid4()), owner=resource_owner, item_id=item.id, lot_id=lot.id,
                    quantity_delta=-deduction.quantity, unit=item.default_unit,
                    reason=reason, source_kind="stock_consume", source_id=key,
                    idempotency_key=_movement_key(key, index), actor=actor or owner,
                    session_id=session_id,
                )
                db.add(movement)
                movements.append(movement)
            remaining = db.query(InventoryLot).filter(
                InventoryLot.owner == resource_owner, InventoryLot.item_id == item.id,
                InventoryLot.quantity > 0,
            ).count()
            if remaining == 0:
                # Depletion is a canonical grocery signal. It does not add
                # stock or alter ownership; it only queues the existing item
                # for the owner's next shopping pass.
                item.shopping_list = True
            db.flush()
            return {"movements": [_movement_view(m) for m in movements], "quantity": requested, "depleted": remaining == 0, "replayed": False}

    def adjust_lot(
        self, owner: str, lot_id: str, *, quantity_delta: Any, unit: str,
        idempotency_key: str, note: str | None = None,
    ) -> dict[str, Any]:
        key = _required_text(idempotency_key, "idempotency_key", maximum=255)
        with self._transaction() as db:
            lot = self._mutable_lot_for_actor(db, owner, lot_id)
            resource_owner = lot.owner
            prior = db.query(InventoryMovement).filter_by(
                owner=resource_owner, idempotency_key=key,
            ).one_or_none()
            if prior is not None:
                delta = normalize_amount(quantity_delta, unit, positive=False).quantity
                if prior.reason != "adjust" or prior.lot_id != lot_id or prior.quantity_delta != delta:
                    raise InventoryConflict("idempotency key was already used for another operation")
                return {"lot": _lot_view(self._lot(db, resource_owner, lot_id)), "movement": _movement_view(prior), "replayed": True}
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
                InventoryLot.id == lot.id, InventoryLot.owner == resource_owner,
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
                id=str(uuid4()), owner=resource_owner, item_id=lot.item_id, lot_id=lot.id,
                quantity_delta=delta.quantity, unit=lot.unit, reason="adjust",
                source_kind="stock_adjust", source_id=key, idempotency_key=key,
                note=_optional_text(note, "note", maximum=10000), actor=owner,
            )
            db.add(movement)
            db.flush()
            return {"lot": _lot_view(lot), "movement": _movement_view(movement), "replayed": False}

    def list_lots(self, owner: str, item_id: str) -> list[dict[str, Any]]:
        with self._read() as db:
            item = self._item_for_actor(db, owner, item_id)
            lots = db.query(InventoryLot).filter_by(owner=item.owner, item_id=item_id).order_by(
                InventoryLot.expiry_date.is_(None), InventoryLot.expiry_date, InventoryLot.id
            ).all()
            return [_lot_view(lot) for lot in lots]

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
            owners = self._shared_owner_ids(db, owner)
            items = db.query(InventoryItem).filter(
                InventoryItem.owner.in_(owners),
                InventoryItem.domain.in_(("kitchen", "household")),
                InventoryItem.archived.is_(False),
            ).order_by(InventoryItem.normalized_name, InventoryItem.id).all()
            item_by_id = {item.id: item for item in items}
            lots = db.query(InventoryLot).filter(
                InventoryLot.owner.in_(owners),
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
            recent = self._history_rows(db, owner, item_by_id=item_by_id, owners=owners, limit=10)
            return {
                "owner": owner,
                "canonical_store": "inventory_service",
                "scope": "kitchen_and_household",
                "item_count": len(items),
                "items": [_item_view(item) | {"stock_quantity": str(totals.get(item.id, Decimal("0")))} for item in items],
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
    def _history_rows(
        db: Session, owner: str, *, item_by_id: dict[str, InventoryItem] | None = None,
        owners: set[str] | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        visible_owners = owners or {owner}
        rows = db.query(InventoryMovement).filter(
            InventoryMovement.owner.in_(visible_owners),
        ).order_by(
            InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc(),
        ).limit(limit).all()
        if item_by_id is None:
            ids = {row.item_id for row in rows}
            item_by_id = {item.id: item for item in db.query(InventoryItem).filter(
                InventoryItem.owner.in_(visible_owners),
                InventoryItem.id.in_(list(ids) or ["__none__"]),
            ).all()}
        return [{
            "movement": _movement_view(row),
            "item": _item_view(item_by_id[row.item_id]) if row.item_id in item_by_id else None,
            "provenance": {"source_kind": row.source_kind, "source_id": row.source_id},
        } for row in rows]

    def inventory_history(self, owner: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return the append-only movement history visible to the owner."""
        owner = _required_text(owner, "owner", maximum=255)
        with self._read() as db:
            return self._history_rows(
                db, owner, owners=self._shared_owner_ids(db, owner), limit=limit,
            )


class RecipeService(InventoryService):
    @staticmethod
    def _recipe(db: Session, owner: str, recipe_id: str) -> InventoryRecipe:
        recipe = db.query(InventoryRecipe).filter_by(id=recipe_id, owner=owner).one_or_none()
        if recipe is None:
            raise InventoryNotFound("recipe not found")
        return recipe

    @classmethod
    def _recipe_for_actor(cls, db: Session, actor: str, recipe_id: str) -> InventoryRecipe:
        recipe = db.query(InventoryRecipe).filter_by(id=recipe_id).one_or_none()
        if recipe is None:
            raise InventoryNotFound("recipe not found")
        if recipe.owner == actor or recipe.owner in cls._shared_owner_ids(db, actor, "recipes"):
            return recipe
        raise InventoryNotFound("recipe not found")

    @staticmethod
    def _recipe_view(db: Session, recipe: InventoryRecipe) -> dict[str, Any]:
        ingredients = db.query(InventoryRecipeIngredient).filter_by(
            owner=recipe.owner, recipe_id=recipe.id
        ).order_by(InventoryRecipeIngredient.sort_order, InventoryRecipeIngredient.id).all()
        return {
            "id": recipe.id, "owner": recipe.owner, "name": recipe.name,
            "instructions": recipe.instructions, "servings": recipe.servings,
            "source_url": recipe.source_url, "tags": list(recipe.tags_json or []),
            "image_refs": list(recipe.image_refs_json or []), "archived": bool(recipe.archived),
            "ingredients": [{
                "id": ingredient.id, "item_id": ingredient.item_id,
                "name": ingredient.ingredient_name, "quantity": ingredient.quantity,
                "unit": ingredient.unit, "optional": bool(ingredient.optional),
                "substitution_group": ingredient.substitution_group,
                "preparation": ingredient.preparation,
            } for ingredient in ingredients],
        }

    def create_recipe(
        self, owner: str, *, name: str, servings: Any,
        ingredients: Iterable[dict[str, Any]], instructions: str = "",
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
                source_url=_optional_text(source_url, "source_url", maximum=4000),
                tags_json=[str(tag) for tag in (tags or [])],
                image_refs_json=[str(ref) for ref in (image_refs or [])],
            )
            db.add(recipe)
            for index, spec in enumerate(specs):
                item_id = spec.get("item_id")
                item = self._item(db, owner, item_id) if item_id else None
                ingredient_name = item.name if item else _required_text(spec.get("name"), "ingredient name", maximum=200)
                expected_unit = item.default_unit if item else normalize_amount(1, spec.get("unit")).unit
                quantity = _canonical_amount(spec.get("quantity"), spec.get("unit"), expected_unit)
                db.add(InventoryRecipeIngredient(
                    id=str(uuid4()), owner=owner, recipe_id=recipe.id,
                    item_id=item.id if item else None, ingredient_name=ingredient_name,
                    quantity=quantity, unit=expected_unit, optional=bool(spec.get("optional", False)),
                    substitution_group=_optional_text(spec.get("substitution_group"), "substitution_group"),
                    preparation=_optional_text(spec.get("preparation"), "preparation"),
                    sort_order=index,
                ))
            db.flush()
            return self._recipe_view(db, recipe)

    def get_recipe(self, owner: str, recipe_id: str) -> dict[str, Any]:
        with self._read() as db:
            return self._recipe_view(db, self._recipe_for_actor(db, owner, recipe_id))

    def list_recipes(self, owner: str, *, include_archived: bool = False) -> list[dict[str, Any]]:
        with self._read() as db:
            owners = self._shared_owner_ids(db, owner, "recipes")
            query = db.query(InventoryRecipe).filter(InventoryRecipe.owner.in_(owners))
            if not include_archived:
                query = query.filter(InventoryRecipe.archived.is_(False))
            recipes = query.order_by(InventoryRecipe.normalized_name, InventoryRecipe.id).all()
            return [self._recipe_view(db, recipe) for recipe in recipes]

    def _stock_plan(self, db: Session, owner: str, recipe: InventoryRecipe, servings: Any) -> RecipeStockPlan:
        requested = parse_decimal(servings)
        multiplier = requested / recipe.servings
        ingredients = db.query(InventoryRecipeIngredient).filter_by(
            owner=recipe.owner, recipe_id=recipe.id
        ).order_by(InventoryRecipeIngredient.sort_order).all()
        requirements: list[RecipeRequirement] = []
        candidate_items: dict[str, tuple[InventoryItem, str]] = {}
        visible_owners = self._shared_owner_ids(db, owner, "kitchen_inventory")
        for ingredient in ingredients:
            item_query = db.query(InventoryItem).filter(
                InventoryItem.owner.in_(visible_owners), InventoryItem.archived.is_(False)
            )
            if ingredient.item_id:
                item_query = item_query.filter(InventoryItem.id == ingredient.item_id)
            else:
                item_query = item_query.filter(
                    InventoryItem.normalized_name == normalize_item_name(ingredient.ingredient_name)
                )
            items = item_query.all()
            requirements.append(RecipeRequirement(
                ingredient.ingredient_name, ingredient.quantity,
                ingredient.unit, bool(ingredient.optional),
            ))
            for item in items:
                # A repeated ingredient must share one stock balance rather
                # than duplicating the same lots in the planner input.
                candidate_items[item.id] = (item, ingredient.ingredient_name)
        lots: list[StockLot] = []
        for item, ingredient_name in candidate_items.values():
            for lot in db.query(InventoryLot).filter(
                InventoryLot.owner == item.owner, InventoryLot.item_id == item.id,
                InventoryLot.quantity > 0,
            ).with_for_update().all():
                lots.append(StockLot(
                    lot.id, item.id, ingredient_name,
                    lot.quantity, lot.unit, lot.expiry_date,
                ))
        return plan_recipe_stock(requirements, lots, servings_multiplier=multiplier)

    def can_make(self, owner: str, recipe_id: str, *, servings: Any | None = None) -> RecipeStockPlan:
        with self._read() as db:
            recipe = self._recipe_for_actor(db, owner, recipe_id)
            return self._stock_plan(db, owner, recipe, servings if servings is not None else recipe.servings)

    def missing_ingredients(self, owner: str, recipe_id: str, *, servings: Any | None = None) -> dict[str, Any]:
        """Return deterministic recipe shortages without changing stock."""
        plan = self.can_make(owner, recipe_id, servings=servings)
        return {
            "recipe_id": recipe_id,
            "can_make": plan.can_make,
            "shortages": [{
                "name": row.name, "missing": row.missing,
                "unit": row.unit, "optional": row.optional,
            } for row in plan.shortages],
        }

    def queue_missing_ingredients(
        self, owner: str, recipe_id: str, *, servings: Any | None = None,
    ) -> dict[str, Any]:
        """Queue required shortages without changing owned stock."""
        with self._transaction() as db:
            recipe = self._recipe(db, owner, recipe_id)
            plan = self._stock_plan(db, owner, recipe, servings if servings is not None else recipe.servings)
            queued: list[dict[str, Any]] = []
            for shortage in plan.shortages:
                if shortage.optional:
                    continue
                normalized = normalize_item_name(shortage.name)
                item = db.query(InventoryItem).filter(
                    InventoryItem.owner == owner,
                    InventoryItem.domain == "kitchen",
                    InventoryItem.normalized_name == normalized,
                    InventoryItem.archived.is_(False),
                ).order_by(InventoryItem.id).first()
                if item is None:
                    item = InventoryItem(
                        id=str(uuid4()), owner=owner, domain="kitchen",
                        item_kind="ingredient", name=shortage.name,
                        normalized_name=normalized, default_unit=shortage.unit,
                        shopping_list=True, metadata_json={}, image_refs_json=[],
                    )
                    db.add(item)
                    db.flush()
                    replayed = False
                else:
                    replayed = bool(item.shopping_list)
                    item.shopping_list = True
                queued.append({
                    "item": _item_view(item), "missing": shortage.missing,
                    "unit": shortage.unit, "replayed": replayed,
                })
            shortages = [{
                "name": row.name, "missing": row.missing,
                "unit": row.unit, "optional": row.optional,
            } for row in plan.shortages]
            return {"recipe_id": recipe.id, "queued": queued,
                    "count": len(queued), "stock_changed": False,
                    "shortages": shortages, "can_make": not shortages}

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

        def resolve_food_item(name_value: Any = None) -> str:
            item_id = str(args.get("item_id") or "").strip() if name_value is None else ""
            if item_id:
                return item_id
            name = _required_text(
                args.get("name") if name_value is None else name_value,
                "name", maximum=200,
            )
            normalized = normalize_item_name(name)
            with self._read() as db:
                owners = self._shared_owner_ids(db, owner)
                rows = db.query(InventoryItem).filter(
                    InventoryItem.owner.in_(owners),
                    InventoryItem.domain.in_(("kitchen", "household")),
                    InventoryItem.archived.is_(False),
                    InventoryItem.normalized_name == normalized,
                ).order_by(InventoryItem.id).all()
            if not rows:
                raise InventoryNotFound("inventory item not found")
            if len(rows) > 1:
                raise InventoryConflict("more than one matching inventory item requires clarification")
            return rows[0].id

        if action == "list":
            requested_list = str(args.get("list_name") or "").strip().casefold()
            return {"items": self.list_items(
                owner, domain=args.get("domain"),
                list_name=args.get("list_name"),
                include_archived=bool(args.get("include_archived", False)),
                include_stock=requested_list in {"pantry", "fridge", "freezer"},
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
            # Natural grocery requests often provide only the item name. The
            # inventory-specific action already establishes the bounded
            # household domain at the binding boundary, so supply the safe
            # kitchen defaults here instead of forcing the owner/model to
            # speak internal domain and item-kind vocabulary.
            domain = args.get("domain") or "kitchen"
            item_kind = args.get("item_kind") or "ingredient"
            shopping_list = args.get("shopping_list")
            if shopping_list is None:
                shopping_list = (
                    str(args.get("list_name") or "").casefold() == "grocery"
                    or not args.get("storage_area")
                )
            # Human-facing additions resolve an existing canonical item first;
            # repeated chat turns must not create duplicate grocery/pantry
            # records. A real ambiguity remains a clarification, not a guess.
            requested_items = args.get("items")
            if requested_items is not None:
                if not isinstance(requested_items, list) or not requested_items or len(requested_items) > 32:
                    raise InventoryError("items must be a non-empty list of at most 32 grocery items")
                names = [_required_text(value, "item name", maximum=200) for value in requested_items]
                if len(set(normalize_item_name(value) for value in names)) != len(names):
                    raise InventoryConflict("the grocery request contains duplicate items")
                # Models occasionally echo the owner's recipe phrase as one
                # member of an otherwise valid item array. Discard that
                # non-item member, while still failing closed when the array
                # contains no concrete grocery item. This keeps the canonical
                # write atomic without turning conversational filler into a
                # persisted item.
                if shopping_list:
                    names = [value for value in names if not _is_grocery_placeholder(value)]
                    if not names:
                        raise InventoryError(
                            "please provide the individual grocery items or a saved recipe; "
                            "no grocery change was made"
                        )
                results = []
                replayed = True
                for value in names:
                    single = dict(args)
                    single.pop("items", None)
                    single["name"] = value
                    outcome = self.manage_inventory(single, owner=owner)
                    results.append(outcome.get("item"))
                    replayed = replayed and bool(outcome.get("replayed"))
                return {"items": results, "count": len(results), "replayed": replayed}
            requested_name = _required_text(args.get("name"), "name", maximum=200)
            _validate_grocery_name(requested_name, bool(shopping_list))
            normalized = normalize_item_name(requested_name)
            with self._read() as db:
                owners = self._shared_owner_ids(db, owner)
                matches = db.query(InventoryItem).filter(
                    InventoryItem.owner.in_(owners),
                    InventoryItem.domain == str(domain).casefold(),
                    InventoryItem.normalized_name == normalized,
                    InventoryItem.archived.is_(False),
                ).order_by(InventoryItem.id).all()
            if len(matches) > 1:
                raise InventoryConflict("more than one matching inventory item requires clarification")
            if matches:
                updates: dict[str, Any] = {}
                if shopping_list:
                    updates["shopping_list"] = True
                if args.get("storage_area"):
                    updates["storage_area"] = args["storage_area"]
                item = self.update_item(owner, matches[0].id, **updates) if updates else self.get_item(owner, matches[0].id)
                return {"item": item, "replayed": True}
            item = self.create_item(
                owner, name=requested_name, domain=domain,
                item_kind=item_kind,
                default_unit=args.get("default_unit") or args.get("unit") or "each",
                category=args.get("category"), description=args.get("description"),
                brand=args.get("brand"), manufacturer=args.get("manufacturer"),
                model=args.get("model"), sku=args.get("sku"), barcode=args.get("barcode"),
                location_id=args.get("location_id"), shopping_list=bool(shopping_list), storage_area=args.get("storage_area"),
            )
            return {"item": item}
        if action == "update_item":
            item_id = _required_text(args.get("item_id"), "item_id")
            allowed = {"name", "category", "description", "default_unit", "reorder_point", "shopping_list", "storage_area"}
            return {"item": self.update_item(owner, item_id, **{key: args[key] for key in allowed if key in args})}
        if action == "archive_item":
            requested_items = args.get("items")
            if requested_items is not None:
                if not isinstance(requested_items, list) or not requested_items or len(requested_items) > 32:
                    raise InventoryError("items must be a non-empty list of at most 32 inventory items")
                names = [_required_text(value, "item name", maximum=200) for value in requested_items]
                item_ids = [resolve_food_item(name) for name in names]
                archived = [self.archive_item(owner, item_id) for item_id in item_ids]
                return {"items": archived, "count": len(archived), "replayed": all(bool(item.get("archived")) for item in archived)}
            item_id = str(args.get("item_id") or "").strip()
            if not item_id:
                item_id = resolve_food_item()
            return {"item": self.archive_item(owner, item_id)}
        if action == "remove_from_grocery":
            item_id = resolve_food_item()
            item = self.get_item(owner, item_id)
            if not item.get("shopping_list"):
                return {"item": item, "removed": False, "replayed": True}
            return {"item": self.update_item(owner, item_id, shopping_list=False), "removed": True}
        if action == "add_stock":
            item_id = resolve_food_item()
            if not args.get("item_id"):
                # A grocery item may begin with the neutral `count` unit
                # because the owner only named it on the shopping list. If
                # it has no stock yet, the first compatible purchase supplies
                # the canonical unit; never reinterpret existing stock.
                current = self.get_item(owner, item_id)
                if current.get("default_unit") == "count" and not any(
                    str(lot.get("quantity") or "0") not in {"0", "0.0", "0.000000"}
                    for lot in self.list_lots(owner, item_id)
                ):
                    try:
                        canonical_unit = normalize_amount(1, args.get("unit")).unit
                    except UnitError as exc:
                        raise InventoryError(str(exc)) from exc
                    self.update_item(owner, item_id, default_unit=canonical_unit)
            if args.get("storage_area"):
                # A purchase can move an existing grocery item into canonical
                # stock in one owner-scoped operation. The same transaction
                # service remains authoritative for both fields.
                self.update_item(owner, item_id, storage_area=args.get("storage_area"), shopping_list=False)
            kwargs: dict[str, Any] = {}
            if args.get("expiry_date"):
                try:
                    kwargs["expiry_date"] = date.fromisoformat(str(args["expiry_date"]))
                except ValueError as exc:
                    raise InventoryError("expiry_date must be an ISO date") from exc
            return self.add_stock(
                owner, item_id,
                quantity=args.get("quantity"), unit=args.get("unit"),
                idempotency_key=args.get("idempotency_key"),
                location_id=args.get("location_id"), **kwargs,
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
                owner, resolve_food_item(),
                quantity=args.get("quantity"), unit=args.get("unit"),
                idempotency_key=args.get("idempotency_key"),
            )
        if action == "adjust_stock":
            return self.adjust_lot(
                owner, _required_text(args.get("lot_id"), "lot_id"),
                quantity_delta=args.get("quantity_delta"), unit=args.get("unit"),
                idempotency_key=args.get("idempotency_key"), note=args.get("notes"),
            )
        if action in {"update_item", "move_stock", "archive_item"}:
            raise InventoryError(f"{action} is not available in this service version")
        raise InventoryError("unsupported inventory action")

    @staticmethod
    def _storage_area(value: Any) -> str | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip().casefold()
        if normalized not in {"pantry", "fridge", "freezer"}:
            raise InventoryError("storage_area must be pantry, fridge, or freezer")
        return normalized

    def manage_recipes(self, args: dict[str, Any], *, owner: str) -> dict[str, Any]:
        """Dispatch the narrow model-facing recipe action vocabulary."""
        action = str(args.get("action") or "")
        if action == "list":
            return {"recipes": self.list_recipes(
                owner, include_archived=bool(args.get("include_archived", False))
            )}
        if action == "search":
            query = normalize_item_name(args.get("query"))
            return {"recipes": [recipe for recipe in self.list_recipes(owner)
                                if query in normalize_item_name(recipe["name"])]}
        if action == "get":
            return {"recipe": self.get_recipe(
                owner, _required_text(args.get("recipe_id"), "recipe_id")
            )}
        if action == "can_make":
            plan = self.can_make(
                owner, _required_text(args.get("recipe_id"), "recipe_id"),
                servings=args.get("servings"),
            )
            return {
                "can_make": plan.can_make,
                "deductions": [{
                    "lot_id": row.lot_id, "item_id": row.item_id,
                    "quantity": row.quantity, "unit": row.unit,
                } for row in plan.deductions],
                "shortages": [{
                    "name": row.name, "missing": row.missing,
                    "unit": row.unit, "optional": row.optional,
                } for row in plan.shortages],
            }
        if action == "missing":
            return self.missing_ingredients(
                owner, _required_text(args.get("recipe_id"), "recipe_id"),
                servings=args.get("servings"),
            )
        if action == "queue_missing":
            return self.queue_missing_ingredients(
                owner, _required_text(args.get("recipe_id"), "recipe_id"),
                servings=args.get("servings"),
            )
        if action in {"missing_by_name", "queue_missing_by_name"}:
            query = normalize_item_name(_required_text(
                args.get("query") or args.get("recipe_name"), "recipe query",
            ))
            recipes = [recipe for recipe in self.list_recipes(owner)
                       if query == normalize_item_name(recipe["name"])
                       or query in normalize_item_name(recipe["name"])]
            if not recipes:
                raise InventoryNotFound(
                    "No saved recipe matched that dish. Import or paste a recipe first."
                )
            if len(recipes) > 1:
                raise InventoryError("More than one saved recipe matched that dish; choose one.")
            recipe_id = recipes[0]["id"]
            if action == "missing_by_name":
                return {
                    "recipe": recipes[0],
                    "missing": self.missing_ingredients(
                        owner, recipe_id, servings=args.get("servings"),
                    ),
                }
            queued = self.queue_missing_ingredients(owner, recipe_id, servings=args.get("servings"))
            return {
                "recipe": recipes[0],
                "missing": {
                    "recipe_id": recipe_id,
                    "can_make": bool(queued.get("can_make")),
                    "shortages": list(queued.get("shortages") or []),
                },
                "queued": queued,
            }
        if action == "add":
            return {"recipe": self.create_recipe(
                owner, name=args.get("name"), servings=args.get("servings") or "1",
                ingredients=args.get("ingredients") or [],
                instructions=args.get("instructions") or "",
                source_url=args.get("source_url"), tags=args.get("tags"),
                image_refs=args.get("image_refs"),
            )}
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
