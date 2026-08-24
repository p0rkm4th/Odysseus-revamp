"""Owner-scoped execution-node metadata; not an authority or executor."""
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, Index, Integer, String, UniqueConstraint
from core.database import Base, TimestampMixin, utcnow_naive


class ExecutionNode(TimestampMixin, Base):
    __tablename__ = "execution_nodes"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True)
    node_key = Column(String(200), nullable=False); display_name = Column(String(300), nullable=False)
    trust_class = Column(String(32), nullable=False, default="standard")
    platform = Column(String(64), nullable=True); architecture = Column(String(64), nullable=True)
    cpu_count = Column(Integer, nullable=True); memory_mb = Column(Integer, nullable=True); gpu = Column(JSON, nullable=False, default=dict)
    runtimes = Column(JSON, nullable=False, default=list); capabilities = Column(JSON, nullable=False, default=list)
    privilege_classes = Column(JSON, nullable=False, default=list); network_reachability = Column(JSON, nullable=False, default=list)
    utilization = Column(JSON, nullable=False, default=dict); health = Column(String(32), nullable=False, default="unknown")
    last_heartbeat = Column(DateTime, nullable=True); metadata_json = Column(JSON, nullable=False, default=dict)
    __table_args__ = (
        UniqueConstraint("owner", "node_key", name="uq_execution_nodes_owner_key"),
        CheckConstraint("trust_class IN ('untrusted','standard','trusted','privileged')", name="ck_execution_node_trust"),
        CheckConstraint("health IN ('unknown','healthy','degraded','unavailable')", name="ck_execution_node_health"),
        Index("ix_execution_nodes_owner_health", "owner", "health"),
    )


EXECUTION_NODE_TABLES = (ExecutionNode.__table__,)
