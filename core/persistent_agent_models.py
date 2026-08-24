"""Canonical owner-scoped state for the persistent Hades agent."""
from sqlalchemy import JSON, Boolean, CheckConstraint, Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from core.database import Base, TimestampMixin, utcnow_naive


class AssistantInstance(TimestampMixin, Base):
    __tablename__ = "assistant_instances"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    canonical_name = Column(String(120), nullable=False, default="Hades")
    installation_id = Column(String(128), nullable=False, unique=True)
    lifecycle_status = Column(String(32), nullable=False, default="active")
    revision = Column(Integer, nullable=False, default=1)
    accepted_source = Column(String(128), nullable=True)
    accepted_runtime = Column(String(300), nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("owner", "canonical_name", name="uq_assistant_instance_owner_name"),)


class AssistantRuntimeSnapshot(Base):
    __tablename__ = "assistant_runtime_snapshots"
    id = Column(String, primary_key=True)
    assistant_instance_id = Column(String, nullable=False, index=True)
    owner = Column(String, nullable=False, index=True)
    observed_at = Column(DateTime, nullable=False, default=utcnow_naive, index=True)
    runtime_version = Column(String(128), nullable=True)
    source_reference = Column(String(128), nullable=True)
    image_reference = Column(String(300), nullable=True)
    model_profile = Column(String(128), nullable=True)
    local_model_health = Column(JSON, nullable=False, default=dict)
    routing_state = Column(JSON, nullable=False, default=dict)
    database_health = Column(String(32), nullable=False, default="healthy")
    broker_health = Column(JSON, nullable=False, default=dict)
    execution_environment = Column(JSON, nullable=False, default=dict)


class Episode(TimestampMixin, Base):
    __tablename__ = "assistant_episodes"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    episode_type = Column(String(64), nullable=False)
    title = Column(String(300), nullable=False)
    summary = Column(Text, nullable=False)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    outcome = Column(String(32), nullable=False, default="observed")
    status = Column(String(32), nullable=False, default="confirmed")
    source_event_id = Column(String, nullable=True, index=True)
    source_run_id = Column(String, nullable=True, index=True)
    domain_references = Column(JSON, nullable=False, default=list)
    evidence_references = Column(JSON, nullable=False, default=list)
    confidence = Column(Integer, nullable=False, default=80)
    significance = Column(Integer, nullable=False, default=50)
    provenance = Column(JSON, nullable=False, default=dict)
    __table_args__ = (Index("ix_assistant_episodes_owner_time", "owner", "ended_at"),)


class Lesson(TimestampMixin, Base):
    __tablename__ = "assistant_lessons"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    statement = Column(Text, nullable=False)
    domain = Column(String(64), nullable=False, default="general")
    confidence = Column(Integer, nullable=False, default=50)
    evidence_episode_refs = Column(JSON, nullable=False, default=list)
    first_observed = Column(DateTime, nullable=True)
    last_confirmed = Column(DateTime, nullable=True)
    supersedes = Column(String, nullable=True)
    status = Column(String(32), nullable=False, default="proposed")
    provenance = Column(JSON, nullable=False, default=dict)
    scope_context = Column(JSON, nullable=False, default=dict)
    __table_args__ = (CheckConstraint("status IN ('proposed','confirmed','rejected','superseded')", name="ck_assistant_lesson_status"),)


class Monitor(TimestampMixin, Base):
    __tablename__ = "assistant_monitors"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    condition_type = Column(String(64), nullable=False)
    source_domain = Column(String(64), nullable=False, default="system")
    query = Column(JSON, nullable=False, default=dict)
    condition = Column(JSON, nullable=False, default=dict)
    consequence_tier = Column(Integer, nullable=False, default=1)
    notification_policy = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True)
    last_evaluated = Column(DateTime, nullable=True)
    last_triggered = Column(DateTime, nullable=True)
    cooldown_seconds = Column(Integer, nullable=False, default=3600)
    revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("consequence_tier BETWEEN 0 AND 3", name="ck_assistant_monitor_tier"),)


class Notification(TimestampMixin, Base):
    __tablename__ = "assistant_notifications"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    notification_type = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False, default="info")
    title = Column(String(300), nullable=False)
    body = Column(Text, nullable=False)
    source_domain = Column(String(64), nullable=True)
    source_entity_id = Column(String, nullable=True)
    source_event_id = Column(String, nullable=True, index=True)
    source_run_id = Column(String, nullable=True)
    monitor_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow_naive, index=True)
    read_at = Column(DateTime, nullable=True)
    requires_action = Column(Boolean, nullable=False, default=False)
    delivery_state = Column(String(32), nullable=False, default="pending")
    dedupe_key = Column(String(300), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("owner", "dedupe_key", name="uq_assistant_notification_dedupe"),)


ASSISTANT_TABLES = tuple(x.__table__ for x in (AssistantInstance, AssistantRuntimeSnapshot, Episode, Lesson, Monitor, Notification))
