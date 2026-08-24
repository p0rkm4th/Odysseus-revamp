"""Owner-scoped Incident and Change projections over Work/Run execution."""
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text
from core.database import Base, TimestampMixin, utcnow_naive


class Incident(TimestampMixin, Base):
    __tablename__ = "control_incidents"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True)
    title = Column(String(300), nullable=False); severity = Column(String(32), nullable=False, default="moderate")
    status = Column(String(32), nullable=False, default="reported"); symptoms = Column(JSON, nullable=False, default=list)
    affected_entities = Column(JSON, nullable=False, default=list); timeline = Column(JSON, nullable=False, default=list)
    evidence_references = Column(JSON, nullable=False, default=list); root_cause = Column(Text, nullable=True); outcome = Column(Text, nullable=True)
    opened_at = Column(DateTime, nullable=False, default=utcnow_naive); closed_at = Column(DateTime, nullable=True)
    __table_args__ = (CheckConstraint("status IN ('reported','triage','investigating','monitoring','resolved','reviewed','cancelled')", name="ck_incident_status"), Index("ix_incidents_owner_status", "owner", "status", "updated_at"))


class IncidentHypothesis(TimestampMixin, Base):
    __tablename__ = "control_incident_hypotheses"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True)
    incident_id = Column(String, ForeignKey("control_incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    statement = Column(Text, nullable=False); status = Column(String(32), nullable=False, default="open")
    confidence_class = Column(String(32), nullable=False, default="unknown"); supporting_evidence = Column(JSON, nullable=False, default=list); contradicting_evidence = Column(JSON, nullable=False, default=list)
    __table_args__ = (CheckConstraint("status IN ('open','supported','rejected','superseded')", name="ck_incident_hypothesis_status"),)


class Change(TimestampMixin, Base):
    __tablename__ = "control_changes"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True)
    incident_id = Column(String, ForeignKey("control_incidents.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id = Column(String, ForeignKey("work_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    objective = Column(Text, nullable=False); status = Column(String(32), nullable=False, default="draft")
    targets = Column(JSON, nullable=False, default=list); desired_state = Column(JSON, nullable=False, default=dict)
    preview = Column(JSON, nullable=False, default=dict); prechecks = Column(JSON, nullable=False, default=list)
    action_ids = Column(JSON, nullable=False, default=list); resources = Column(JSON, nullable=False, default=list)
    risk = Column(String(32), nullable=False, default="low"); blast_radius = Column(JSON, nullable=False, default=dict)
    approval = Column(JSON, nullable=False, default=dict); compensation = Column(JSON, nullable=False, default=dict)
    verification = Column(JSON, nullable=False, default=dict); outcome = Column(JSON, nullable=False, default=dict)
    __table_args__ = (CheckConstraint("status IN ('draft','validated','awaiting_approval','scheduled','executing','verifying','completed','failed','compensated','cancelled')", name="ck_change_status"), Index("ix_changes_owner_status", "owner", "status", "updated_at"))


INCIDENT_TABLES = tuple(x.__table__ for x in (Incident, IncidentHypothesis, Change))
