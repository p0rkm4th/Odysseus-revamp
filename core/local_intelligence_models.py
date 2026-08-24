"""Small durable records for explicitly granted developer authority."""
from sqlalchemy import Column, DateTime, Integer, String, Text, Index
from core.database import Base, utcnow_naive
class DeveloperLease(Base):
    __tablename__ = "developer_authority_leases"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True)
    workspace = Column(Text, nullable=False); granted_at = Column(DateTime, nullable=False, default=utcnow_naive); expires_at = Column(DateTime, nullable=False)
    run_id = Column(String, nullable=True, index=True); session_id = Column(String, nullable=True)
    network_policy = Column(String(64), nullable=False, default="normal"); authority = Column(String(64), nullable=False, default="workspace_bash")
    revoked_at = Column(DateTime, nullable=True); revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (Index("ix_developer_leases_owner_active", "owner", "expires_at", "revoked_at"),)
