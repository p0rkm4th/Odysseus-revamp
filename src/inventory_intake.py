"""Pure validation boundary for reviewable inventory-intake drafts.

This module deliberately does not call a model, execute a tool, or write to a
database.  Vision descriptions, transcripts, and model-produced candidates are
untrusted input.  Callers may show the returned draft to a user, but must not
commit it without a separate explicit confirmation step.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
import uuid
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = 1
ALLOWED_DOMAINS = frozenset({"it", "kitchen", "household"})
ALLOWED_ACTIONS = frozenset({"add", "remove"})

_UPLOAD_ID_RE = re.compile(r"^[0-9a-fA-F]{32}(?:\.[A-Za-z0-9]+)?$")
_AMBIGUOUS_QUANTITY_RE = re.compile(
    r"(?:^|\s)(?:about|approx(?:imately)?|around|few|several|some|unknown|maybe)(?:\s|$)|"
    r"[~?]|\d\s*(?:-|–|—|to)\s*\d",
    re.IGNORECASE,
)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_UNIT_ALIASES = {
    "ea": "each", "each": "each", "item": "each", "items": "each",
    "pc": "each", "pcs": "each", "piece": "each", "pieces": "each",
    "g": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml",
    "millilitre": "ml", "millilitres": "ml",
    "l": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "package": "package", "packages": "package", "pack": "package", "packs": "package",
    "can": "can", "cans": "can",
    "roll": "roll", "rolls": "roll", "bottle": "bottle", "bottles": "bottle",
}
_AMBIGUOUS_PACKAGE_UNITS = frozenset({
    "package", "pack", "can", "roll", "bottle",
})

_COMMON_FIELDS = frozenset({"name", "category", "location", "notes"})
_DOMAIN_FIELDS = {
    "it": frozenset({
        "manufacturer", "model", "serial_number", "part_number", "condition",
        "hostname", "mac_addresses", "ip_addresses",
    }),
    "kitchen": frozenset({"brand", "expiration_date", "lot_code"}),
    "household": frozenset({"brand"}),
}
_MAX_FIELD_LENGTHS = {
    "name": 160,
    "category": 80,
    "location": 120,
    "notes": 1000,
    "manufacturer": 120,
    "model": 160,
    "serial_number": 160,
    "part_number": 160,
    "condition": 80,
    "hostname": 253,
    "brand": 120,
    "expiration_date": 40,
    "lot_code": 120,
}
_IT_LIST_FIELDS = frozenset({"mac_addresses", "ip_addresses"})


def _clean_text(value: Any, *, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = _CONTROL_RE.sub("", value).strip()
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    if not value:
        return None
    return value[:limit]


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _normalize_quantity(value: Any) -> tuple[str | None, str | None]:
    if value is None or isinstance(value, bool):
        return None, "quantity is required and must be explicitly reviewed"
    if isinstance(value, str):
        raw = value.strip()
        if not raw or _AMBIGUOUS_QUANTITY_RE.search(raw):
            return None, "quantity is unknown or ambiguous; enter an exact amount"
    else:
        raw = str(value)
    try:
        quantity = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None, "quantity is unknown or ambiguous; enter an exact amount"
    if not quantity.is_finite() or quantity <= 0:
        return None, "quantity must be a finite number greater than zero"
    if quantity > Decimal("1000000000"):
        return None, "quantity exceeds the supported maximum"
    if quantity.as_tuple().exponent < -6:
        return None, "quantity has more than six decimal places"
    return _decimal_text(quantity), None


def _normalize_unit(value: Any) -> tuple[str | None, str | None]:
    unit = _clean_text(value, limit=40)
    if not unit:
        return None, "unit is required and must be explicitly reviewed"
    normalized = _UNIT_ALIASES.get(unit.casefold().rstrip("."))
    if not normalized:
        return None, f"unit {unit!r} is not recognized; choose a supported unit"
    if normalized in _AMBIGUOUS_PACKAGE_UNITS:
        return None, (
            f"unit {unit!r} needs an explicit package size or count before confirmation"
        )
    return normalized, None


def owner_checked_attachment_ids(
    owner: str,
    resolved_attachments: Iterable[Mapping[str, Any]] | None,
) -> list[str]:
    """Extract provenance IDs only from resolver results owned by ``owner``.

    The public API intentionally accepts resolved metadata rather than raw IDs.
    A route should first call ``UploadHandler.resolve_upload(id, owner=owner)``;
    passing a mismatched, malformed, or incomplete result fails closed here.
    """
    normalized_owner = _clean_text(owner, limit=200)
    if not normalized_owner:
        raise ValueError("an inventory draft requires an explicit owner")

    attachment_ids: list[str] = []
    seen: set[str] = set()
    for attachment in resolved_attachments or ():
        if not isinstance(attachment, Mapping):
            raise ValueError("owner-checked attachment metadata must be an object")
        attachment_id = str(attachment.get("id") or "").strip()
        if not _UPLOAD_ID_RE.fullmatch(attachment_id):
            raise ValueError("owner-checked attachment metadata has an invalid upload id")
        if attachment.get("owner") != normalized_owner:
            raise ValueError("attachment owner does not match inventory draft owner")
        if attachment_id not in seen:
            seen.add(attachment_id)
            attachment_ids.append(attachment_id)
    return attachment_ids


def _normalize_candidate(candidate: Any, index: int) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(candidate, Mapping):
        return {
            "candidate_index": index,
            "status": "invalid",
            "action": None,
            "domain": None,
            "item": {},
            "quantity": None,
            "unit": None,
            "warnings": [],
            "errors": ["candidate must be an object"],
        }

    domain_raw = _clean_text(candidate.get("domain"), limit=40)
    domain = domain_raw.casefold() if domain_raw else None
    if domain not in ALLOWED_DOMAINS:
        errors.append("domain must be one of: household, it, kitchen")

    action_raw = _clean_text(candidate.get("action"), limit=40)
    action = action_raw.casefold() if action_raw else None
    if action not in ALLOWED_ACTIONS:
        errors.append("action must be one of: add, remove")

    allowed_fields = _COMMON_FIELDS | _DOMAIN_FIELDS.get(domain or "", frozenset())
    item: dict[str, Any] = {}
    for field in sorted(allowed_fields - _IT_LIST_FIELDS):
        cleaned = _clean_text(candidate.get(field), limit=_MAX_FIELD_LENGTHS[field])
        if cleaned is not None:
            item[field] = cleaned
    for field in sorted(_IT_LIST_FIELDS & allowed_fields):
        values = candidate.get(field)
        if values is None:
            continue
        if not isinstance(values, list) or len(values) > 32:
            warnings.append(f"{field} must be a reviewed list of at most 32 values")
            continue
        cleaned_values = []
        for value in values:
            cleaned = _clean_text(value, limit=80)
            if cleaned and cleaned not in cleaned_values:
                cleaned_values.append(cleaned)
        if cleaned_values:
            item[field] = cleaned_values
    if "name" not in item:
        errors.append("item name is required")

    quantity, quantity_warning = _normalize_quantity(candidate.get("quantity"))
    unit, unit_warning = _normalize_unit(candidate.get("unit"))
    if quantity_warning:
        warnings.append(quantity_warning)
    if unit_warning:
        warnings.append(unit_warning)

    ignored = sorted(
        str(key) for key in candidate.keys()
        if key not in allowed_fields and key not in {"domain", "action", "quantity", "unit"}
    )
    if ignored:
        warnings.append("ignored unrecognized fields: " + ", ".join(ignored))

    status = "invalid" if errors else ("review_required" if warnings else "ready")
    return {
        "candidate_index": index,
        "status": status,
        "action": action if action in ALLOWED_ACTIONS else None,
        "domain": domain if domain in ALLOWED_DOMAINS else None,
        "item": item,
        "quantity": quantity,
        "unit": unit,
        "warnings": warnings,
        "errors": errors,
    }


def build_inventory_intake_draft(
    *,
    owner: str,
    candidates: Iterable[Any],
    resolved_attachments: Iterable[Mapping[str, Any]] | None = None,
    source_text: str | None = None,
    draft_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a non-executable, reviewable inventory draft payload."""
    normalized_owner = _clean_text(owner, limit=200)
    if not normalized_owner:
        raise ValueError("an inventory draft requires an explicit owner")
    if isinstance(candidates, (str, bytes, Mapping)):
        raise ValueError("candidates must be a list or iterable of candidate objects")

    attachment_ids = owner_checked_attachment_ids(normalized_owner, resolved_attachments)
    operations = [_normalize_candidate(candidate, index) for index, candidate in enumerate(candidates)]
    if not operations:
        raise ValueError("at least one inventory candidate is required")

    statuses = {operation["status"] for operation in operations}
    status = "invalid" if "invalid" in statuses else (
        "review_required" if "review_required" in statuses else "ready_for_confirmation"
    )
    created_at = now or datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    safe_source_text = _clean_text(source_text, limit=4000) if source_text is not None else None
    return {
        "schema_version": SCHEMA_VERSION,
        "draft_id": str(draft_id or uuid.uuid4()),
        "owner": normalized_owner,
        "status": status,
        "requires_explicit_confirmation": True,
        "executable": False,
        "created_at": created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "trust": "untrusted_input",
            "text": safe_source_text,
            "attachment_ids": attachment_ids,
        },
        "operations": operations,
    }
