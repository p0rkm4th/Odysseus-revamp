"""Durable control-plane records for gated policy improvement.

Candidate rows identify externally reviewed, immutable artifacts by digest.  They
never contain prompt text, source traces, memories, or executable code.  Active
selection is a separate pointer so promotion and rollback are auditable.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String,
    UniqueConstraint, event,
)

from core.database import Base, TimestampMixin, utcnow_naive


class ImprovementCandidate(TimestampMixin, Base):
    __tablename__ = "improvement_candidates"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    policy_key = Column(String, nullable=False)
    version = Column(String, nullable=False)
    parent_version = Column(String, nullable=True)
    artifact_kind = Column(String, nullable=False)
    artifact_digest = Column(String(64), nullable=False)
    source_failure_counts_json = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint("owner", "policy_key", "version", name="uq_improvement_candidate_version"),
        CheckConstraint(
            "artifact_kind IN ('prompt_policy','retrieval_policy','tool_policy','capability_profile')",
            name="ck_improvement_candidate_kind",
        ),
        Index("ix_improvement_candidates_owner_policy", "owner", "policy_key", "created_at"),
    )


class ImprovementEvaluation(Base):
    __tablename__ = "improvement_evaluations"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    candidate_id = Column(String, ForeignKey("improvement_candidates.id", ondelete="RESTRICT"), nullable=False)
    baseline_report_json = Column(JSON, nullable=False)
    candidate_report_json = Column(JSON, nullable=False)
    evidence_policy_json = Column(JSON, nullable=False)
    verdict_json = Column(JSON, nullable=False)
    baseline_digest = Column(String(64), nullable=False)
    candidate_report_digest = Column(String(64), nullable=False)
    passed = Column(Integer, nullable=False)
    evaluated_at = Column(DateTime, nullable=False, default=utcnow_naive)
    __table_args__ = (
        CheckConstraint("passed IN (0,1)", name="ck_improvement_evaluation_passed"),
        Index("ix_improvement_evaluations_owner_candidate", "owner", "candidate_id", "evaluated_at"),
    )


class ActiveImprovementPolicy(TimestampMixin, Base):
    __tablename__ = "active_improvement_policies"
    owner = Column(String, primary_key=True)
    policy_key = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("improvement_candidates.id", ondelete="RESTRICT"), nullable=False)
    revision = Column(Integer, nullable=False, default=1)


class ImprovementPromotionEvent(Base):
    __tablename__ = "improvement_promotion_events"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    policy_key = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    from_candidate_id = Column(String, nullable=True)
    to_candidate_id = Column(String, ForeignKey("improvement_candidates.id", ondelete="RESTRICT"), nullable=False)
    evaluation_id = Column(String, ForeignKey("improvement_evaluations.id", ondelete="RESTRICT"), nullable=True)
    approved_by = Column(String, nullable=False)
    approval_digest = Column(String(64), nullable=False)
    idempotency_key = Column(String, nullable=False)
    occurred_at = Column(DateTime, nullable=False, default=utcnow_naive)
    __table_args__ = (
        UniqueConstraint("owner", "idempotency_key", name="uq_improvement_promotion_idempotency"),
        CheckConstraint("event_type IN ('promote','rollback')", name="ck_improvement_promotion_event"),
        Index("ix_improvement_promotion_history", "owner", "policy_key", "occurred_at"),
    )


IMPROVEMENT_TABLES = tuple(model.__table__ for model in (
    ImprovementCandidate, ImprovementEvaluation, ActiveImprovementPolicy,
    ImprovementPromotionEvent,
))


def _reject_immutable_change(*_args, **_kwargs):
    raise RuntimeError("improvement candidates, evaluations, and promotion events are append-only")


for _model in (ImprovementCandidate, ImprovementEvaluation, ImprovementPromotionEvent):
    event.listen(_model, "before_update", _reject_immutable_change)
    event.listen(_model, "before_delete", _reject_immutable_change)
