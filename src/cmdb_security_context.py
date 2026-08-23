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
        if not asset_id or not self.path.is_file():
            return {"resolution_state": "unresolved", "canonical_asset_id": asset_id or None}
        try:
            with sqlite3.connect(self.path) as db:
                db.row_factory = sqlite3.Row
                asset = db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
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
                    "SELECT id, observed_at, source, kind, confidence, data_json FROM observations WHERE asset_id = ? ORDER BY observed_at DESC LIMIT 50",
                    (asset_id,),
                ):
                    item = dict(row); item["data"] = _json(item.pop("data_json", "{}")); result["observations"].append(item)
                result["relationships"] = [dict(row) for row in db.execute(
                    "SELECT parent_asset_id, child_asset_id, relation, started_at, ended_at, source, notes FROM relationships WHERE (parent_asset_id = ? OR child_asset_id = ?) AND ended_at IS NULL",
                    (asset_id, asset_id),
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
