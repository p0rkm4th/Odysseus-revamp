"""Durable, owner-scoped records for bounded security assessments.

This schema stores authorization, scope decisions, provenance, and reporting
state.  It intentionally contains no exploit, credential, or arbitrary-command
executor.
"""

from __future__ import annotations

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text

from core.database import Base, TimestampMixin, utcnow_naive


class SecurityEngagement(TimestampMixin, Base):
    __tablename__ = "security_engagements"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="draft")
    assessment_type = Column(String(64), nullable=False, default="security_review")
    starts_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    authorization_status = Column(String(32), nullable=False, default="pending")
    authorization_reference = Column(String(300), nullable=True)
    authorization_notes = Column(Text, nullable=False, default="")
    rules_of_engagement = Column(Text, nullable=False, default="")
    created_by = Column(String, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (
        CheckConstraint("status IN ('draft','awaiting_authorization','authorized','active','paused','completed','cancelled','expired')", name="ck_security_engagement_status"),
        CheckConstraint("authorization_status IN ('pending','authorized','rejected','expired','revoked')", name="ck_security_authorization_status"),
        Index("ix_security_engagement_owner_status", "owner", "status", "updated_at"),
    )


class SecurityAuthorization(TimestampMixin, Base):
    __tablename__ = "security_authorizations"
    id = Column(String, primary_key=True)
    engagement_id = Column(String, ForeignKey("security_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    owner = Column(String, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending")
    reference = Column(String(300), nullable=False)
    notes = Column(Text, nullable=False, default="")
    valid_from = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    approved_by = Column(String, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("status IN ('pending','authorized','rejected','expired','revoked')", name="ck_security_authorization_record_status"),)


class SecurityScope(TimestampMixin, Base):
    __tablename__ = "security_scopes"
    id = Column(String, primary_key=True)
    engagement_id = Column(String, ForeignKey("security_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    owner = Column(String, nullable=False, index=True)
    includes_json = Column(JSON, nullable=False, default=list)
    exclusions_json = Column(JSON, nullable=False, default=list)
    allowed_actions_json = Column(JSON, nullable=False, default=list)
    prohibited_actions_json = Column(JSON, nullable=False, default=list)
    valid_from = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=False, default="")
    revision = Column(Integer, nullable=False, default=1)


class SecurityTarget(TimestampMixin, Base):
    __tablename__ = "security_targets"
    id = Column(String, primary_key=True)
    engagement_id = Column(String, ForeignKey("security_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    scope_id = Column(String, ForeignKey("security_scopes.id", ondelete="RESTRICT"), nullable=False)
    owner = Column(String, nullable=False, index=True)
    target_kind = Column(String(32), nullable=False)
    target_value = Column(String(500), nullable=False)
    canonical_asset_id = Column(String, nullable=True, index=True)
    inventory_item_id = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    revision = Column(Integer, nullable=False, default=1)


class SecurityRun(TimestampMixin, Base):
    __tablename__ = "security_runs"
    id = Column(String, primary_key=True)
    engagement_id = Column(String, ForeignKey("security_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(String, ForeignKey("security_targets.id", ondelete="RESTRICT"), nullable=False)
    scope_id = Column(String, ForeignKey("security_scopes.id", ondelete="RESTRICT"), nullable=False)
    owner = Column(String, nullable=False, index=True)
    run_class = Column(String(64), nullable=False)
    capability_id = Column(String, nullable=False)
    action_id = Column(String, nullable=False)
    status = Column(String(32), nullable=False, default="planned")
    requester = Column(String, nullable=False)
    authorization_decision = Column(String(32), nullable=False)
    approval_reference = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    result_summary_json = Column(JSON, nullable=False, default=dict)
    error = Column(Text, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (
        CheckConstraint("status IN ('planned','approved','running','completed','failed','cancelled')", name="ck_security_run_status"),
        CheckConstraint("run_class IN ('posture_review','reconnaissance','host_discovery','service_enumeration','configuration_review','vulnerability_observation','remediation_validation')", name="ck_security_run_class"),
        Index("ix_security_runs_owner_status", "owner", "status", "created_at"),
    )


class SecurityEvidence(TimestampMixin, Base):
    __tablename__ = "security_evidence"
    id = Column(String, primary_key=True)
    engagement_id = Column(String, ForeignKey("security_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(String, ForeignKey("security_runs.id", ondelete="RESTRICT"), nullable=True, index=True)
    target_id = Column(String, ForeignKey("security_targets.id", ondelete="RESTRICT"), nullable=True)
    owner = Column(String, nullable=False, index=True)
    evidence_kind = Column(String(64), nullable=False)
    reference = Column(String(1000), nullable=False)
    structured_facts_json = Column(JSON, nullable=False, default=dict)
    observed_at = Column(DateTime, nullable=False, default=utcnow_naive)
    source_trust = Column(String(32), nullable=False, default="system")
    confidence = Column(String(32), nullable=False, default="medium")
    content_digest = Column(String(64), nullable=True)


class SecurityFinding(TimestampMixin, Base):
    __tablename__ = "security_findings"
    id = Column(String, primary_key=True)
    engagement_id = Column(String, ForeignKey("security_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(String, ForeignKey("security_targets.id", ondelete="RESTRICT"), nullable=True)
    run_id = Column(String, ForeignKey("security_runs.id", ondelete="RESTRICT"), nullable=True)
    owner = Column(String, nullable=False, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False, default="informational")
    confidence = Column(String(32), nullable=False, default="medium")
    status = Column(String(32), nullable=False, default="draft")
    first_seen = Column(DateTime, nullable=False, default=utcnow_naive)
    last_seen = Column(DateTime, nullable=False, default=utcnow_naive)
    evidence_refs_json = Column(JSON, nullable=False, default=list)
    remediation = Column(Text, nullable=False, default="")
    verification_state = Column(String(32), nullable=False, default="unverified")
    created_by = Column(String, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    scoring_basis = Column(String(100), nullable=False, default="operator_recorded")
    __table_args__ = (
        CheckConstraint("severity IN ('informational','low','medium','high','critical')", name="ck_security_finding_severity"),
        CheckConstraint("status IN ('draft','confirmed','accepted_risk','remediation_planned','remediated','verification_pending','verified','false_positive','closed')", name="ck_security_finding_status"),
        Index("ix_security_findings_owner_status_severity", "owner", "status", "severity"),
    )


class SecurityReport(TimestampMixin, Base):
    __tablename__ = "security_reports"
    id = Column(String, primary_key=True)
    engagement_id = Column(String, ForeignKey("security_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    owner = Column(String, nullable=False, index=True)
    generated_by = Column(String, nullable=False)
    generated_at = Column(DateTime, nullable=False, default=utcnow_naive)
    projection_json = Column(JSON, nullable=False, default=dict)
    source_revision = Column(Integer, nullable=False)


SECURITY_ASSESSMENT_TABLES = tuple(model.__table__ for model in (
    SecurityEngagement, SecurityAuthorization, SecurityScope, SecurityTarget,
    SecurityRun, SecurityEvidence, SecurityFinding, SecurityReport,
))
