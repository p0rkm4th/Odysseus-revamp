"""Explicit boundary between technical CMDB observations and user inventory.

The CMDB is the system of record for discovered identity and observations.
Inventory is the system of record for owner-approved items, stock, and drafts.
This adapter only creates reviewable proposals; it never mutates inventory.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping


STRONG_IDENTIFIERS = ("system_uuid", "serial", "mac")


def strong_identity(observation: Mapping[str, Any]) -> dict[str, str]:
    """Return normalized strong identifiers; IP/hostname are deliberately excluded."""
    identifiers = observation.get("identifiers")
    if not isinstance(identifiers, Mapping):
        identifiers = observation
    result: dict[str, str] = {}
    for kind in STRONG_IDENTIFIERS:
        value = identifiers.get(kind)
        if value is None or isinstance(value, (list, dict)):
            continue
        value = str(value).strip()
        if value:
            result[kind] = value.casefold() if kind == "mac" else value
    return result


def identity_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Match only on a shared strong identifier, never on IP alone."""
    a, b = strong_identity(left), strong_identity(right)
    return bool(a and b and any(a[k] == b[k] for k in a.keys() & b.keys()))


def inventory_proposal(*, owner: str, cmdb_asset_id: str, observation: Mapping[str, Any]) -> dict[str, Any]:
    """Translate one CMDB observation into an explicit pending inventory draft."""
    owner = str(owner or "").strip()
    asset_id = str(cmdb_asset_id or "").strip()
    if not owner or not asset_id:
        raise ValueError("owner and cmdb_asset_id are required")
    identity = strong_identity(observation)
    payload = {
        "domain": "it",
        "action": "add",
        "item": {
            "name": str(observation.get("name") or observation.get("hostname") or "Discovered asset").strip(),
            "hostname": observation.get("hostname"),
            "model": observation.get("model"),
            "manufacturer": observation.get("manufacturer"),
            "serial_number": identity.get("serial"),
            "mac_addresses": [identity["mac"]] if identity.get("mac") else [],
            "ip_addresses": [str(observation["ip"]).strip()] if observation.get("ip") else [],
            "cmdb_asset_id": asset_id,
        },
        "source": {"type": "cmdb_observation", "asset_id": asset_id},
    }
    digest = sha256(json.dumps({"owner": owner, "asset": asset_id, "observation": observation}, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "owner": owner,
        "source_type": "network_discovery",
        "source_ref": asset_id,
        "idempotency_key": f"cmdb:{asset_id}:{digest[:32]}",
        "status": "pending",
        "requires_confirmation": True,
        "identity": identity,
        "payload": payload,
    }
