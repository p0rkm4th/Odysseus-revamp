"""Deterministic inventory quantity parsing and compatible unit conversion."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


class UnitError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedAmount:
    quantity: Decimal
    unit: str
    dimension: str


_SIX_PLACES = Decimal("0.000001")
_DEFINITIONS = {
    # alias: (dimension, canonical unit, multiplier)
    "g": ("mass", "g", Decimal("1")),
    "gram": ("mass", "g", Decimal("1")),
    "grams": ("mass", "g", Decimal("1")),
    "kg": ("mass", "g", Decimal("1000")),
    "kilogram": ("mass", "g", Decimal("1000")),
    "kilograms": ("mass", "g", Decimal("1000")),
    "oz": ("mass", "g", Decimal("28.349523125")),
    "ounce": ("mass", "g", Decimal("28.349523125")),
    "ounces": ("mass", "g", Decimal("28.349523125")),
    "lb": ("mass", "g", Decimal("453.59237")),
    "lbs": ("mass", "g", Decimal("453.59237")),
    "pound": ("mass", "g", Decimal("453.59237")),
    "pounds": ("mass", "g", Decimal("453.59237")),
    "ml": ("volume", "ml", Decimal("1")),
    "milliliter": ("volume", "ml", Decimal("1")),
    "milliliters": ("volume", "ml", Decimal("1")),
    "l": ("volume", "ml", Decimal("1000")),
    "liter": ("volume", "ml", Decimal("1000")),
    "liters": ("volume", "ml", Decimal("1000")),
    "tsp": ("volume", "ml", Decimal("4.92892159375")),
    "teaspoon": ("volume", "ml", Decimal("4.92892159375")),
    "teaspoons": ("volume", "ml", Decimal("4.92892159375")),
    "tbsp": ("volume", "ml", Decimal("14.78676478125")),
    "tablespoon": ("volume", "ml", Decimal("14.78676478125")),
    "tablespoons": ("volume", "ml", Decimal("14.78676478125")),
    "cup": ("volume", "ml", Decimal("236.5882365")),
    "cups": ("volume", "ml", Decimal("236.5882365")),
    "count": ("count", "count", Decimal("1")),
    "each": ("count", "count", Decimal("1")),
    "item": ("count", "count", Decimal("1")),
    "items": ("count", "count", Decimal("1")),
    "pc": ("count", "count", Decimal("1")),
    "pcs": ("count", "count", Decimal("1")),
    "piece": ("count", "count", Decimal("1")),
    "pieces": ("count", "count", Decimal("1")),
}

AMBIGUOUS_UNITS = frozenset({
    "bag", "bags", "bottle", "bottles", "box", "boxes", "can", "cans",
    "container", "containers", "pack", "packs", "package", "packages",
    "roll", "rolls",
})


def parse_decimal(value: Any, *, positive: bool = True) -> Decimal:
    if isinstance(value, bool):
        raise UnitError("quantity must be a number, not a boolean")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, ValueError) as exc:
        raise UnitError("quantity must be a finite decimal number") from exc
    if not parsed.is_finite():
        raise UnitError("quantity must be finite")
    if positive and parsed <= 0:
        raise UnitError("quantity must be greater than zero")
    return parsed


def normalize_amount(value: Any, unit: Any, *, positive: bool = True) -> NormalizedAmount:
    quantity = parse_decimal(value, positive=positive)
    normalized_unit = str(unit or "").strip().casefold().rstrip(".")
    if normalized_unit in AMBIGUOUS_UNITS:
        raise UnitError(
            f"unit '{normalized_unit}' needs a package size or an explicit mass, volume, or count"
        )
    definition = _DEFINITIONS.get(normalized_unit)
    if definition is None:
        raise UnitError(f"unsupported unit: {normalized_unit or '<missing>'}")
    dimension, canonical, multiplier = definition
    canonical_quantity = (quantity * multiplier).quantize(_SIX_PLACES)
    return NormalizedAmount(canonical_quantity, canonical, dimension)


def convert_amount(value: Any, from_unit: Any, to_unit: Any) -> Decimal:
    source = normalize_amount(value, from_unit, positive=False)
    target_key = str(to_unit or "").strip().casefold().rstrip(".")
    target = _DEFINITIONS.get(target_key)
    if target is None:
        raise UnitError(f"unsupported unit: {target_key or '<missing>'}")
    dimension, _canonical, multiplier = target
    if source.dimension != dimension:
        raise UnitError(f"incompatible units: {from_unit} and {to_unit}")
    return (source.quantity / multiplier).quantize(_SIX_PLACES)
