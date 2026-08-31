"""Grounded owner-facing Asset inventory Result rendering."""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def _project_asset(asset: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    attrs = asset.get("attributes") if isinstance(asset.get("attributes"), Mapping) else {}
    return {"id": asset.get("id"), "name": asset.get("name"), **{
        key: value for key in fields
        if (value := asset.get(key) if asset.get(key) not in (None, "", [], {}) else attrs.get(key))
        not in (None, "", [], {})}}


def project_asset_result(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Bound a canonical Asset Result for history and owner rendering."""
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return None
    fields = ("role", "hostname", "model", "manufacturer", "ram", "gpu", "storage", "cpu", "type")
    projected = [_project_asset(asset, fields) for asset in assets[:100] if isinstance(asset, Mapping)]
    return {"status": payload.get("status"), "assets": projected, "asset_count": len(assets),
            "query": payload.get("query"), "result_projection": payload.get("result_projection"),
            "asset_property": payload.get("asset_property")}


def _label(asset: Mapping[str, Any]) -> str:
    name = str(asset.get("name") or asset.get("id") or "Unnamed asset").strip()
    attributes = asset.get("attributes")
    attributes = attributes if isinstance(attributes, Mapping) else {}
    details: list[str] = []
    for key in ("role", "hostname", "os", "platform", "manufacturer", "model", "cpu", "ram", "gpu", "storage", "motherboard"):
        value = asset.get(key)
        if value in (None, "", [], {}):
            value = attributes.get(key)
        if value not in (None, "", [], {}):
            details.append(f"{key}={value}")
    return f"- {name}" + (f" ({', '.join(details)})" if details else "")


def canonical_asset_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render only structured successful Asset evidence; never model prose."""
    event = next((item for item in reversed(tuple(tool_events or ()))
                  if isinstance(item, Mapping) and str(item.get("tool") or "").strip() == "manage_assets"), None)
    if event is None or event.get("exit_code") not in (None, 0):
        return None
    try:
        projection_payload = event.get("result_projection")
        payload = projection_payload if isinstance(projection_payload, Mapping) else json.loads(str(event.get("output") or ""))
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping) or str(payload.get("status") or "").strip().upper() in {"FAILED", "UNAVAILABLE", "INVALID_RESULT", "ERROR"}:
        return None
    if {"assets", "active", "observed", "observations", "relationships", "by_type"} <= payload.keys():
        try:
            total, active, observed = (int(payload[key]) for key in ("assets", "active", "observed"))
            observations, relationships = (int(payload[key]) for key in ("observations", "relationships"))
            by_type = payload["by_type"]
        except (KeyError, TypeError, ValueError):
            return None
        if not isinstance(by_type, Mapping):
            return None
        if total == 0:
            return "No canonical IT assets are recorded for this owner."
        lines = [f"Canonical IT asset inventory: {total} asset{'s' if total != 1 else ''} ({active} active, {observed} observed).", f"Recorded observations: {observations}; active relationships: {relationships}."]
        try:
            type_counts = [f"{str(kind)}={int(count)}" for kind, count in sorted(by_type.items(), key=lambda item: str(item[0]))]
        except (TypeError, ValueError):
            return None
        if type_counts:
            lines.append("By type: " + ", ".join(type_counts) + ".")
        return "\n".join(lines)
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return None
    projection = str(payload.get("result_projection") or "").strip().lower()
    if projection == "property":
        prop = str(payload.get("asset_property") or "property").strip().lower()
        label = {"ram": "RAM", "gpu": "GPU", "storage": "storage", "cpu": "CPU", "processor": "processor"}.get(prop, prop)
        values = []
        for asset in assets:
            if not isinstance(asset, Mapping):
                continue
            attrs = asset.get("attributes") if isinstance(asset.get("attributes"), Mapping) else {}
            value = asset.get(prop)
            if value in (None, "", [], {}):
                value = attrs.get(prop)
            if value not in (None, "", [], {}):
                values.append(f"{asset.get('name') or asset.get('id') or 'Unnamed asset'}: {value}")
        return f"No recorded {label} values were found for this owner's assets." if not values else f"Recorded {label} by asset:\n" + "\n".join(f"- {value}" for value in values[:50])
    if projection == "filter":
        query = str(payload.get("query") or "").strip()
        if not assets:
            return f"I don't have any recorded server with {query}." if query else "No matching canonical IT assets are recorded."
        return "\n".join([f"I found {len(assets)} canonical IT asset{'s' if len(assets) != 1 else ''} matching {query!r}:", *(_label(asset) for asset in assets[:50] if isinstance(asset, Mapping))])
    if projection == "count":
        query = str(payload.get("query") or "").strip()
        return f"I found {len(assets)} canonical IT asset{'s' if len(assets) != 1 else ''}{f' matching {query!r}' if query else ''}."
    if not assets:
        return "No canonical IT assets are recorded for this owner."
    lines = [f"I found {len(assets)} canonical IT asset{'s' if len(assets) != 1 else ''}:", *(_label(asset) for asset in assets[:50] if isinstance(asset, Mapping))]
    if len(assets) > 50:
        lines.append(f"- …and {len(assets) - 50} more")
    return "\n".join(lines)
