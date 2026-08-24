"""Owner-scoped disposable-sandbox lifecycle metadata.

The service intentionally does not execute commands or create containers.  It
records a bounded request that a future trusted adapter may consume after a
separate security review.
"""
from core.execution_node_models import ExecutionNode
from core.sandbox_models import SandboxSession
from core.work_models import WorkRun
from src.work_engine import WorkError, ident, now, serialize

WORKLOADS = {"repository", "generated_code", "unknown_script", "package_experiment", "suspicious_file", "other"}
STATUSES = {"planned", "creating", "active", "exporting", "destroyed", "failed", "cancelled"}
TRANSITIONS = {
    "planned": {"creating", "cancelled"},
    "creating": {"active", "failed", "cancelled"},
    "active": {"exporting", "destroyed", "failed", "cancelled"},
    "exporting": {"destroyed", "failed"},
    "failed": {"destroyed"},
    "destroyed": set(),
    "cancelled": set(),
}


class SandboxService:
    def __init__(self, db):
        self.db = db

    def _one(self, owner, sandbox_id):
        row = self.db.query(SandboxSession).filter_by(owner=owner, id=sandbox_id).one_or_none()
        if row is None:
            raise WorkError("sandbox not found")
        return row

    @staticmethod
    def _bounded_limits(value):
        limits = dict(value or {})
        allowed = {"cpu_seconds", "memory_mb", "disk_mb", "pids", "wall_seconds"}
        if set(limits) - allowed:
            raise WorkError("sandbox resource limit is unsupported")
        for key, raw in limits.items():
            value = int(raw)
            if value < 1 or value > 1_000_000:
                raise WorkError("sandbox resource limit is out of bounds")
            limits[key] = value
        return limits

    @staticmethod
    def _network_policy(value):
        policy = dict(value or {})
        mode = str(policy.get("mode") or "none").lower()
        if mode not in {"none", "allowlist"}:
            raise WorkError("sandbox network policy must be none or allowlist")
        hosts = policy.get("hosts") or []
        if not isinstance(hosts, list) or len(hosts) > 32 or any(not isinstance(host, str) or not host.strip() for host in hosts):
            raise WorkError("sandbox network host allowlist is invalid")
        if mode == "none" and hosts:
            raise WorkError("sandbox network-none policy cannot contain hosts")
        return {"mode": mode, "hosts": [host.strip()[:255] for host in hosts]}

    def create(self, owner, data):
        run_id = str(data.get("run_id") or "")
        node_key = str(data.get("node_key") or "")
        workload_type = str(data.get("workload_type") or "other").lower()
        if not run_id or not node_key:
            raise WorkError("sandbox requires a Run and execution node")
        if workload_type not in WORKLOADS:
            raise WorkError("unsupported sandbox workload")
        if self.db.query(WorkRun).filter_by(owner=owner, id=run_id).one_or_none() is None:
            raise WorkError("sandbox Run not found")
        node = self.db.query(ExecutionNode).filter_by(owner=owner, node_key=node_key).one_or_none()
        if node is None:
            raise WorkError("sandbox execution node not found")
        if node.health not in {"unknown", "healthy"}:
            raise WorkError("sandbox execution node is not healthy")
        if node.trust_class == "privileged":
            raise WorkError("privileged execution nodes cannot host sandboxes")
        if "sandbox" not in (node.capabilities or []):
            raise WorkError("execution node does not advertise sandbox capability")
        row = SandboxSession(
            id=ident("sandbox"), owner=owner, run_id=run_id, node_key=node_key,
            workload_type=workload_type, network_policy=self._network_policy(data.get("network_policy")),
            resource_limits=self._bounded_limits(data.get("resource_limits")),
            workspace_ref=str(data.get("workspace_ref") or "")[:500] or None,
        )
        self.db.add(row); self.db.commit(); self.db.refresh(row)
        return serialize(row) | {"authority_unchanged": True, "runtime_adapter": "not_configured"}

    def get(self, owner, sandbox_id):
        return serialize(self._one(owner, sandbox_id)) | {"authority_unchanged": True, "runtime_adapter": "not_configured"}

    def list(self, owner, *, status=None, limit=200):
        query = self.db.query(SandboxSession).filter_by(owner=owner)
        if status:
            if status not in STATUSES:
                raise WorkError("invalid sandbox status")
            query = query.filter_by(status=status)
        return [serialize(row) | {"authority_unchanged": True, "runtime_adapter": "not_configured"} for row in query.order_by(SandboxSession.updated_at.desc()).limit(max(1, min(int(limit), 500))).all()]

    def transition(self, owner, sandbox_id, status, *, artifacts=None, error=None):
        row = self._one(owner, sandbox_id); status = str(status or "").lower()
        if status not in STATUSES or status not in TRANSITIONS.get(row.status, set()):
            raise WorkError("invalid sandbox lifecycle transition")
        if artifacts is not None:
            if not isinstance(artifacts, list) or len(artifacts) > 100 or any(not isinstance(ref, str) or not ref.strip() for ref in artifacts):
                raise WorkError("sandbox artifact references are invalid")
            row.artifact_refs = [ref.strip()[:1000] for ref in artifacts]
        row.status = status
        row.failure_summary = str(error or "")[:2000] or None
        if status == "active" and row.started_at is None:
            row.started_at = now()
        if status in {"destroyed", "failed", "cancelled"}:
            row.ended_at = now()
        row.revision = str(int(row.revision or "1") + 1)
        self.db.commit(); self.db.refresh(row)
        return serialize(row) | {"authority_unchanged": True, "runtime_adapter": "not_configured"}
