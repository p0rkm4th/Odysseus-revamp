"""Owner-scoped durable work engine and bounded domain adapters."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import uuid4
from sqlalchemy.orm import Session
from core.work_models import (WorkAction, WorkArtifact, WorkCommitment, WorkEvent, WorkGoal, WorkProject, WorkResult, WorkRun, WorkTask, WorkTaskDependency)

GOAL_STATUSES = {"draft", "active", "blocked", "paused", "completed", "cancelled", "failed"}
PROJECT_STATUSES = {"planned", "active", "blocked", "paused", "completed", "cancelled"}
TASK_STATUSES = {"pending", "ready", "running", "awaiting_approval", "awaiting_input", "blocked", "completed", "failed", "cancelled"}
RUN_STATUSES = {"queued", "running", "awaiting_approval", "awaiting_input", "suspended", "completed", "failed", "cancelled"}
ACTION_STATUSES = {"proposed", "awaiting_approval", "approved", "executing", "completed", "failed", "rejected", "cancelled", "expired"}

class WorkError(ValueError): pass

def now(): return datetime.now(timezone.utc).replace(tzinfo=None)
def ident(prefix): return f"{prefix}_{uuid4().hex}"
def serialize(row):
    return {c.name: (getattr(row, c.name).isoformat() if isinstance(getattr(row, c.name), datetime) else getattr(row, c.name)) for c in row.__table__.columns}
def parse_dt(value):
    if not value: return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed

class WorkEngine:
    def __init__(self, db: Session): self.db = db

    def _one(self, model, owner, ident_value, label):
        row = self.db.query(model).filter_by(id=ident_value, owner=owner).one_or_none()
        if row is None: raise WorkError(f"{label} not found")
        return row

    def event(self, owner, event_type, *, goal_id=None, project_id=None, task_id=None, run_id=None, action_id=None, payload=None):
        row = WorkEvent(id=ident("event"), owner=owner, event_type=event_type, goal_id=goal_id, project_id=project_id, task_id=task_id, run_id=run_id, action_id=action_id, payload=payload or {})
        self.db.add(row); return row

    def create_goal(self, owner, data):
        title = str(data.get("title") or "").strip()
        if not title: raise WorkError("goal title is required")
        row = WorkGoal(id=ident("goal"), owner=owner, title=title[:300], description=str(data.get("description") or "")[:20000], priority=int(data.get("priority") or 0), desired_outcome=str(data.get("desired_outcome") or "")[:20000], success_criteria=data.get("success_criteria") or {}, constraints=data.get("constraints") or {}, deadline=parse_dt(data.get("deadline")), source=str(data.get("source") or "operator")[:64])
        self.db.add(row); self.event(owner, "goal.created", goal_id=row.id, payload={"title": row.title}); self.db.commit(); self.db.refresh(row); return serialize(row)

    def update_goal(self, owner, goal_id, data):
        row = self._one(WorkGoal, owner, goal_id, "goal")
        if "status" in data and data["status"] not in GOAL_STATUSES: raise WorkError("invalid goal status")
        for key in ("title", "description", "desired_outcome", "source"):
            if key in data: setattr(row, key, str(data[key])[:20000])
        for key in ("priority", "success_criteria", "constraints", "deadline"):
            if key in data: setattr(row, key, parse_dt(data[key]) if key == "deadline" else data[key])
        if "status" in data:
            row.status = data["status"]; row.completed_at = now() if row.status == "completed" else None; row.revision += 1
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def create_project(self, owner, data):
        goal_id = data.get("goal_id")
        if goal_id: self._one(WorkGoal, owner, goal_id, "goal")
        title = str(data.get("title") or "").strip()
        if not title: raise WorkError("project title is required")
        row = WorkProject(id=ident("project"), owner=owner, goal_id=goal_id, title=title[:300], description=str(data.get("description") or "")[:20000], priority=int(data.get("priority") or 0), started_at=parse_dt(data.get("started_at")), target_date=parse_dt(data.get("target_date")), external_reference=str(data.get("external_reference") or "")[:500] or None, domain=str(data.get("domain") or "general")[:64])
        self.db.add(row); self.event(owner, "project.started" if row.started_at else "project.created", goal_id=goal_id, project_id=row.id, payload={"title": row.title}); self.db.commit(); self.db.refresh(row); return serialize(row)

    def create_task(self, owner, data):
        project = self._one(WorkProject, owner, str(data.get("project_id") or ""), "project")
        parent_id = data.get("parent_task_id")
        if parent_id:
            parent = self._one(WorkTask, owner, parent_id, "parent task")
            if parent.project_id != project.id: raise WorkError("parent task must belong to project")
        title = str(data.get("title") or "").strip()
        if not title: raise WorkError("task title is required")
        row = WorkTask(id=ident("task"), project_id=project.id, parent_task_id=parent_id, owner=owner, title=title[:300], description=str(data.get("description") or "")[:20000], status=str(data.get("status") or "pending"), priority=int(data.get("priority") or 0), assignee_type=str(data.get("assignee_type") or "operator")[:32], assignee_ref=data.get("assignee_ref"), success_criteria=data.get("success_criteria") or {}, due_at=parse_dt(data.get("due_at")))
        if row.status not in TASK_STATUSES: raise WorkError("invalid task status")
        self.db.add(row); self.event(owner, "task.ready" if row.status == "ready" else "task.created", project_id=project.id, task_id=row.id, payload={"title": row.title}); self.db.commit(); self.db.refresh(row); return serialize(row)

    def add_dependency(self, owner, task_id, depends_on_id):
        task = self._one(WorkTask, owner, task_id, "task"); dependency = self._one(WorkTask, owner, depends_on_id, "dependency task")
        if task.id == dependency.id: raise WorkError("task cannot depend on itself")
        if task.project_id != dependency.project_id: raise WorkError("task dependencies must share a project")
        # Adding A -> B is invalid if B already reaches A.
        seen = set()
        def reaches(current):
            if current in seen: return False
            seen.add(current)
            for dep in self.db.query(WorkTaskDependency).filter_by(owner=owner, task_id=current).all():
                if dep.depends_on_task_id == task.id or reaches(dep.depends_on_task_id): return True
            return False
        if reaches(dependency.id): raise WorkError("task dependency would create a cycle")
        row = WorkTaskDependency(owner=owner, task_id=task.id, depends_on_task_id=dependency.id); self.db.add(row); self.db.commit(); return {"task_id": task.id, "depends_on_task_id": dependency.id}

    def create_run(self, owner, data):
        for model, key, label in ((WorkGoal, "goal_id", "goal"), (WorkProject, "project_id", "project"), (WorkTask, "task_id", "task")):
            if data.get(key): self._one(model, owner, data[key], label)
        row = WorkRun(id=ident("run"), owner=owner, goal_id=data.get("goal_id"), project_id=data.get("project_id"), task_id=data.get("task_id"), session_id=data.get("session_id"), domain=str(data.get("domain") or "general")[:64], requested_by=str(data.get("requested_by") or owner)[:200], model_endpoint=data.get("model_endpoint"), model_name=data.get("model_name"), continuation_state=data.get("continuation_state") or {})
        self.db.add(row); self.event(owner, "run.started", goal_id=row.goal_id, project_id=row.project_id, task_id=row.task_id, run_id=row.id, payload={"domain": row.domain}); self.db.commit(); self.db.refresh(row); return serialize(row)

    def create_action(self, owner, run_id, data):
        run = self._one(WorkRun, owner, run_id, "run")
        sequence = int(data.get("sequence") or (self.db.query(WorkAction).filter_by(run_id=run.id).count() + 1))
        digest = data.get("sealed_input_digest")
        if not digest and data.get("normalized_input") is not None: digest = sha256(str(data["normalized_input"]).encode()).hexdigest()
        row = WorkAction(id=ident("action"), run_id=run.id, sequence=sequence, capability_id=str(data.get("capability_id") or "").strip(), action_id=str(data.get("action_id") or "").strip(), tool_binding_name=data.get("tool_binding_name"), effect_class=str(data.get("effect_class") or "internal"), sealed_input_digest=digest, normalized_input=data.get("normalized_input") or {}, status=str(data.get("status") or "proposed"), approval_reference=data.get("approval_reference"))
        if not row.capability_id or not row.action_id: raise WorkError("capability_id and action_id are required")
        if row.status not in ACTION_STATUSES: raise WorkError("invalid action status")
        self.db.add(row)
        if row.status == "awaiting_approval":
            run.status = "awaiting_approval"; run.current_step = f"approval required: {row.action_id}"; run.revision += 1
        self.event(owner, "approval.requested" if row.status == "awaiting_approval" else "action.proposed", run_id=run.id, action_id=row.id, payload={"capability_id": row.capability_id, "action_id": row.action_id}); self.db.commit(); self.db.refresh(row); return serialize(row)

    def bind_approval(self, owner, action_id, approval_reference, *, digest=None):
        row = self.db.query(WorkAction).join(WorkRun).filter(WorkAction.id == action_id, WorkRun.owner == owner).one_or_none()
        if row is None: raise WorkError("action not found")
        reference = str(approval_reference or "").strip()
        if not reference: raise WorkError("approval reference is required")
        if digest and row.sealed_input_digest and str(digest) != row.sealed_input_digest: raise WorkError("approval digest does not match the persisted action")
        if row.status == "completed": raise WorkError("completed action cannot await approval")
        row.approval_reference = reference[:300]; row.status = "awaiting_approval"; row.revision += 1
        run = self.db.query(WorkRun).filter_by(id=row.run_id, owner=owner).one()
        run.status = "awaiting_approval"; run.current_step = f"approval required: {row.action_id}"; run.revision += 1
        self.event(owner, "approval.requested", run_id=run.id, action_id=row.id, payload={"approval_reference": row.approval_reference})
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def resume_approved_action(self, owner, action_id, approval_reference, *, digest=None):
        row = self.db.query(WorkAction).join(WorkRun).filter(WorkAction.id == action_id, WorkRun.owner == owner).one_or_none()
        if row is None: raise WorkError("action not found")
        if row.status == "completed": return serialize(row) | {"replayed": True}
        if row.status != "awaiting_approval" or row.approval_reference != str(approval_reference or ""): raise WorkError("approval is not bound to this awaiting action")
        if digest and row.sealed_input_digest and str(digest) != row.sealed_input_digest: raise WorkError("approval digest does not match the persisted action")
        row.status = "approved"; row.revision += 1
        self.event(owner, "approval.resumed", run_id=row.run_id, action_id=row.id, payload={"approval_reference": row.approval_reference})
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def complete_action(self, owner, action_id, data):
        row = self.db.query(WorkAction).join(WorkRun, WorkRun.id == WorkAction.run_id).filter(WorkAction.id == action_id, WorkRun.owner == owner).one_or_none()
        if row is None: raise WorkError("action not found")
        if row.status == "completed": return serialize(row) | {"replayed": True}
        if row.status not in {"proposed", "approved", "executing"}: raise WorkError("action is not completable")
        row.status = "completed"; row.completed_at = now(); row.result_reference = str(data.get("result_reference") or "")[:1000] or None; row.revision += 1
        self.event(owner, "action.completed", run_id=row.run_id, action_id=row.id, payload={"result_reference": row.result_reference}); self.db.commit(); self.db.refresh(row); return serialize(row)

    def set_run_status(self, owner, run_id, status, data=None):
        row = self._one(WorkRun, owner, run_id, "run")
        if status not in RUN_STATUSES: raise WorkError("invalid run status")
        if data and "model_name" in data: row.model_name = str(data["model_name"] or "")[:200] or None
        if data and "model_endpoint" in data: row.model_endpoint = str(data["model_endpoint"] or "")[:500] or None
        if data and "session_id" in data: row.session_id = str(data["session_id"] or "")[:200] or None
        row.status = status; row.current_step = (data or {}).get("current_step", row.current_step); row.error_summary = (data or {}).get("error_summary", row.error_summary); row.result_summary = (data or {}).get("result_summary", row.result_summary); row.continuation_state = (data or {}).get("continuation_state", row.continuation_state); row.ended_at = now() if status in {"completed", "failed", "cancelled"} else None; row.revision += 1
        self.event(owner, f"run.{status}", goal_id=row.goal_id, project_id=row.project_id, task_id=row.task_id, run_id=row.id, payload={"current_step": row.current_step}); self.db.commit(); self.db.refresh(row); return serialize(row)

    def create_commitment(self, owner, data):
        row = WorkCommitment(id=ident("commitment"), owner=owner, goal_id=data.get("goal_id"), project_id=data.get("project_id"), task_id=data.get("task_id"), run_id=data.get("run_id"), text=str(data.get("text") or "").strip()[:20000], due_at=parse_dt(data.get("due_at")), source=str(data.get("source") or "operator")[:64])
        if not row.text: raise WorkError("commitment text is required")
        self.db.add(row); self.db.commit(); self.db.refresh(row); return serialize(row)

    def add_result(self, owner, run_id, data):
        run = self._one(WorkRun, owner, run_id, "run")
        row = WorkResult(id=ident("result"), owner=owner, run_id=run.id, action_id=data.get("action_id"), result_type=str(data.get("result_type") or "reference")[:64], reference=str(data.get("reference") or "").strip()[:1000], domain_reference=data.get("domain_reference"), content_digest=data.get("content_digest"), metadata_json=data.get("metadata") or {}, provenance=data.get("provenance") or {})
        if not row.reference: raise WorkError("result reference is required")
        self.db.add(row); self.db.commit(); self.db.refresh(row); return serialize(row)

    def context(self, owner, *, goal_id=None, project_id=None, task_id=None, run_id=None):
        goal = self._one(WorkGoal, owner, goal_id, "goal") if goal_id else self.db.query(WorkGoal).filter_by(owner=owner, status="active").order_by(WorkGoal.updated_at.desc()).first()
        run = self._one(WorkRun, owner, run_id, "run") if run_id else self.db.query(WorkRun).filter_by(owner=owner).filter(WorkRun.status.in_(["running", "awaiting_approval", "awaiting_input", "suspended"])).order_by(WorkRun.updated_at.desc()).first()
        task = self._one(WorkTask, owner, task_id, "task") if task_id else (self._one(WorkTask, owner, run.task_id, "task") if run and run.task_id else None)
        project = self._one(WorkProject, owner, project_id, "project") if project_id else (self._one(WorkProject, owner, run.project_id, "project") if run and run.project_id else None)
        events = self.db.query(WorkEvent).filter_by(owner=owner).order_by(WorkEvent.created_at.desc()).limit(12).all()
        commitments = self.db.query(WorkCommitment).filter_by(owner=owner, status="open").order_by(WorkCommitment.due_at.asc()).limit(20).all()
        actions = self.db.query(WorkAction).join(WorkRun).filter(WorkRun.owner == owner, WorkAction.run_id == run.id).order_by(WorkAction.sequence.asc()).all() if run else []
        return {"goal": serialize(goal) if goal else None, "project": serialize(project) if project else None, "task": serialize(task) if task else None, "run": serialize(run) if run else None, "actions": [serialize(x) for x in actions], "pending_approval": any(x.status == "awaiting_approval" for x in actions), "pending_input": bool(run and run.status == "awaiting_input"), "commitments": [serialize(x) for x in commitments], "recent_events": [serialize(x) for x in events]}

    def life_review(self, owner, *, horizon_hours=48):
        """Deterministic daily-review projection over canonical Work records."""
        current = now()
        horizon = current + __import__("datetime").timedelta(hours=max(1, min(int(horizon_hours), 336)))
        goals = self.db.query(WorkGoal).filter_by(owner=owner).filter(WorkGoal.status.in_(["active", "blocked", "paused"])).order_by(WorkGoal.priority.desc(), WorkGoal.updated_at.desc()).limit(50).all()
        tasks = self.db.query(WorkTask).filter_by(owner=owner).filter(WorkTask.status.in_(["pending", "ready", "running", "awaiting_input", "blocked"])).all()
        commitments = self.db.query(WorkCommitment).filter_by(owner=owner, status="open").all()
        runs = self.db.query(WorkRun).filter_by(owner=owner).filter(WorkRun.status.in_(["awaiting_approval", "awaiting_input", "blocked", "suspended", "running"])).all()
        due = [serialize(x) for x in commitments if x.due_at and x.due_at <= horizon]
        overdue = [serialize(x) for x in commitments if x.due_at and x.due_at < current]
        return {
            "generated_at": current.isoformat(),
            "horizon_hours": max(1, min(int(horizon_hours), 336)),
            "focus_goals": [serialize(x) for x in goals[:8]],
            "blocked_tasks": [serialize(x) for x in tasks if x.status == "blocked"],
            "due_soon_tasks": [serialize(x) for x in tasks if x.due_at and current <= x.due_at <= horizon],
            "due_soon_commitments": due,
            "overdue_commitments": overdue,
            "waiting_runs": [serialize(x) for x in runs],
        }

    def get_run(self, owner, run_id):
        run = self._one(WorkRun, owner, run_id, "run")
        return serialize(run) | {"actions": [serialize(x) for x in self.db.query(WorkAction).filter_by(run_id=run.id).order_by(WorkAction.sequence).all()], "results": [serialize(x) for x in self.db.query(WorkResult).filter_by(run_id=run.id).all()], "artifacts": [serialize(x) for x in self.db.query(WorkArtifact).filter_by(run_id=run.id).all()], "events": [serialize(x) for x in self.db.query(WorkEvent).filter_by(owner=owner, run_id=run.id).order_by(WorkEvent.created_at).all()]}

    def list_records(self, owner, model, status=None, domain=None):
        query = self.db.query(model).filter_by(owner=owner)
        if status and hasattr(model, "status"): query = query.filter_by(status=status)
        if domain and model is WorkRun: query = query.filter_by(domain=domain)
        return [serialize(x) for x in query.order_by(model.updated_at.desc() if hasattr(model, "updated_at") else model.created_at.desc()).limit(200).all()]
