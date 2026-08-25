"""Read-only Network workspace projection over the canonical CMDB."""
from __future__ import annotations
import json, os, sqlite3
from pathlib import Path
from src.constants import DATA_DIR
def map_projection(*, owner=None):
    """Project only the authenticated owner's owner-aware CMDB partition.

    Legacy asset databases are intentionally preserved but not projected in an
    authenticated request until an explicit ownership migration binds them.
    """
    owner = str(owner or "").strip()
    path=Path(os.environ.get("ODY_ASSET_DB",Path(DATA_DIR)/"assets"/"assets.db"))
    base={"nodes":[],"edges":[],"source":"canonical_cmdb","owner_scope":owner or None,
          "identity_rule":"IP addresses remain observations; no IP-only merge"}
    if not owner:
        return {**base,"status":"UNAVAILABLE","error_code":"OWNER_REQUIRED","warning":"authenticated owner is required"}
    if not path.is_file(): return {**base,"status":"UNAVAILABLE","error_code":"CMDB_UNAVAILABLE","warning":"CMDB unavailable"}
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row
        columns={row[1] for row in db.execute("PRAGMA table_info(assets)")}
        observation_columns={row[1] for row in db.execute("PRAGMA table_info(observations)")}
        if "owner" not in columns or "owner" not in observation_columns:
            return {**base,"status":"UNAVAILABLE","error_code":"OWNER_SCOPE_NOT_CONFIGURED","warning":"CMDB owner scope is not configured; legacy rows remain hidden"}
        nodes=[]
        for a in db.execute("SELECT * FROM assets WHERE owner=? ORDER BY id",(owner,)):
            item=dict(a);item["attributes"]=_json(item.pop("attributes_json","{}"));item["canonical"]=True;item["resolution_state"]="retired" if item.get("status")=="retired" else "canonical"
            item["identifiers"]=[dict(x) for x in db.execute("SELECT kind,value,confidence,source,last_seen FROM identifiers WHERE asset_id=?",(item["id"],))]
            item["observations"]=[dict(x) for x in db.execute("SELECT observed_at,source,kind,confidence,data_json FROM observations WHERE asset_id=? AND owner=? ORDER BY observed_at DESC LIMIT 20",(item["id"],owner))]
            nodes.append(item)
        # Discovery observations without a strong identifier are intentionally
        # projected as unidentified nodes.  They are not canonical assets and
        # are never merged by IP alone; a later MAC/serial/system-UUID
        # reconciliation may attach the observation to an existing asset.
        unresolved = {}
        for row in db.execute(
            "SELECT id,observed_at,source,kind,confidence,data_json "
            "FROM observations WHERE asset_id IS NULL AND owner=? AND kind='network_host' "
            "ORDER BY observed_at DESC", (owner,)
        ):
            data = _json(row["data_json"])
            ip = str(data.get("ip") or "").strip()
            if not ip or ip in unresolved:
                continue
            unresolved[ip] = {
                "id": "unidentified:" + ip,
                "name": "Unidentified device " + ip,
                "type": "network_device",
                "status": "observed",
                "source": row["source"],
                "confidence": row["confidence"],
                "attributes": {"ip": ip},
                "canonical": False,
                "resolution_state": "unidentified",
                "identifiers": [],
                "observations": [{
                    "id": row["id"], "observed_at": row["observed_at"],
                    "source": row["source"], "kind": row["kind"],
                    "confidence": row["confidence"], "data_json": row["data_json"],
                }],
            }
        nodes.extend(unresolved.values())
        edges=[dict(x) for x in db.execute("SELECT r.parent_asset_id,r.child_asset_id,r.relation,r.source,r.started_at,r.ended_at FROM relationships r JOIN assets p ON p.id=r.parent_asset_id JOIN assets c ON c.id=r.child_asset_id WHERE r.ended_at IS NULL AND p.owner=? AND c.owner=?",(owner,owner))]
    return {**base,"status":"SUCCESS" if nodes else "EMPTY_RESULT","nodes":nodes,"edges":edges}
def _json(v):
    try:return json.loads(v or "{}")
    except (TypeError,ValueError):return {}
