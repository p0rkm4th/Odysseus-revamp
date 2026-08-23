"""Canonical, domain-neutral durable work state."""
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from core.database import Base, TimestampMixin, utcnow_naive

class WorkGoal(TimestampMixin, Base):
    __tablename__ = "work_goals"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True)
    title = Column(String(300), nullable=False); description = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="draft"); priority = Column(Integer, nullable=False, default=0)
    desired_outcome = Column(Text, nullable=False, default=""); success_criteria = Column(JSON, nullable=False, default=dict)
    constraints = Column(JSON, nullable=False, default=dict); deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True); source = Column(String(64), nullable=False, default="operator"); revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("status IN ('draft','active','blocked','paused','completed','cancelled','failed')", name="ck_work_goal_status"), Index("ix_work_goals_owner_status", "owner", "status", "updated_at"))

class WorkProject(TimestampMixin, Base):
    __tablename__ = "work_projects"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True)
    goal_id = Column(String, ForeignKey("work_goals.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(300), nullable=False); description = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="planned"); priority = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True); target_date = Column(DateTime, nullable=True); completed_at = Column(DateTime, nullable=True)
    external_reference = Column(String(500), nullable=True); domain = Column(String(64), nullable=False, default="general"); revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("status IN ('planned','active','blocked','paused','completed','cancelled')", name="ck_work_project_status"), Index("ix_work_projects_owner_status", "owner", "status", "updated_at"))

class WorkTask(TimestampMixin, Base):
    __tablename__ = "work_tasks"
    id = Column(String, primary_key=True); project_id = Column(String, ForeignKey("work_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_task_id = Column(String, ForeignKey("work_tasks.id", ondelete="CASCADE"), nullable=True, index=True); owner = Column(String, nullable=False, index=True)
    title = Column(String(300), nullable=False); description = Column(Text, nullable=False, default=""); status = Column(String(32), nullable=False, default="pending"); priority = Column(Integer, nullable=False, default=0)
    assignee_type = Column(String(32), nullable=False, default="operator"); assignee_ref = Column(String(300), nullable=True); success_criteria = Column(JSON, nullable=False, default=dict)
    blocked_reason = Column(Text, nullable=True); due_at = Column(DateTime, nullable=True); started_at = Column(DateTime, nullable=True); completed_at = Column(DateTime, nullable=True); revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("status IN ('pending','ready','running','awaiting_approval','awaiting_input','blocked','completed','failed','cancelled')", name="ck_work_task_status"), Index("ix_work_tasks_owner_status", "owner", "status", "updated_at"))

class WorkTaskDependency(Base):
    __tablename__ = "work_task_dependencies"
    owner = Column(String, primary_key=True); task_id = Column(String, ForeignKey("work_tasks.id", ondelete="CASCADE"), primary_key=True); depends_on_task_id = Column(String, ForeignKey("work_tasks.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=utcnow_naive)
    __table_args__ = (CheckConstraint("task_id <> depends_on_task_id", name="ck_work_task_dependency_not_self"),)

class WorkRun(TimestampMixin, Base):
    __tablename__ = "work_runs"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True); goal_id = Column(String, ForeignKey("work_goals.id", ondelete="SET NULL"), nullable=True, index=True); project_id = Column(String, ForeignKey("work_projects.id", ondelete="SET NULL"), nullable=True, index=True); task_id = Column(String, ForeignKey("work_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(String, nullable=True); domain = Column(String(64), nullable=False, default="general"); status = Column(String(32), nullable=False, default="queued"); current_step = Column(String(300), nullable=True); started_at = Column(DateTime, nullable=True); ended_at = Column(DateTime, nullable=True); requested_by = Column(String, nullable=False); model_endpoint = Column(String(300), nullable=True); model_name = Column(String(300), nullable=True); result_summary = Column(JSON, nullable=False, default=dict); error_summary = Column(Text, nullable=True); continuation_state = Column(JSON, nullable=False, default=dict); revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("status IN ('queued','running','awaiting_approval','awaiting_input','suspended','completed','failed','cancelled')", name="ck_work_run_status"), Index("ix_work_runs_owner_status", "owner", "status", "updated_at"))

class WorkAction(TimestampMixin, Base):
    __tablename__ = "work_actions"
    id = Column(String, primary_key=True); run_id = Column(String, ForeignKey("work_runs.id", ondelete="CASCADE"), nullable=False, index=True); sequence = Column(Integer, nullable=False); capability_id = Column(String(200), nullable=False); action_id = Column(String(200), nullable=False); tool_binding_name = Column(String(200), nullable=True); effect_class = Column(String(100), nullable=False, default="internal"); sealed_input_digest = Column(String(128), nullable=True); normalized_input = Column(JSON, nullable=False, default=dict); status = Column(String(32), nullable=False, default="proposed"); approval_reference = Column(String(300), nullable=True); requested_at = Column(DateTime, nullable=False, default=utcnow_naive); started_at = Column(DateTime, nullable=True); completed_at = Column(DateTime, nullable=True); result_reference = Column(String(1000), nullable=True); error = Column(Text, nullable=True); replay_of_action_id = Column(String, ForeignKey("work_actions.id", ondelete="SET NULL"), nullable=True); revision = Column(Integer, nullable=False, default=1)
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_work_action_run_sequence"), CheckConstraint("status IN ('proposed','awaiting_approval','approved','executing','completed','failed','rejected','cancelled','expired')", name="ck_work_action_status"))

class WorkResult(TimestampMixin, Base):
    __tablename__ = "work_results"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True); run_id = Column(String, ForeignKey("work_runs.id", ondelete="CASCADE"), nullable=False, index=True); action_id = Column(String, ForeignKey("work_actions.id", ondelete="CASCADE"), nullable=True); result_type = Column(String(64), nullable=False); reference = Column(String(1000), nullable=False); domain_reference = Column(JSON, nullable=True); content_digest = Column(String(128), nullable=True); metadata_json = Column(JSON, nullable=False, default=dict); provenance = Column(JSON, nullable=False, default=dict)

class WorkArtifact(TimestampMixin, Base):
    __tablename__ = "work_artifacts"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True); run_id = Column(String, ForeignKey("work_runs.id", ondelete="CASCADE"), nullable=False, index=True); action_id = Column(String, ForeignKey("work_actions.id", ondelete="CASCADE"), nullable=True); artifact_type = Column(String(64), nullable=False); reference = Column(String(1000), nullable=False); content_digest = Column(String(128), nullable=True); metadata_json = Column(JSON, nullable=False, default=dict); provenance = Column(JSON, nullable=False, default=dict)

class WorkEvent(Base):
    __tablename__ = "work_events"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True); event_type = Column(String(100), nullable=False); goal_id = Column(String, nullable=True, index=True); project_id = Column(String, nullable=True, index=True); task_id = Column(String, nullable=True, index=True); run_id = Column(String, nullable=True, index=True); action_id = Column(String, nullable=True, index=True); payload = Column(JSON, nullable=False, default=dict); created_at = Column(DateTime, nullable=False, default=utcnow_naive); __table_args__ = (Index("ix_work_events_owner_created", "owner", "created_at"),)

class WorkCommitment(TimestampMixin, Base):
    __tablename__ = "work_commitments"
    id = Column(String, primary_key=True); owner = Column(String, nullable=False, index=True); goal_id = Column(String, nullable=True, index=True); project_id = Column(String, nullable=True, index=True); task_id = Column(String, nullable=True, index=True); run_id = Column(String, nullable=True, index=True); text = Column(Text, nullable=False); due_at = Column(DateTime, nullable=True); status = Column(String(32), nullable=False, default="open"); source = Column(String(64), nullable=False, default="operator"); completed_at = Column(DateTime, nullable=True)
    __table_args__ = (CheckConstraint("status IN ('open','satisfied','missed','cancelled')", name="ck_work_commitment_status"),)

WORK_TABLES = tuple(x.__table__ for x in (WorkGoal, WorkProject, WorkTask, WorkTaskDependency, WorkRun, WorkAction, WorkResult, WorkArtifact, WorkEvent, WorkCommitment))
