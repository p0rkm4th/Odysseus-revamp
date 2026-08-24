"""Durable, redacted OTel-shaped trace projections for Hades requests/Runs."""
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String
from core.database import Base, utcnow_naive


class TraceSpan(Base):
    __tablename__ = "trace_spans"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    trace_id = Column(String(64), nullable=False, index=True)
    span_id = Column(String(64), nullable=False, unique=True)
    parent_span_id = Column(String(64), nullable=True)
    run_id = Column(String, ForeignKey("work_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="ok")
    attributes = Column(JSON, nullable=False, default=dict)
    started_at = Column(DateTime, nullable=False, default=utcnow_naive)
    ended_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    __table_args__ = (
        CheckConstraint("status IN ('ok','error','unset')", name="ck_trace_span_status"),
        Index("ix_trace_spans_owner_run_started", "owner", "run_id", "started_at"),
    )


OBSERVABILITY_TABLES = (TraceSpan.__table__,)
