"""Read-only NetworkState projection over the canonical CMDB.

The CMDB remains the sole durable observation store. This module adds only a
bounded freshness-aware owner projection; it does not create a second network
database or promote observations into Asset identity.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json, os, sqlite3
from pathlib import Path
from src.constants import DATA_DIR

NETWORK_OBSERVATION_TTL_SECONDS = 900


def observation_freshness(observed_at, *, now=None, ttl_seconds=NETWORK_OBSERVATION_TTL_SECONDS):
    """Classify persisted evidence without treating stale data as current."""
    if not observed_at:
        return {"state": "UNKNOWN", "staleness_seconds": None}
    try:
        observed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        reference = now or datetime.now(timezone.utc)
        age = max(0, int((reference - observed).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return {"state": "UNKNOWN", "staleness_seconds": None}
    return {"state": "FRESH" if age <= max(0, int(ttl_seconds)) else "STALE", "staleness_seconds": age}


def _decorate_observations(observations):
    decorated = []
    for raw in observations:
        item = dict(raw)
        freshness = observation_freshness(item.get("observed_at"))
        item["freshness"] = freshness["state"]
        item["staleness_seconds"] = freshness["staleness_seconds"]
        item["provenance"] = item.get("source") or "unknown"
        decorated.append(item)
    return decorated


def map_projection(*, owner=None):
    """Project only the authenticated owner's owner-aware CMDB partition.

    Legacy asset databases are intentionally preserved but not projected in an
    authenticated request until an explicit ownership migration binds them.
    """
    owner = str(owner or "").strip()
    path=Path(os.environ.get("ODY_ASSET_DB",Path(DATA_DIR)/"assets"/"assets.db"))
    base={"nodes":[],"edges":[],"source":"canonical_cmdb","owner_scope":owner or None,
          "identity_rule":"IP addresses remain observations; no IP-only merge",
          "network_state":{"observation_ttl_seconds": NETWORK_OBSERVATION_TTL_SECONDS,
                          "derived_state":"bounded_owner_projection"}}
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
            item=dict(a)
            item["attributes"]=_json(item.pop("attributes_json","{}"))
            # Network discovery may retain a strong identifier while it is
            # still an owner-reviewable candidate.  Observed rows are not
            # canonical identity until the owner confirms/reconciles them.
            status = str(item.get("status") or "").lower()
            pending = status in {"observed", "pending", "pending_review"}
            item["canonical"] = not pending and status != "retired"
            item["resolution_state"] = (
                "retired" if status == "retired" else
                "pending_candidate" if pending else "canonical"
            )
            item["requires_confirmation"] = pending
            item["identifiers"]=[dict(x) for x in db.execute("SELECT kind,value,confidence,source,last_seen FROM identifiers WHERE asset_id=?",(item["id"],))]
            item["observations"]=_decorate_observations(db.execute("SELECT id,observed_at,source,kind,confidence,data_json FROM observations WHERE asset_id=? AND owner=? ORDER BY observed_at DESC LIMIT 20",(item["id"],owner)))
            item["last_observed_at"] = item["observations"][0].get("observed_at") if item["observations"] else None
            item["freshness"] = item["observations"][0].get("freshness") if item["observations"] else "UNKNOWN"
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
                "observations": _decorate_observations([{
                    "id": row["id"], "observed_at": row["observed_at"],
                    "source": row["source"], "kind": row["kind"],
                    "confidence": row["confidence"], "data_json": row["data_json"],
                }]),
                "last_observed_at": row["observed_at"],
                "freshness": observation_freshness(row["observed_at"])["state"],
            }
        nodes.extend(unresolved.values())
        edges=[dict(x) for x in db.execute("SELECT r.parent_asset_id,r.child_asset_id,r.relation,r.source,r.started_at,r.ended_at FROM relationships r JOIN assets p ON p.id=r.parent_asset_id JOIN assets c ON c.id=r.child_asset_id WHERE r.ended_at IS NULL AND p.owner=? AND c.owner=?",(owner,owner))]
    projected_observations = [
        observation
        for node in nodes
        for observation in (node.get("observations") or [])
    ]
    freshness_counts = {}
    for observation in projected_observations:
        state = str(observation.get("freshness") or "UNKNOWN")
        freshness_counts[state] = freshness_counts.get(state, 0) + 1
    latest = max(
        (str(item.get("observed_at") or "") for item in projected_observations),
        default=None,
    )
    network_state = dict(base["network_state"])
    network_state.update({
        "projected_observation_count": len(projected_observations),
        "fresh_observation_count": freshness_counts.get("FRESH", 0),
        "stale_observation_count": freshness_counts.get("STALE", 0),
        "unknown_observation_count": freshness_counts.get("UNKNOWN", 0),
        "latest_observed_at": latest or None,
        "current_state": "FRESH" if freshness_counts.get("FRESH") else (
            "STALE" if freshness_counts.get("STALE") else "UNKNOWN"
        ),
    })
    return {**base,"status":"SUCCESS" if nodes else "EMPTY_RESULT","nodes":nodes,"edges":edges,"network_state":network_state}
def _json(v):
    try:return json.loads(v or "{}")
    except (TypeError,ValueError):return {}
