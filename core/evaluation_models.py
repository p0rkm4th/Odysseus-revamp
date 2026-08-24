"""Owner-scoped durable evaluation and supervised failure records.

Evaluation records describe sanitized trajectories and expected properties. They
do not store raw prompts, secrets, or model chain-of-thought.
"""
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text
from core.database import Base, TimestampMixin, utcnow_naive


class EvaluationScenario(TimestampMixin, Base):
    __tablename__ = "evaluation_scenarios"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    scenario_key = Column(String(200), nullable=False)
    domain = Column(String(64), nullable=False)
    task_class = Column(String(128), nullable=False)
    title = Column(String(300), nullable=False)
    initial_state = Column(JSON, nullable=False, default=dict)
    initial_epistemic_state = Column(JSON, nullable=False, default=dict)
    user_intent = Column(Text, nullable=False, default="")
    available_capabilities = Column(JSON, nullable=False, default=list)
    available_models = Column(JSON, nullable=False, default=list)
    authority = Column(JSON, nullable=False, default=dict)
    expected = Column(JSON, nullable=False, default=dict)
    forbidden = Column(JSON, nullable=False, default=dict)
    scoring = Column(JSON, nullable=False, default=dict)
    source_failure_id = Column(String, nullable=True)
    status = Column(String(32), nullable=False, default="active")
    __table_args__ = (
        CheckConstraint("status IN ('active','retired','draft')", name="ck_eval_scenario_status"),
        Index("ix_eval_scenarios_owner_domain", "owner", "domain", "status"),
    )


class EvaluationRun(TimestampMixin, Base):
    __tablename__ = "evaluation_runs"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    scenario_id = Column(String, ForeignKey("evaluation_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    work_run_id = Column(String, ForeignKey("work_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    model = Column(JSON, nullable=False, default=dict)
    trajectory = Column(JSON, nullable=False, default=dict)
    score = Column(JSON, nullable=False, default=dict)
    metrics = Column(JSON, nullable=False, default=dict)
    artifacts = Column(JSON, nullable=False, default=list)
    failure_category = Column(String(64), nullable=False, default="none")
    status = Column(String(32), nullable=False, default="completed")
    passed = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=False, default=utcnow_naive)
    ended_at = Column(DateTime, nullable=True)
    __table_args__ = (
        CheckConstraint("status IN ('running','completed','failed','cancelled')", name="ck_eval_run_status"),
        CheckConstraint("passed IS NULL OR passed IN (0,1)", name="ck_eval_run_passed"),
        Index("ix_eval_runs_owner_scenario", "owner", "scenario_id", "created_at"),
    )


class EvaluationFailure(TimestampMixin, Base):
    __tablename__ = "evaluation_failures"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    evaluation_run_id = Column(String, ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    work_run_id = Column(String, ForeignKey("work_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(300), nullable=False)
    taxonomy = Column(String(128), nullable=False)
    impact = Column(String(32), nullable=False, default="low")
    reproducibility = Column(String(32), nullable=False, default="unknown")
    sanitized_context = Column(JSON, nullable=False, default=dict)
    expected_behavior = Column(JSON, nullable=False, default=dict)
    actual_behavior = Column(JSON, nullable=False, default=dict)
    proposed_scenario = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="pending_review")
    reviewed_by = Column(String(200), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    __table_args__ = (
        CheckConstraint("status IN ('pending_review','admitted','rejected')", name="ck_eval_failure_status"),
        Index("ix_eval_failures_owner_status", "owner", "status", "created_at"),
    )


EVALUATION_TABLES = tuple(model.__table__ for model in (EvaluationScenario, EvaluationRun, EvaluationFailure))
