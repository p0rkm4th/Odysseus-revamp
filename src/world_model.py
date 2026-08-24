"""Evidence-backed relationship projection over existing CMDB references."""
from __future__ import annotations
from datetime import datetime, timezone
from core.work_models import WorldRelationship
from src.work_engine import WorkError, ident, now, parse_dt, serialize

RELATIONSHIPS = {"RUNS_ON", "DEPENDS_ON", "USES", "POINTS_TO", "CONNECTED_TO", "BACKED_UP_BY", "OWNS"}
RELATIONSHIP_STATUSES = {"proposed", "observed", "user_confirmed", "contradicted", "stale", "superseded"}


class WorldModelService:
    def __init__(self, db): self.db = db

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
        return [serialize(row) for row in query.order_by(WorldRelationship.updated_at.desc()).limit(max(1, min(int(limit), 500))).all()]

    def neighbors(self, owner, entity_ref, *, depth=1, limit=100):
        depth = max(1, min(int(depth), 3)); seen = {entity_ref}; frontier = {entity_ref}; edges = []
        for _ in range(depth):
            rows = self.list_relationships(owner, limit=limit)
            next_frontier = set()
            for row in rows:
                if row["status"] in {"contradicted", "stale", "superseded"}: continue
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
        for _ in range(3):
            rows = self.list_relationships(owner, limit=limit)
            next_frontier = set()
            for row in rows:
                if row["source_ref"] not in frontier and row["target_ref"] not in frontier: continue
                other = row["target_ref"] if row["source_ref"] in frontier else row["source_ref"]
                if row not in traversed: traversed.append(row)
                impact.append((row, other))
                if other not in seen:
                    seen.add(other); next_frontier.add(other)
            frontier = next_frontier
            if not frontier: break
        confirmed, likely, unknown = [], [], []
        for row, other in impact:
            item = {"entity": other, "relation": row["relation"], "confidence": row["confidence_class"], "source": row["source"]}
            if row["status"] in {"observed", "user_confirmed"} and row["confidence_class"] in {"high", "confirmed"}: confirmed.append(item)
            elif row["status"] == "proposed" or row["observation_kind"] == "inferred": likely.append(item)
        if not traversed: unknown.append({"reason": "no evidence-backed dependency edges", "entity": entity_ref})
        return {"focus": entity_ref, "confirmed": confirmed, "likely": likely, "unknown": unknown}
