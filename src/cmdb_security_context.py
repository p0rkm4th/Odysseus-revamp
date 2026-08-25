"""Read-only CMDB projection used by Security Assessment targets."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from src.constants import DATA_DIR


def _path() -> Path:
    return Path(os.environ.get("ODY_ASSET_DB", Path(DATA_DIR) / "assets" / "assets.db"))


class CmdbSecurityContext:
    """Resolve canonical assets without creating or mutating CMDB identity."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else _path()

    def resolve(self, asset_id: str, *, owner: str | None = None) -> dict[str, Any]:
        asset_id = str(asset_id or "").strip()
        owner = str(owner or "").strip()
        if not asset_id or not owner or not self.path.is_file():
            return {"resolution_state": "unresolved", "canonical_asset_id": asset_id or None}
        try:
            with sqlite3.connect(self.path) as db:
                db.row_factory = sqlite3.Row
                columns = {row[1] for row in db.execute("PRAGMA table_info(assets)")}
                if "owner" not in columns:
                    return {"resolution_state": "unresolved", "canonical_asset_id": asset_id, "error_code": "OWNER_SCOPE_NOT_CONFIGURED"}
                asset = db.execute("SELECT * FROM assets WHERE id = ? AND owner = ?", (asset_id, owner)).fetchone()
                if asset is None:
                    return {"resolution_state": "unresolved", "canonical_asset_id": asset_id}
                result = dict(asset)
                result["attributes"] = _json(result.pop("attributes_json", "{}"))
                result["identifiers"] = [dict(row) for row in db.execute(
                    "SELECT kind, value, confidence, source, first_seen, last_seen FROM identifiers WHERE asset_id = ? ORDER BY kind, value",
                    (asset_id,),
                )]
                result["observations"] = []
                for row in db.execute(
                    "SELECT id, observed_at, source, kind, confidence, data_json FROM observations WHERE asset_id = ? AND owner = ? ORDER BY observed_at DESC LIMIT 50",
                    (asset_id, owner),
                ):
                    item = dict(row); item["data"] = _json(item.pop("data_json", "{}")); result["observations"].append(item)
                result["relationships"] = [dict(row) for row in db.execute(
                    "SELECT r.parent_asset_id, r.child_asset_id, r.relation, r.started_at, r.ended_at, r.source, r.notes FROM relationships r JOIN assets p ON p.id=r.parent_asset_id JOIN assets c ON c.id=r.child_asset_id WHERE (r.parent_asset_id = ? OR r.child_asset_id = ?) AND r.ended_at IS NULL AND p.owner = ? AND c.owner = ?",
                    (asset_id, asset_id, owner, owner),
                )]
                retired = str(result.get("status") or "").casefold() == "retired" or bool(result.get("retired_at"))
                result["resolution_state"] = "retired" if retired else "canonical"
                result["owner_visible"] = True
                result["owner_context"] = owner
                result["canonical_asset_id"] = asset_id
                result["last_validated_at"] = result.get("updated_at")
                return result
        except (OSError, sqlite3.Error):
            return {"resolution_state": "unresolved", "canonical_asset_id": asset_id}


def _json(value: Any) -> Any:
    try:
        return json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
