"""Durable metadata for disposable execution sandboxes.

This model is an audited lifecycle projection, not a container runtime.  The
trusted execution adapter remains a future, separately reviewed boundary.
"""
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, String
from core.database import Base, TimestampMixin


class SandboxSession(TimestampMixin, Base):
    __tablename__ = "sandbox_sessions"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    run_id = Column(String, ForeignKey("work_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    node_key = Column(String(200), nullable=False)
    workload_type = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="planned")
    network_policy = Column(JSON, nullable=False, default=dict)
    resource_limits = Column(JSON, nullable=False, default=dict)
    workspace_ref = Column(String(500), nullable=True)
    artifact_refs = Column(JSON, nullable=False, default=list)
    failure_summary = Column(String(2000), nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    revision = Column(String(64), nullable=False, default="1")
    __table_args__ = (
        CheckConstraint("status IN ('planned','creating','active','exporting','destroyed','failed','cancelled')", name="ck_sandbox_status"),
        Index("ix_sandbox_owner_status", "owner", "status", "updated_at"),
    )


SANDBOX_TABLES = (SandboxSession.__table__,)
