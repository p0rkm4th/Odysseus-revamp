"""Evidence-backed relationship projection over existing CMDB references."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from core.work_models import WorldRelationship, WorkEvent
from src.work_engine import WorkError, ident, now, parse_dt, serialize

RELATIONSHIPS = {"RUNS_ON", "DEPENDS_ON", "USES", "POINTS_TO", "CONNECTED_TO", "BACKED_UP_BY", "OWNS", "CONTAINS"}
RELATIONSHIP_STATUSES = {"proposed", "observed", "user_confirmed", "contradicted", "stale", "superseded"}
INACTIVE_RELATIONSHIP_STATUSES = {"contradicted", "stale", "superseded"}


def _current_relationship(row, at=None):
    """Whether an edge is usable for present-state traversal."""
    return relationship_activity(row, at=at)["activity_state"] == "active"


def relationship_activity(row, *, at=None):
    """Project relationship lifecycle into a safe present/history distinction.

    ``status`` retains the evidence/reconciliation vocabulary used by the
    canonical relationship store.  Consumers that estimate current impact
    must use this derived state: inactive statuses and out-of-valid-time edges
    remain visible as history, but cannot silently become dependencies.
    """
    if row.get("status") in INACTIVE_RELATIONSHIP_STATUSES:
        return {"activity_state": "historical", "reason": f"status:{row.get('status')}"}
    at = at or now()
    valid_from = parse_dt(row.get("valid_from"))
    valid_until = parse_dt(row.get("valid_until"))
    if valid_from and valid_from > at:
        return {"activity_state": "historical", "reason": "not_yet_valid"}
    if valid_until and valid_until <= at:
        return {"activity_state": "historical", "reason": "validity_ended"}
    return {"activity_state": "active", "reason": "currently_valid"}


class WorldModelService:
    def __init__(self, db): self.db = db

    def sync_cmdb_edges(self, owner, edges, *, limit=500):
        """Project canonical CMDB edges into the existing World Model store."""
        allowed = {"RUNS_ON", "DEPENDS_ON", "USES", "POINTS_TO", "CONNECTED_TO", "BACKED_UP_BY", "OWNS", "CONTAINS"}
        rows, skipped = [], []
        for edge in list(edges or [])[:max(1, min(int(limit), 500))]:
            if not isinstance(edge, dict):
                continue
            relation = str(edge.get("relation") or "").strip().upper()
            if relation not in allowed:
                skipped.append({"relation": relation, "reason": "unsupported_cmdb_relation"})
                continue
            parent = str(edge.get("parent_asset_id") or "").strip()
            child = str(edge.get("child_asset_id") or "").strip()
            if not parent or not child:
                skipped.append({"relation": relation, "reason": "missing_asset_identity"})
                continue
            source_ref, target_ref = f"asset:{parent}", f"asset:{child}"
            evidence = {"parent": parent, "child": child, "relation": relation, "started_at": edge.get("started_at"), "ended_at": edge.get("ended_at")}
            evidence_ref = "cmdb://relationship/" + hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            status = "stale" if edge.get("ended_at") else "observed"
            existing = self.db.query(WorldRelationship).filter_by(owner=owner, source_ref=source_ref, relation=relation, target_ref=target_ref, status=status).all()
            if any(evidence_ref in (item.evidence_references or []) for item in existing):
                rows.append(serialize(existing[0]))
                continue
            row = WorldRelationship(
                id=ident("rel"), owner=owner, source_ref=source_ref, relation=relation,
                target_ref=target_ref, status=status, evidence_references=[evidence_ref],
                source="cmdb", confidence_class="high" if status == "observed" else "unknown",
                observation_kind="observed", valid_from=parse_dt(edge.get("started_at")),
                valid_until=parse_dt(edge.get("ended_at")), recorded_at=now(),
            )
            self.db.add(row)
            rows.append(serialize(row))
        if rows:
            self.db.flush()
            self.db.add(WorkEvent(id=ident("event"), owner=owner, event_type="world.cmdb_synced", payload={"relationship_count": len(rows), "skipped_count": len(skipped)}))
        self.db.commit()
        return {"relationships": rows, "relationship_count": len(rows), "skipped": skipped, "authority": "canonical_cmdb"}

    def create_relationship(self, owner, data):
        relation = str(data.get("relation") or "").strip().upper()
        source = str(data.get("source_ref") or "").strip()
        target = str(data.get("target_ref") or "").strip()
        status = str(data.get("status") or "proposed").strip().lower()
        if relation not in RELATIONSHIPS: raise WorkError("unsupported world relationship")
        if not source or not target: raise WorkError("relationship source and target are required")
        if status not in RELATIONSHIP_STATUSES: raise WorkError("invalid relationship status")
        if status == "user_confirmed" and str(data.get("source") or "").strip() == "":
            raise WorkError("confirmed relationships require provenance")
        row = WorldRelationship(id=ident("rel"), owner=owner, source_ref=source[:500], relation=relation, target_ref=target[:500], status=status, evidence_references=data.get("evidence_references") or [], source=str(data.get("source") or "operator")[:500], confidence_class=str(data.get("confidence_class") or "unknown")[:32], observation_kind=str(data.get("observation_kind") or "inferred")[:32], valid_from=parse_dt(data.get("valid_from")), valid_until=parse_dt(data.get("valid_until")), recorded_at=now())
        self.db.add(row); self.db.commit(); self.db.refresh(row); return serialize(row)

    def list_relationships(self, owner, *, entity_ref=None, relation=None, status=None, limit=200):
        query = self.db.query(WorldRelationship).filter_by(owner=owner)
        if entity_ref: query = query.filter((WorldRelationship.source_ref == entity_ref) | (WorldRelationship.target_ref == entity_ref))
        if relation: query = query.filter_by(relation=str(relation).upper())
        if status: query = query.filter_by(status=status)
        result = []
        for row in query.order_by(WorldRelationship.updated_at.desc()).limit(max(1, min(int(limit), 500))).all():
            item = serialize(row)
            item.update(relationship_activity(item))
            result.append(item)
        return result

    def update_relationship(self, owner, relationship_id, data):
        row = self.db.query(WorldRelationship).filter_by(owner=owner, id=relationship_id).one_or_none()
        if row is None: raise WorkError("relationship not found")
        if "status" in data:
            status = str(data.get("status") or "").strip().lower()
            if status not in RELATIONSHIP_STATUSES: raise WorkError("invalid relationship status")
            if status == "user_confirmed" and not str(data.get("source") or row.source).strip():
                raise WorkError("confirmed relationships require provenance")
            row.status = status
        for field in ("source", "confidence_class", "observation_kind"):
            if field in data: setattr(row, field, str(data.get(field) or "")[:500 if field == "source" else 32])
        if "evidence_references" in data: row.evidence_references = list(data.get("evidence_references") or [])
        if "valid_from" in data: row.valid_from = parse_dt(data.get("valid_from"))
        if "valid_until" in data: row.valid_until = parse_dt(data.get("valid_until"))
        self.db.add(WorkEvent(id=ident("event"), owner=owner, event_type="world.relationship.updated", payload={"relationship_id": row.id, "status": row.status, "source_ref": row.source_ref, "target_ref": row.target_ref}))
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def neighbors(self, owner, entity_ref, *, depth=1, limit=100):
        depth = max(1, min(int(depth), 3)); seen = {entity_ref}; frontier = {entity_ref}; edges = []
        for _ in range(depth):
            rows = self.list_relationships(owner, limit=limit)
            next_frontier = set()
            for row in rows:
                if not _current_relationship(row): continue
                if row["source_ref"] in frontier or row["target_ref"] in frontier:
                    if row not in edges: edges.append(row)
                    other = row["target_ref"] if row["source_ref"] in frontier else row["source_ref"]
                    if other not in seen: seen.add(other); next_frontier.add(other)
            frontier = next_frontier
            if not frontier: break
        return {"focus": entity_ref, "depth": depth, "entities": sorted(seen), "relationships": edges[:limit]}

    def blast_radius(self, owner, entity_ref, *, limit=100):
        # Traverse from the focus while retaining the frontier endpoint.  A
        # flat edge list is insufficient for multi-hop impact: for
        # host -> service -> dependency, the affected entity at hop two must
        # be the dependency, not the already-visited service.
        focus = str(entity_ref); seen = {focus}; frontier = {focus}; traversed = []; impact = []
        inactive_edges = []
        for _ in range(3):
            rows = self.list_relationships(owner, limit=limit)
            next_frontier = set()
            for row in rows:
                if row["source_ref"] not in frontier and row["target_ref"] not in frontier: continue
                if not _current_relationship(row):
                    inactive_edges.append(row)
                    continue
                other = row["target_ref"] if row["source_ref"] in frontier else row["source_ref"]
                # A relationship can be encountered again when the graph has
                # a cycle or when traversal crosses an already visited node.
                # It remains useful evidence in the World Model, but it must
                # not inflate present blast-radius impact or re-add the focus.
                if other in seen:
                    continue
                if row not in traversed: traversed.append(row)
                impact.append((row, other))
                seen.add(other); next_frontier.add(other)
            frontier = next_frontier
            if not frontier: break
        confirmed, likely, unknown = [], [], []
        for row, other in impact:
            activity = relationship_activity(row)
            item = {"entity": other, "relation": row["relation"], "confidence": row["confidence_class"], "source": row["source"], "activity_state": activity["activity_state"], "observation_kind": row.get("observation_kind", "unknown"), "evidence_references": list(row.get("evidence_references") or [])}
            if row["status"] in {"observed", "user_confirmed"} and row["confidence_class"] in {"high", "confirmed"}: confirmed.append(item)
            elif row["status"] == "proposed" or row["observation_kind"] == "inferred": likely.append(item)
        for row in inactive_edges[:limit]:
            other = row["target_ref"] if row["source_ref"] == focus else row["source_ref"]
            activity = relationship_activity(row)
            unknown.append({"entity": other, "relation": row["relation"], "reason": activity["reason"], "source": row["source"], "status": row["status"], "activity_state": activity["activity_state"], "confidence": row.get("confidence_class", "unknown"), "observation_kind": row.get("observation_kind", "unknown"), "evidence_references": list(row.get("evidence_references") or [])})
        if not traversed and not unknown: unknown.append({"reason": "no evidence-backed dependency edges", "entity": entity_ref})
        return {"focus": entity_ref, "confirmed": confirmed, "likely": likely, "unknown": unknown}
