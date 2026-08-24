"""Read-only Network workspace projection over the canonical CMDB."""
from __future__ import annotations
import json, os, sqlite3
from pathlib import Path
from src.constants import DATA_DIR
def map_projection():
    path=Path(os.environ.get("ODY_ASSET_DB",Path(DATA_DIR)/"assets"/"assets.db"))
    if not path.is_file(): return {"nodes":[],"edges":[],"source":"cmdb","warning":"CMDB unavailable"}
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row; nodes=[]
        for a in db.execute("SELECT * FROM assets ORDER BY id"):
            item=dict(a);item["attributes"]=_json(item.pop("attributes_json","{}"));item["canonical"]=True;item["resolution_state"]="retired" if item.get("status")=="retired" else "canonical"
            item["identifiers"]=[dict(x) for x in db.execute("SELECT kind,value,confidence,source,last_seen FROM identifiers WHERE asset_id=?",(item["id"],))]
            item["observations"]=[dict(x) for x in db.execute("SELECT observed_at,source,kind,confidence,data_json FROM observations WHERE asset_id=? ORDER BY observed_at DESC LIMIT 20",(item["id"],))]
            nodes.append(item)
        # Discovery observations without a strong identifier are intentionally
        # projected as unidentified nodes.  They are not canonical assets and
        # are never merged by IP alone; a later MAC/serial/system-UUID
        # reconciliation may attach the observation to an existing asset.
        unresolved = {}
        for row in db.execute(
            "SELECT id,observed_at,source,kind,confidence,data_json "
            "FROM observations WHERE asset_id IS NULL AND kind='network_host' "
            "ORDER BY observed_at DESC"
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
        edges=[dict(x) for x in db.execute("SELECT parent_asset_id,child_asset_id,relation,source,started_at,ended_at FROM relationships WHERE ended_at IS NULL")]
    return {"nodes":nodes,"edges":edges,"source":"canonical_cmdb","identity_rule":"IP addresses remain observations; no IP-only merge"}
def _json(v):
    try:return json.loads(v or "{}")
    except (TypeError,ValueError):return {}
