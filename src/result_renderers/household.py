"""Grounded owner-facing Household/ kitchen Result rendering."""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def project_household_result(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Bound canonical household inventory evidence for history output."""
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return {
        "status": payload.get("status"), "item_count": payload.get("item_count", len(items)),
        "items": [{"id": row.get("id"), "name": row.get("name"), "domain": row.get("domain"),
                   "stock_quantity": row.get("stock_quantity", row.get("quantity")),
                   "default_unit": row.get("default_unit", row.get("unit"))}
                  for row in items[:100] if isinstance(row, Mapping)],
        "expiring_lots": payload.get("expiring_lots", [])[:100] if isinstance(payload.get("expiring_lots"), list) else [],
        "low_stock": payload.get("low_stock", [])[:100] if isinstance(payload.get("low_stock"), list) else [],
    }


def canonical_inventory_mutation_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render a verified inventory mutation from its structured Result."""
    event = next(iter(reversed(tuple(tool_events or ()))), None)
    if not isinstance(event, Mapping) or str(event.get("tool") or "").strip() != "manage_assets":
        return None
    try:
        request = json.loads(str(event.get("command") or "{}"))
        payload = json.loads(str(event.get("output") or ""))
    except (TypeError, ValueError):
        return None
    if not isinstance(request, Mapping) or request.get("action") not in {
        "add_item", "add_stock", "consume_stock", "adjust_stock", "move_item", "update_asset",
    } or not isinstance(payload, Mapping):
        return None
    if event.get("exit_code") not in (None, 0) or payload.get("success") is False:
        return "The inventory change was not completed; no change is confirmed."
    action = str(request.get("action"))
    verification = payload.get("verification")
    verified = isinstance(verification, Mapping) and verification.get("status") == "VERIFIED"
    item = payload.get("item") or payload.get("asset") or {}
    name = item.get("name") if isinstance(item, Mapping) else None
    label = str(name or request.get("name") or "the inventory item").strip()
    verb = {
        "add_item": "Recorded",
        "add_stock": "Added stock for",
        "consume_stock": "Consumed stock for",
        "adjust_stock": "Adjusted stock for",
        "update_asset": "Updated",
        "move_item": "Moved",
    }[action]
    if verified:
        return f"{verb} {label}; the canonical inventory readback is verified."
    return f"{verb} {label}; the write succeeded but canonical readback verification is incomplete."


def canonical_household_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render Household/ kitchen reads from the canonical inventory Result."""
    event = next(
        (
            item for item in reversed(tuple(tool_events or ()))
            if isinstance(item, Mapping)
            and str(item.get("tool") or "").strip() == "read_household"
        ),
        None,
    )
    if event is None or event.get("exit_code") not in (None, 0):
        return None
    explicit_summary = str(event.get("calendar_summary") or "").strip()
    if explicit_summary:
        return explicit_summary
    projection = event.get("result_projection")
    if isinstance(projection, Mapping):
        payload = projection
    else:
        try:
            payload = json.loads(str(event.get("output") or ""))
        except (TypeError, ValueError):
            return None
    if not isinstance(payload, Mapping):
        return None
    if str(payload.get("status") or "").strip().upper() in {"FAILED", "UNAVAILABLE", "INVALID_RESULT", "ERROR"}:
        return None

    items = payload.get("items")
    if not isinstance(items, list):
        item = payload.get("item")
        items = [item] if isinstance(item, Mapping) else None
    if items is None:
        return None
    if not items:
        return "No kitchen or household inventory is recorded for this owner."

    lines = [f"I found {len(items)} kitchen/household item{'s' if len(items) != 1 else ''}:"]
    for item in items[:100]:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or item.get("id") or "Unnamed item").strip()
        details: list[str] = []
        domain = item.get("domain")
        quantity = item.get("stock_quantity", item.get("quantity"))
        unit = item.get("default_unit", item.get("unit"))
        if domain not in (None, ""):
            details.append(f"domain={domain}")
        if quantity not in (None, ""):
            details.append(f"quantity={quantity}")
            if unit not in (None, ""):
                details[-1] += f" {unit}"
        lines.append(f"- {name}" + (f" ({', '.join(details)})" if details else ""))
    if len(items) > 100:
        lines.append(f"- …and {len(items) - 100} more")

    expiring = payload.get("expiring_lots")
    if isinstance(expiring, list) and expiring:
        lines.append("Expiring soon:")
        for row in expiring[:100]:
            if not isinstance(row, Mapping):
                continue
            item = row.get("item") if isinstance(row.get("item"), Mapping) else {}
            lot = row.get("lot") if isinstance(row.get("lot"), Mapping) else {}
            name = str(item.get("name") or item.get("id") or "Unnamed item").strip()
            expiry = str(lot.get("expiry_date") or "date unknown").strip()
            status = str(row.get("status") or "expiring").strip()
            lines.append(f"- {name} ({status}, expires {expiry})")
        if len(expiring) > 100:
            lines.append(f"- …and {len(expiring) - 100} more expiring lot{'s' if len(expiring) != 1 else ''}")

    low_stock = payload.get("low_stock")
    if isinstance(low_stock, list) and low_stock:
        lines.append("Low stock:")
        for row in low_stock[:100]:
            if not isinstance(row, Mapping):
                continue
            item = row.get("item") if isinstance(row.get("item"), Mapping) else {}
            name = str(item.get("name") or item.get("id") or "Unnamed item").strip()
            quantity = str(row.get("quantity") or "0").strip()
            unit = str(item.get("default_unit") or "").strip()
            reorder = str(row.get("reorder_point") or "unknown").strip()
            amount = f"{quantity} {unit}".strip()
            lines.append(f"- {name} ({amount}; reorder at {reorder})")
        if len(low_stock) > 100:
            lines.append(f"- …and {len(low_stock) - 100} more low-stock item{'s' if len(low_stock) != 1 else ''}")
    return "\n".join(lines)
