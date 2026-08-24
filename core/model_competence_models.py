"""Owner-scoped empirical model/task competence projections."""
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, Index, Integer, String, UniqueConstraint
from core.database import Base, TimestampMixin, utcnow_naive


class ModelCompetence(TimestampMixin, Base):
    __tablename__ = "model_competence"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True)
    model_key = Column(String(300), nullable=False); task_class = Column(String(160), nullable=False)
    sample_count = Column(Integer, nullable=False, default=0); success_count = Column(Integer, nullable=False, default=0)
    success_rate = Column(Integer, nullable=False, default=0); recent_success_rate = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=True); token_count = Column(Integer, nullable=True); estimated_cost = Column(JSON, nullable=False, default=dict)
    failure_classes = Column(JSON, nullable=False, default=list); qualification = Column(String(32), nullable=False, default="unknown")
    evidence_refs = Column(JSON, nullable=False, default=list); last_evaluated_at = Column(DateTime, nullable=True, default=utcnow_naive)
    __table_args__ = (UniqueConstraint("owner", "model_key", "task_class", name="uq_model_competence_owner_key_task"), CheckConstraint("qualification IN ('unknown','experimental','qualified','degraded','disqualified')", name="ck_model_competence_qualification"), Index("ix_model_competence_owner_task", "owner", "task_class", "qualification"))


COMPETENCE_TABLES = (ModelCompetence.__table__,)
