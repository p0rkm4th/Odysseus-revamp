"""Short-lived exact-scope capability grants over existing approvals."""
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String
from core.database import Base, TimestampMixin, utcnow_naive


class DelegatedCapabilityGrant(TimestampMixin, Base):
    __tablename__ = "delegated_capability_grants"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True)
    run_id = Column(String, ForeignKey("work_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    action_id = Column(String, ForeignKey("work_actions.id", ondelete="CASCADE"), nullable=False, index=True)
    capability_id = Column(String(200), nullable=False); target_resources = Column(JSON, nullable=False, default=list)
    parameter_constraints = Column(JSON, nullable=False, default=dict); sealed_input_digest = Column(String(128), nullable=False)
    approval_reference = Column(String(300), nullable=False); max_calls = Column(Integer, nullable=False, default=1); consumed_calls = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=False); revoked_at = Column(DateTime, nullable=True); consumed_at = Column(DateTime, nullable=True)
    __table_args__ = (CheckConstraint("max_calls > 0 AND consumed_calls >= 0 AND consumed_calls <= max_calls", name="ck_grant_call_bounds"), Index("ix_grants_owner_active", "owner", "expires_at", "revoked_at"))


DELEGATED_GRANT_TABLES = (DelegatedCapabilityGrant.__table__,)
