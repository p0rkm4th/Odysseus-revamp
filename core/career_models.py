"""Durable Career projections owned by Work, not by external providers."""
from sqlalchemy import JSON, CheckConstraint, Column, ForeignKey, Index, String, Text
from core.database import Base, TimestampMixin


class CareerProfile(TimestampMixin, Base):
    __tablename__ = "career_profiles"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    headline = Column(String(300), nullable=False, default="")
    preferences = Column(JSON, nullable=False, default=dict)
    resume_document_refs = Column(JSON, nullable=False, default=list)
    __table_args__ = ()


class JobSearch(TimestampMixin, Base):
    __tablename__ = "career_job_searches"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    name = Column(String(300), nullable=False)
    criteria = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="active")
    provider_refs = Column(JSON, nullable=False, default=list)
    __table_args__ = (
        CheckConstraint("status IN ('active','paused','archived')", name="ck_career_search_status"),
        Index("ix_career_searches_owner_status", "owner", "status"),
    )


class JobOpportunity(TimestampMixin, Base):
    __tablename__ = "career_job_opportunities"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    dedup_key = Column(String(500), nullable=False)
    title = Column(String(500), nullable=False)
    employer = Column(String(500), nullable=False, default="")
    location = Column(String(500), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    normalized = Column(JSON, nullable=False, default=dict)
    provider_refs = Column(JSON, nullable=False, default=list)
    state = Column(String(32), nullable=False, default="new")
    source = Column(String(500), nullable=False, default="provider")
    __table_args__ = (
        CheckConstraint("state IN ('new','saved','dismissed','archived')", name="ck_career_opportunity_state"),
        Index("ix_career_opportunities_owner_dedup", "owner", "dedup_key", unique=True),
    )


class JobApplication(TimestampMixin, Base):
    __tablename__ = "career_applications"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    opportunity_id = Column(String, ForeignKey("career_job_opportunities.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="draft")
    contact_refs = Column(JSON, nullable=False, default=list)
    task_refs = Column(JSON, nullable=False, default=list)
    document_refs = Column(JSON, nullable=False, default=list)
    follow_up_at = Column(String(64), nullable=True)
    notes = Column(Text, nullable=False, default="")
    __table_args__ = (Index("ix_career_applications_owner_status", "owner", "status"),)


class JobInterview(TimestampMixin, Base):
    __tablename__ = "career_interviews"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    application_id = Column(String, ForeignKey("career_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    calendar_event_ref = Column(String(500), nullable=True)
    starts_at = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="scheduled")
    notes = Column(Text, nullable=False, default="")


CAREER_TABLES = (CareerProfile.__table__, JobSearch.__table__, JobOpportunity.__table__, JobApplication.__table__, JobInterview.__table__)
