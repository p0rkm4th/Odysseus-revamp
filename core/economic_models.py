"""Durable, owner-scoped control-plane records for supervised economic work."""

from __future__ import annotations

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint,
    event,
)

from core.database import Base, TimestampMixin, utcnow_naive


MONEY_MINOR_TYPE = Numeric(24, 0)


class EconomicControl(TimestampMixin, Base):
    __tablename__ = "economic_controls"
    owner = Column(String, primary_key=True)
    kill_switch_engaged = Column(Boolean, nullable=False, default=True)
    revision = Column(Integer, nullable=False, default=0)


class EconomicMandateRecord(TimestampMixin, Base):
    __tablename__ = "economic_mandates"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    digest = Column(String(64), nullable=False)
    policy_version = Column(String, nullable=False)
    autonomy_tier = Column(String, nullable=False, default="off")
    allowed_actions_json = Column(JSON, nullable=False, default=list)
    issued_at = Column(Integer, nullable=False)
    expires_at = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="inactive")
    external_actions_limit = Column(Integer, nullable=False, default=0)
    messages_limit = Column(Integer, nullable=False, default=0)
    submissions_limit = Column(Integer, nullable=False, default=0)
    gross_spend_minor_limit = Column(MONEY_MINOR_TYPE, nullable=False, default=0)
    committed_value_minor_limit = Column(MONEY_MINOR_TYPE, nullable=False, default=0)
    external_actions_used = Column(Integer, nullable=False, default=0)
    messages_used = Column(Integer, nullable=False, default=0)
    submissions_used = Column(Integer, nullable=False, default=0)
    gross_spend_minor_used = Column(MONEY_MINOR_TYPE, nullable=False, default=0)
    committed_value_minor_used = Column(MONEY_MINOR_TYPE, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("owner", "digest", name="uq_economic_mandate_owner_digest"),
        CheckConstraint("status IN ('inactive','active','revoked','expired')", name="ck_economic_mandate_status"),
        CheckConstraint("autonomy_tier IN ('off','observe','prepare','bounded_execution')", name="ck_economic_mandate_tier"),
        CheckConstraint("expires_at > issued_at", name="ck_economic_mandate_expiry"),
        CheckConstraint("external_actions_used >= 0 AND messages_used >= 0 AND submissions_used >= 0 AND gross_spend_minor_used >= 0 AND committed_value_minor_used >= 0", name="ck_economic_mandate_usage_nonnegative"),
        Index("ix_economic_mandates_owner_status_expiry", "owner", "status", "expires_at"),
    )


class EconomicJob(TimestampMixin, Base):
    __tablename__ = "economic_jobs"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    mandate_id = Column(String, ForeignKey("economic_mandates.id", ondelete="RESTRICT"), nullable=False)
    kind = Column(String, nullable=False)
    action = Column(String, nullable=False)
    title = Column(String, nullable=False)
    state = Column(String, nullable=False, default="proposed")
    proposal_json = Column(JSON, nullable=False, default=dict)
    result_json = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint("owner", "idempotency_key", name="uq_economic_job_owner_idempotency"),
        CheckConstraint("kind IN ('proposal','job')", name="ck_economic_job_kind"),
        CheckConstraint("state IN ('proposed','prepared','awaiting_approval','approved','executing','completed','failed','cancelled')", name="ck_economic_job_state"),
        Index("ix_economic_jobs_owner_state", "owner", "state", "created_at"),
    )


class EconomicBudgetUsage(Base):
    __tablename__ = "economic_budget_usage"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    mandate_id = Column(String, ForeignKey("economic_mandates.id", ondelete="RESTRICT"), nullable=False)
    job_id = Column(String, ForeignKey("economic_jobs.id", ondelete="RESTRICT"), nullable=True)
    idempotency_key = Column(String, nullable=False)
    external_actions_delta = Column(Integer, nullable=False, default=0)
    messages_delta = Column(Integer, nullable=False, default=0)
    submissions_delta = Column(Integer, nullable=False, default=0)
    gross_spend_minor_delta = Column(MONEY_MINOR_TYPE, nullable=False, default=0)
    committed_value_minor_delta = Column(MONEY_MINOR_TYPE, nullable=False, default=0)
    occurred_at = Column(DateTime, nullable=False, default=utcnow_naive)
    __table_args__ = (
        UniqueConstraint("owner", "idempotency_key", name="uq_economic_usage_owner_idempotency"),
        CheckConstraint("external_actions_delta >= 0 AND messages_delta >= 0 AND submissions_delta >= 0 AND gross_spend_minor_delta >= 0 AND committed_value_minor_delta >= 0", name="ck_economic_usage_nonnegative"),
    )


class EconomicApprovalReceipt(Base):
    __tablename__ = "economic_approval_receipts"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    mandate_id = Column(String, ForeignKey("economic_mandates.id", ondelete="RESTRICT"), nullable=False)
    job_id = Column(String, ForeignKey("economic_jobs.id", ondelete="RESTRICT"), nullable=False)
    action = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    mandate_digest = Column(String(64), nullable=False)
    exact_request_digest = Column(String(64), nullable=False)
    actor = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=False)
    decided_at = Column(DateTime, nullable=False, default=utcnow_naive)
    __table_args__ = (
        UniqueConstraint("owner", "idempotency_key", name="uq_economic_approval_owner_idempotency"),
        CheckConstraint("decision IN ('approved','denied')", name="ck_economic_approval_decision"),
    )


class EconomicAuditReceipt(Base):
    __tablename__ = "economic_audit_receipts"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    mandate_id = Column(String, nullable=True)
    job_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    detail_json = Column(JSON, nullable=False, default=dict)
    actor = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=False)
    occurred_at = Column(DateTime, nullable=False, default=utcnow_naive)
    __table_args__ = (UniqueConstraint("owner", "idempotency_key", name="uq_economic_audit_owner_idempotency"),)


ECONOMIC_TABLES = tuple(model.__table__ for model in (
    EconomicControl, EconomicMandateRecord, EconomicJob, EconomicBudgetUsage,
    EconomicApprovalReceipt, EconomicAuditReceipt,
))


def _reject_immutable_change(*_args, **_kwargs):
    raise RuntimeError("economic ledger and receipt records are append-only")


for _immutable_model in (EconomicBudgetUsage, EconomicApprovalReceipt, EconomicAuditReceipt):
    event.listen(_immutable_model, "before_update", _reject_immutable_change)
    event.listen(_immutable_model, "before_delete", _reject_immutable_change)
