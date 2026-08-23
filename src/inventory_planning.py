"""Pure deterministic planning for recipe stock checks and FEFO deductions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from src.inventory_units import UnitError, parse_decimal


def normalize_item_name(value: Any) -> str:
    name = " ".join(str(value or "").strip().casefold().split())
    if not name or len(name) > 200:
        raise ValueError("item name must contain 1 to 200 characters")
    return name


@dataclass(frozen=True)
class StockLot:
    lot_id: str
    item_id: str
    item_name: str
    quantity: Decimal
    unit: str
    expires_on: date | None = None


@dataclass(frozen=True)
class RecipeRequirement:
    name: str
    quantity: Decimal
    unit: str
    optional: bool = False


@dataclass(frozen=True)
class PlannedDeduction:
    lot_id: str
    item_id: str
    quantity: Decimal
    unit: str


@dataclass(frozen=True)
class StockShortage:
    name: str
    missing: Decimal
    unit: str
    optional: bool


@dataclass(frozen=True)
class RecipeStockPlan:
    deductions: tuple[PlannedDeduction, ...]
    shortages: tuple[StockShortage, ...]

    @property
    def can_make(self) -> bool:
        return not any(not shortage.optional for shortage in self.shortages)


def _decimal_quantity(value: Any) -> Decimal:
    try:
        return parse_decimal(value)
    except UnitError as exc:
        raise ValueError(str(exc)) from exc


def plan_recipe_stock(
    requirements: Iterable[RecipeRequirement],
    lots: Iterable[StockLot],
    *,
    servings_multiplier: Any = Decimal("1"),
) -> RecipeStockPlan:
    """Allocate matching canonical-unit lots in first-expiry-first-out order."""
    multiplier = _decimal_quantity(servings_multiplier)
    available: dict[str, list[list[Any]]] = {}
    for lot in lots:
        quantity = _decimal_quantity(lot.quantity)
        key = normalize_item_name(lot.item_name)
        available.setdefault(key, []).append([lot, quantity])
    max_date = date.max
    for entries in available.values():
        entries.sort(key=lambda pair: (
            pair[0].expires_on or max_date,
            pair[0].lot_id,
        ))

    deductions: list[PlannedDeduction] = []
    shortages: list[StockShortage] = []
    for requirement in requirements:
        key = normalize_item_name(requirement.name)
        remaining = (_decimal_quantity(requirement.quantity) * multiplier)
        for lot, quantity_left in available.get(key, []):
            if lot.unit != requirement.unit:
                continue
            take = min(quantity_left, remaining)
            if take <= 0:
                continue
            deductions.append(PlannedDeduction(
                lot_id=lot.lot_id,
                item_id=lot.item_id,
                quantity=take,
                unit=lot.unit,
            ))
            quantity_left -= take
            remaining -= take
            # Lists intentionally hold the mutable planning balance; inputs
            # and returned records stay immutable.
            for pair in available[key]:
                if pair[0].lot_id == lot.lot_id:
                    pair[1] = quantity_left
                    break
            if remaining == 0:
                break
        if remaining > 0:
            shortages.append(StockShortage(
                name=key,
                missing=remaining,
                unit=requirement.unit,
                optional=bool(requirement.optional),
            ))
    return RecipeStockPlan(tuple(deductions), tuple(shortages))
