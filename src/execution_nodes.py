"""Deterministic execution-node registry and eligibility projection."""
from core.execution_node_models import ExecutionNode
from src.work_engine import WorkError, ident, now, serialize

TRUST = {"untrusted", "standard", "trusted", "privileged"}
HEALTH = {"unknown", "healthy", "degraded", "unavailable"}


class ExecutionNodeService:
    def __init__(self, db): self.db = db

    def register(self, owner, data):
        key = str(data.get("node_key") or "").strip()
        if not key: raise WorkError("execution node key is required")
        trust = str(data.get("trust_class") or "standard").lower()
        health = str(data.get("health") or "unknown").lower()
        if trust not in TRUST: raise WorkError("invalid execution node trust class")
        if health not in HEALTH: raise WorkError("invalid execution node health")
        row = self.db.query(ExecutionNode).filter_by(owner=owner, node_key=key).one_or_none()
        if row is None:
            row = ExecutionNode(id=ident("node"), owner=owner, node_key=key[:200], display_name=str(data.get("display_name") or key)[:300])
            self.db.add(row)
        for field in ("display_name", "trust_class", "platform", "architecture", "cpu_count", "memory_mb", "gpu", "runtimes", "capabilities", "privilege_classes", "network_reachability", "utilization", "health", "metadata_json"):
            if field in data: setattr(row, field, data[field])
        row.last_heartbeat = now() if data.get("heartbeat", False) else row.last_heartbeat
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def heartbeat(self, owner, node_key, *, health="healthy", utilization=None):
        return self.register(owner, {"node_key": node_key, "health": health, "utilization": utilization or {}, "heartbeat": True})

    def list(self, owner, *, health=None, limit=200):
        query = self.db.query(ExecutionNode).filter_by(owner=owner)
        if health: query = query.filter_by(health=health)
        return [serialize(row) for row in query.order_by(ExecutionNode.node_key).limit(max(1, min(int(limit), 500))).all()]

    def select(self, owner, requirements=None, *, limit=1):
        requirements = requirements or {}; candidates = []
        for row in self.db.query(ExecutionNode).filter_by(owner=owner).all():
            if row.health not in {"unknown", "healthy"}: continue
            if requirements.get("platform") and row.platform != requirements["platform"]: continue
            if requirements.get("architecture") and row.architecture != requirements["architecture"]: continue
            if requirements.get("runtime") and requirements["runtime"] not in (row.runtimes or []): continue
            if requirements.get("capability") and requirements["capability"] not in (row.capabilities or []): continue
            if requirements.get("privilege_class") and requirements["privilege_class"] not in (row.privilege_classes or []): continue
            if requirements.get("network_reachability") and requirements["network_reachability"] not in (row.network_reachability or []): continue
            if requirements.get("sandbox") is True and "sandbox" not in (row.capabilities or []): continue
            utilization = (row.utilization or {}).get("cpu_percent", 100)
            candidates.append((float(utilization or 0), row.node_key, row))
        selected = [serialize(row) for _, _, row in sorted(candidates, key=lambda item: (item[0], item[1]))[:max(1, min(int(limit), 20))]]
        return {"requirements": requirements, "nodes": selected, "eligible": bool(selected), "authority_unchanged": True}
