"""Owner-scoped durable work engine and bounded domain adapters."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4
from sqlalchemy.orm import Session
from core.work_models import (EpistemicClaim, WorldRelationship, WorkAction, WorkArtifact, WorkCommitment, WorkEvent, WorkGoal, WorkLock, WorkProject, WorkResult, WorkRun, WorkTask, WorkTaskDependency)

GOAL_STATUSES = {"draft", "active", "blocked", "paused", "completed", "cancelled", "failed"}
PROJECT_STATUSES = {"planned", "active", "blocked", "paused", "completed", "cancelled"}
TASK_STATUSES = {"pending", "ready", "running", "awaiting_approval", "awaiting_input", "blocked", "completed", "failed", "cancelled"}
RUN_STATUSES = {"queued", "running", "awaiting_approval", "awaiting_input", "suspended", "completed", "failed", "cancelled"}
ACTION_STATUSES = {"proposed", "awaiting_approval", "approved", "executing", "completed", "failed", "rejected", "cancelled", "expired"}
LOCK_MODES = {"shared", "exclusive"}
CLAIM_CLASSES = {"Fact", "Observation", "Observed", "UserAssertion", "RetrievedClaim", "Inference", "Assumption", "Hypothesis", "HistoricalState", "CurrentState", "Imported", "Assumed", "Hypothesized", "Confirmed", "Stale", "Unknown"}
RUN_LIFECYCLE_STATES = {"created", "planning", "ready", "executing", "verifying", "succeeded", "waiting_approval", "waiting_input", "paused", "failed", "cancelled", "compensating"}
_STATUS_TO_LIFECYCLE = {"queued": "ready", "running": "executing", "awaiting_approval": "waiting_approval", "awaiting_input": "waiting_input", "suspended": "paused", "completed": "succeeded", "failed": "failed", "cancelled": "cancelled"}

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
        row = WorkRun(id=ident("run"), owner=owner, goal_id=data.get("goal_id"), project_id=data.get("project_id"), task_id=data.get("task_id"), session_id=data.get("session_id"), domain=str(data.get("domain") or "general")[:64], requested_by=str(data.get("requested_by") or owner)[:200], model_endpoint=data.get("model_endpoint"), model_name=data.get("model_name"), lifecycle_state=str(data.get("lifecycle_state") or "created"), intent=data.get("intent") or {}, plan=data.get("plan") or [], assumptions=data.get("assumptions") or [], costs=data.get("costs") or {}, checkpoints=data.get("checkpoints") or [], verification=data.get("verification") or {}, continuation_state=data.get("continuation_state") or {})
        if row.lifecycle_state not in RUN_LIFECYCLE_STATES: raise WorkError("invalid run lifecycle state")
        self.db.add(row); self.event(owner, "run.started", goal_id=row.goal_id, project_id=row.project_id, task_id=row.task_id, run_id=row.id, payload={"domain": row.domain}); self.db.commit(); self.db.refresh(row); return serialize(row)

    def create_action(self, owner, run_id, data):
        run = self._one(WorkRun, owner, run_id, "run")
        sequence = int(data.get("sequence") or (self.db.query(WorkAction).filter_by(run_id=run.id).count() + 1))
        digest = data.get("sealed_input_digest")
        if not digest and data.get("normalized_input") is not None: digest = sha256(str(data["normalized_input"]).encode()).hexdigest()
        row = WorkAction(id=ident("action"), run_id=run.id, sequence=sequence, capability_id=str(data.get("capability_id") or "").strip(), action_id=str(data.get("action_id") or "").strip(), tool_binding_name=data.get("tool_binding_name"), effect_class=str(data.get("effect_class") or "internal"), sealed_input_digest=digest, normalized_input=data.get("normalized_input") or {}, target_resources=data.get("target_resources") or [], preconditions=data.get("preconditions") or [], locks=data.get("locks") or [], risk_level=str(data.get("risk_level") or "low")[:32], idempotency_key=data.get("idempotency_key"), retry_policy=data.get("retry_policy") or {}, timeout_seconds=data.get("timeout_seconds"), rollback_capability=data.get("rollback_capability"), compensating_action=data.get("compensating_action"), postconditions=data.get("postconditions") or [], verification=data.get("verification") or [], status=str(data.get("status") or "proposed"), approval_reference=data.get("approval_reference"))
        if not row.capability_id or not row.action_id: raise WorkError("capability_id and action_id are required")
        if row.status not in ACTION_STATUSES: raise WorkError("invalid action status")
        self.db.add(row)
        if row.status == "awaiting_approval":
            run.status = "awaiting_approval"; run.current_step = f"approval required: {row.action_id}"; run.revision += 1
        self.event(owner, "approval.requested" if row.status == "awaiting_approval" else "action.proposed", run_id=run.id, action_id=row.id, payload={"capability_id": row.capability_id, "action_id": row.action_id}); self.db.commit(); self.db.refresh(row); return serialize(row)

    def preview_action(self, owner, run_id, data):
        """Compile an action contract without persisting or executing it."""
        self._one(WorkRun, owner, run_id, "run")
        required = ("capability_id", "action_id")
        if any(not str(data.get(key) or "").strip() for key in required):
            raise WorkError("capability_id and action_id are required")
        return {
            "run_id": run_id,
            "capability_id": str(data["capability_id"]).strip(),
            "action_id": str(data["action_id"]).strip(),
            "target_resources": list(data.get("target_resources") or []),
            "preconditions": list(data.get("preconditions") or []),
            "locks": list(data.get("locks") or []),
            "risk_level": str(data.get("risk_level") or "low"),
            "approval_required": bool(data.get("approval_required", False)),
            "expected_cost": data.get("expected_cost") or {},
            "rollback_capability": str(data.get("rollback_capability") or "none"),
            "postconditions": list(data.get("postconditions") or []),
            "verification": list(data.get("verification") or []),
            "execution": "preview_only",
        }

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
        self._release_action_locks(owner, row.id)
        self.event(owner, "action.completed", run_id=row.run_id, action_id=row.id, payload={"result_reference": row.result_reference}); self.db.commit(); self.db.refresh(row); return serialize(row)

    @staticmethod
    def _lock_requests(value):
        requests = []
        for item in value or []:
            if isinstance(item, str):
                resource, mode = item.strip(), "exclusive"
            elif isinstance(item, dict):
                resource, mode = str(item.get("resource") or "").strip(), str(item.get("mode") or "exclusive").strip().lower()
            else:
                raise WorkError("lock entries must be strings or objects")
            if not resource: raise WorkError("lock resource is required")
            if mode not in LOCK_MODES: raise WorkError("invalid lock mode")
            requests.append((resource[:500], mode))
        if len({resource for resource, _ in requests}) != len(requests):
            raise WorkError("duplicate lock resource")
        return sorted(requests)

    def lock_conflicts(self, owner, action_id):
        action = self.db.query(WorkAction).join(WorkRun).filter(WorkAction.id == action_id, WorkRun.owner == owner).one_or_none()
        if action is None: raise WorkError("action not found")
        conflicts = []
        for resource, mode in self._lock_requests(action.locks):
            active = self.db.query(WorkLock).filter_by(owner=owner, resource=resource, released_at=None).all()
            for lock in active:
                if lock.action_id == action.id: continue
                if mode == "exclusive" or lock.mode == "exclusive": conflicts.append(serialize(lock))
        return conflicts

    def acquire_action_locks(self, owner, action_id):
        action = self.db.query(WorkAction).join(WorkRun).filter(WorkAction.id == action_id, WorkRun.owner == owner).one_or_none()
        if action is None: raise WorkError("action not found")
        if action.status not in {"proposed", "approved", "executing"}: raise WorkError("action cannot acquire locks in its current state")
        conflicts = self.lock_conflicts(owner, action_id)
        if conflicts: raise WorkError(f"resource lock conflict: {conflicts[0]['resource']}")
        existing = {lock.resource for lock in self.db.query(WorkLock).filter_by(owner=owner, action_id=action.id, released_at=None).all()}
        requests = self._lock_requests(action.locks)
        for resource, mode in requests:
            if resource not in existing:
                self.db.add(WorkLock(id=ident("lock"), owner=owner, resource=resource, mode=mode, run_id=action.run_id, action_id=action.id))
        action.status = "executing"; action.started_at = action.started_at or now(); action.revision += 1
        self.event(owner, "action.locks_acquired", run_id=action.run_id, action_id=action.id, payload={"locks": [resource for resource, _ in requests]})
        self.db.commit(); self.db.refresh(action); return serialize(action)

    def _release_action_locks(self, owner, action_id):
        locks = self.db.query(WorkLock).filter_by(owner=owner, action_id=action_id, released_at=None).all()
        for lock in locks: lock.released_at = now()

    def release_action_locks(self, owner, action_id):
        action = self.db.query(WorkAction).join(WorkRun).filter(WorkAction.id == action_id, WorkRun.owner == owner).one_or_none()
        if action is None: raise WorkError("action not found")
        self._release_action_locks(owner, action_id)
        self.event(owner, "action.locks_released", run_id=action.run_id, action_id=action.id, payload={})
        self.db.commit()
        return {"action_id": action_id, "released": True}

    def release_run_locks(self, owner, run_id):
        self._one(WorkRun, owner, run_id, "run")
        locks = self.db.query(WorkLock).filter_by(owner=owner, run_id=run_id, released_at=None).all()
        for lock in locks: lock.released_at = now()
        if locks: self.db.commit()
        return {"run_id": run_id, "released": len(locks)}

    def recover_locks(self, owner, *, max_age_seconds=3600):
        """Release locks held by terminal/unknown Runs or beyond their lease."""
        cutoff = now() - timedelta(seconds=max(0, int(max_age_seconds)))
        active = self.db.query(WorkLock).filter_by(owner=owner, released_at=None).all()
        released = []
        for lock in active:
            run = self.db.query(WorkRun).filter_by(id=lock.run_id, owner=owner).one_or_none()
            if run is None or run.status in {"completed", "failed", "cancelled"} or (lock.acquired_at and lock.acquired_at < cutoff):
                lock.released_at = now(); released.append(lock.id)
        if released: self.db.commit()
        return {"released": released, "count": len(released)}

    def set_run_status(self, owner, run_id, status, data=None):
        row = self._one(WorkRun, owner, run_id, "run")
        if status not in RUN_STATUSES: raise WorkError("invalid run status")
        if data and "model_name" in data: row.model_name = str(data["model_name"] or "")[:200] or None
        if data and "model_endpoint" in data: row.model_endpoint = str(data["model_endpoint"] or "")[:500] or None
        if data and "session_id" in data: row.session_id = str(data["session_id"] or "")[:200] or None
        row.status = status; row.lifecycle_state = (data or {}).get("lifecycle_state", _STATUS_TO_LIFECYCLE.get(status, row.lifecycle_state or "created")); row.current_step = (data or {}).get("current_step", row.current_step); row.error_summary = (data or {}).get("error_summary", row.error_summary); row.result_summary = (data or {}).get("result_summary", row.result_summary); row.continuation_state = (data or {}).get("continuation_state", row.continuation_state); row.verification = (data or {}).get("verification", row.verification); row.ended_at = now() if status in {"completed", "failed", "cancelled"} else None; row.revision += 1
        if row.lifecycle_state not in RUN_LIFECYCLE_STATES: raise WorkError("invalid run lifecycle state")
        if status in {"completed", "failed", "cancelled"}:
            for lock in self.db.query(WorkLock).filter_by(owner=owner, run_id=run_id, released_at=None).all(): lock.released_at = now()
        self.event(owner, f"run.{status}", goal_id=row.goal_id, project_id=row.project_id, task_id=row.task_id, run_id=row.id, payload={"current_step": row.current_step}); self.db.commit(); self.db.refresh(row); return serialize(row)

    def transition_run(self, owner, run_id, lifecycle_state, data=None):
        """Advance the durable lifecycle while retaining legacy status values."""
        if lifecycle_state not in RUN_LIFECYCLE_STATES:
            raise WorkError("invalid run lifecycle state")
        row = self._one(WorkRun, owner, run_id, "run")
        payload = data or {}
        row.lifecycle_state = lifecycle_state
        if "plan" in payload: row.plan = payload["plan"]
        if "assumptions" in payload: row.assumptions = payload["assumptions"]
        if "checkpoints" in payload: row.checkpoints = payload["checkpoints"]
        if "costs" in payload: row.costs = payload["costs"]
        if "verification" in payload: row.verification = payload["verification"]
        if "current_step" in payload: row.current_step = str(payload["current_step"] or "")[:300] or None
        row.revision += 1
        self.event(owner, f"Run{''.join(part.title() for part in lifecycle_state.split('_'))}", goal_id=row.goal_id, project_id=row.project_id, task_id=row.task_id, run_id=row.id, payload={"lifecycle_state": lifecycle_state, "current_step": row.current_step})
        self.db.commit(); self.db.refresh(row)
        return serialize(row)

    def checkpoint_run(self, owner, run_id, checkpoint):
        row = self._one(WorkRun, owner, run_id, "run")
        entries = list(row.checkpoints or [])
        entry = dict(checkpoint or {})
        entry.setdefault("created_at", now().isoformat())
        entry.setdefault("lifecycle_state", row.lifecycle_state)
        entries.append(entry)
        row.checkpoints = entries[-100:]
        row.revision += 1
        self.event(owner, "CheckpointCreated", goal_id=row.goal_id, project_id=row.project_id, task_id=row.task_id, run_id=row.id, payload=entry)
        self.db.commit(); self.db.refresh(row)
        return entry

    def record_verification(self, owner, run_id, verification):
        row = self._one(WorkRun, owner, run_id, "run")
        row.verification = dict(verification or {})
        row.revision += 1
        self.event(owner, "VerificationRecorded", goal_id=row.goal_id, project_id=row.project_id, task_id=row.task_id, run_id=row.id, payload=row.verification)
        self.db.commit(); self.db.refresh(row)
        return serialize(row)

    def complete_verification(self, owner, run_id, *, success, details=None, compensation_reference=None):
        """Commit a verification decision without allowing prose to waive it.

        A failed postcondition either enters explicit compensation or ends in a
        distinct verification-failed outcome.  The external binding remains
        responsible for performing the verifier/compensator itself.
        """
        row = self._one(WorkRun, owner, run_id, "run")
        if row.lifecycle_state != "verifying": raise WorkError("run is not awaiting verification")
        verification = dict(details or {}); verification.update({"success": bool(success), "recorded_at": now().isoformat()})
        row.verification = verification
        state = dict(row.continuation_state or {})
        if success:
            outcome = "compensated_restored" if state.get("compensation_attempted") else "execution_succeeded_verified"
            row.result_summary = {**(row.result_summary or {}), "outcome": outcome, "verification": verification}
            self.db.commit()
            return self.verified_execution_step(owner, run_id, "succeeded", reason=outcome)
        if compensation_reference:
            state.update({"compensation_attempted": True, "compensation_reference": str(compensation_reference)[:500]})
            row.continuation_state = state
            row.result_summary = {**(row.result_summary or {}), "outcome": "execution_succeeded_verification_failed", "verification": verification}
            self.db.commit()
            return self.verified_execution_step(owner, run_id, "compensating", reason="verification failed; compensation required", failure_class="verification_failed")
        row.result_summary = {**(row.result_summary or {}), "outcome": "execution_succeeded_verification_failed", "verification": verification}
        self.db.commit()
        return self.verified_execution_step(owner, run_id, "failed", reason="verification failed", failure_class="verification_failed")

    def complete_compensation(self, owner, run_id, *, success, details=None):
        """Record compensation and require restoration verification when it succeeds."""
        row = self._one(WorkRun, owner, run_id, "run")
        if row.lifecycle_state != "compensating": raise WorkError("run is not compensating")
        compensation = dict(details or {}); compensation.update({"success": bool(success), "recorded_at": now().isoformat()})
        state = {**(row.continuation_state or {}), "compensation_result": compensation}
        row.continuation_state = state
        if success:
            row.result_summary = {**(row.result_summary or {}), "outcome": "compensation_completed", "compensation": compensation}
            self.db.commit()
            return self.verified_execution_step(owner, run_id, "verifying", reason="compensation completed; restoration verification required")
        row.result_summary = {**(row.result_summary or {}), "outcome": "compensation_failed", "compensation": compensation}
        self.db.commit()
        return self.verified_execution_step(owner, run_id, "failed", reason="compensation failed", failure_class="compensation_failed")

    def verified_execution_step(self, owner, run_id, lifecycle_state, *, reason=None, failure_class=None):
        """Persist a named verified-execution phase using the Work Run."""
        allowed = {
            "created": {"planning", "cancelled"}, "planning": {"ready", "failed", "cancelled"},
            "ready": {"executing", "waiting_approval", "failed", "cancelled"},
            "waiting_approval": {"ready", "cancelled", "failed"},
            "executing": {"verifying", "failed", "cancelled", "compensating"},
            "verifying": {"succeeded", "failed", "compensating", "cancelled"},
            "compensating": {"verifying", "failed", "cancelled"},
            "paused": {"ready", "cancelled"}, "succeeded": set(), "failed": set(), "cancelled": set(),
        }
        row = self._one(WorkRun, owner, run_id, "run")
        current = row.lifecycle_state or "created"
        if lifecycle_state not in RUN_LIFECYCLE_STATES: raise WorkError("invalid run lifecycle state")
        if lifecycle_state == "executing":
            # Consequential execution must pass the canonical structured plan
            # validator before the durable lifecycle can advance.  Empty
            # diagnostic/projection Runs remain usable for lifecycle tests and
            # non-mutating orchestration; any Run carrying Actions/Plan is
            # fail-closed here, before a binding can execute it.
            actions = self.db.query(WorkAction).filter_by(run_id=run_id).count()
            if actions or (row.plan and isinstance(row.plan, list)):
                from src.run_planner import RunPlanner
                validation = RunPlanner(self.db).validate(owner, run_id)
                if not validation["valid"]:
                    codes = ", ".join(sorted({str(item.get("code") or "invalid_plan") for item in validation["failures"]}))
                    raise WorkError(f"plan validation failed before execution: {codes}")
        if lifecycle_state != current and lifecycle_state not in allowed.get(current, set()):
            raise WorkError(f"invalid execution transition: {current} -> {lifecycle_state}")
        row.lifecycle_state = lifecycle_state
        if lifecycle_state in {"failed", "cancelled"}: row.status = lifecycle_state
        elif lifecycle_state == "waiting_approval": row.status = "awaiting_approval"
        elif lifecycle_state == "paused": row.status = "suspended"
        elif lifecycle_state == "succeeded": row.status = "completed"
        elif lifecycle_state in {"executing", "verifying", "compensating"}: row.status = "running"
        elif lifecycle_state in {"planning", "ready"}: row.status = "queued"
        row.current_step = str(reason or lifecycle_state)[:300]
        if failure_class: row.error_summary = str(failure_class)[:500]
        row.ended_at = now() if lifecycle_state in {"succeeded", "failed", "cancelled"} else None
        row.revision += 1
        self.event(owner, "execution." + lifecycle_state, run_id=run_id, payload={"lifecycle_state": lifecycle_state, "reason": reason, "failure_class": failure_class})
        try:
            from src.observability import ObservabilityService
            ObservabilityService(self.db).record_span(owner, "execution." + lifecycle_state, run_id=run_id, attributes={"status": "error" if lifecycle_state == "failed" else "ok", "reason": reason or lifecycle_state, "failure_class": failure_class})
        except Exception:
            # Observability is diagnostic and must not block a valid Work step.
            pass
        if lifecycle_state in {"succeeded", "failed", "cancelled"}: self.release_run_locks(owner, run_id)
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def record_precheck(self, owner, run_id, precheck):
        row = self._one(WorkRun, owner, run_id, "run")
        entry = dict(precheck or {}); entry.setdefault("recorded_at", now().isoformat())
        checkpoints = list(row.checkpoints or []); checkpoints.append({"kind": "precheck", **entry}); row.checkpoints = checkpoints[-100:]
        self.event(owner, "execution.precheck", run_id=run_id, payload=entry)
        self.db.commit(); return entry

    def invalidate_state(self, owner, run_id, invalidations, *, reason="mutation completed"):
        """Mark targeted current claims stale while retaining historical evidence.

        Optional propagation is deliberately explicit in the invalidation
        entry. Only observed or owner-confirmed World Model edges with strong
        confidence propagate, and propagation is one hop per declared rule;
        proposed/inferred topology never silently invalidates unrelated state.
        """
        self._one(WorkRun, owner, run_id, "run")
        entries = [item for item in (invalidations or []) if isinstance(item, dict)]
        expanded = list(entries)
        for item in entries:
            propagation = item.get("propagate") or []
            if isinstance(propagation, dict): propagation = [propagation]
            for rule in propagation:
                if not isinstance(rule, dict): continue
                relation = str(rule.get("relation") or "").strip().upper()
                predicate = rule.get("predicate") or item.get("predicate")
                if not relation or not predicate: continue
                rows = self.db.query(WorldRelationship).filter_by(owner=owner, relation=relation, target_ref=item.get("subject_ref")).all()
                for row in rows:
                    if row.status not in {"observed", "user_confirmed"} or row.confidence_class not in {"high", "confirmed"}: continue
                    expanded.append({"subject_ref": row.source_ref, "predicate": predicate, "propagated_from": item.get("subject_ref"), "propagation_relation": relation})
        changed = []
        for claim in self.db.query(EpistemicClaim).filter_by(owner=owner, status="active").all():
            if any((item.get("subject_ref") in {None, claim.subject_ref} and item.get("predicate") in {None, claim.predicate}) for item in expanded):
                provenance = dict(claim.provenance or {}); provenance.update({"state": "stale", "invalidated_at": now().isoformat(), "invalidated_by_run": run_id, "invalidated_reason": reason}); claim.provenance = provenance; changed.append(claim.id)
        self.event(owner, "execution.state_invalidated", run_id=run_id, payload={"claims": changed, "invalidations": expanded, "reason": reason})
        self.db.commit(); return {"run_id": run_id, "stale_claims": changed, "invalidations": expanded}

    def request_cancel(self, owner, run_id, *, reason="operator requested cancellation"):
        row = self._one(WorkRun, owner, run_id, "run")
        if row.lifecycle_state in {"succeeded", "failed", "cancelled"}: return serialize(row)
        row.continuation_state = {**(row.continuation_state or {}), "cancellation_requested": True}
        row.current_step = "cancellation requested"; row.revision += 1
        self.event(owner, "execution.cancellation_requested", run_id=run_id, payload={"reason": reason})
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def reconstruct_run(self, owner, run_id):
        """Replay the durable journal into an inspectable lifecycle projection.

        This is deliberately read-only. The ORM row remains the fast current
        projection; WorkEvents are the audit/journal source for reconstruction.
        """
        row = self._one(WorkRun, owner, run_id, "run")
        events = self.db.query(WorkEvent).filter_by(owner=owner, run_id=run_id).order_by(WorkEvent.created_at, WorkEvent.id).all()
        transitions = []
        action_events = []
        lifecycle = "created"
        for event in events:
            payload = event.payload or {}
            state = payload.get("lifecycle_state") if isinstance(payload, dict) and (event.event_type.startswith("Run") or event.event_type.startswith("run.")) else None
            if not state and event.event_type.startswith("execution."):
                state = event.event_type.split(".", 1)[1]
            if not state and event.event_type.startswith("run."):
                state = _STATUS_TO_LIFECYCLE.get(event.event_type[4:])
            if not state and event.event_type.startswith("Run"):
                candidate = event.event_type[3:]
                state = {"Planning": "planning", "Ready": "ready", "Executing": "executing", "Verifying": "verifying", "Succeeded": "succeeded", "WaitingApproval": "waiting_approval", "WaitingInput": "waiting_input", "Paused": "paused", "Failed": "failed", "Cancelled": "cancelled", "Compensating": "compensating"}.get(candidate)
            if state in RUN_LIFECYCLE_STATES:
                lifecycle = state
                transitions.append({"event": event.event_type, "state": state, "created_at": event.created_at.isoformat()})
            if event.action_id:
                action_events.append({"event": event.event_type, "action_id": event.action_id, "created_at": event.created_at.isoformat()})
        return {"run_id": row.id, "owner": owner, "lifecycle_state": lifecycle, "transitions": transitions, "action_events": action_events, "event_count": len(events), "current_projection": row.lifecycle_state or "created"}

    def action_loop_check(self, owner, run_id, *, threshold=2):
        from src.control_plane_safety import detect_action_loop
        self._one(WorkRun, owner, run_id, "run")
        actions = [serialize(row) for row in self.db.query(WorkAction).filter_by(run_id=run_id).order_by(WorkAction.sequence).all()]
        return detect_action_loop(actions, threshold=threshold)

    def knowledge_gaps(self, owner, required, *, at=None):
        from src.control_plane_safety import classify_knowledge_gaps
        claims = [serialize(row) for row in self.db.query(EpistemicClaim).filter_by(owner=owner).all()]
        return classify_knowledge_gaps(required, claims, at=at)

    def create_commitment(self, owner, data):
        row = WorkCommitment(id=ident("commitment"), owner=owner, goal_id=data.get("goal_id"), project_id=data.get("project_id"), task_id=data.get("task_id"), run_id=data.get("run_id"), text=str(data.get("text") or "").strip()[:20000], due_at=parse_dt(data.get("due_at")), source=str(data.get("source") or "operator")[:64])
        if not row.text: raise WorkError("commitment text is required")
        self.db.add(row); self.db.commit(); self.db.refresh(row); return serialize(row)

    def record_claim(self, owner, data):
        claim_class = str(data.get("claim_class") or "").strip()
        if claim_class not in CLAIM_CLASSES: raise WorkError("invalid epistemic claim class")
        predicate = str(data.get("predicate") or "").strip()
        source = str(data.get("source") or "").strip()
        if not predicate or not source: raise WorkError("claim predicate and source are required")
        confidence = max(0, min(100, int(data.get("confidence", 50))))
        run_id = data.get("run_id")
        if run_id: self._one(WorkRun, owner, run_id, "run")
        row = EpistemicClaim(id=ident("claim"), owner=owner, claim_class=claim_class, subject_ref=str(data.get("subject_ref") or "")[:500] or None, predicate=predicate[:300], value=data.get("value") if data.get("value") is not None else {}, source=source[:500], confidence=confidence, observed_at=parse_dt(data.get("observed_at")), valid_from=parse_dt(data.get("valid_from")), valid_until=parse_dt(data.get("valid_until")), expires_at=parse_dt(data.get("expires_at")), evidence_references=data.get("evidence_references") or [], contradicting_references=data.get("contradicting_references") or [], derived_from=data.get("derived_from") or [], run_id=run_id, provenance=data.get("provenance") or {})
        self.db.add(row)
        self.event(owner, "claim.recorded", run_id=run_id, payload={"claim_id": row.id, "claim_class": claim_class, "subject_ref": row.subject_ref, "predicate": row.predicate})
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def list_claims(self, owner, *, subject_ref=None, claim_class=None, include_inactive=False, limit=100):
        query = self.db.query(EpistemicClaim).filter_by(owner=owner)
        if subject_ref: query = query.filter_by(subject_ref=subject_ref)
        if claim_class: query = query.filter_by(claim_class=claim_class)
        if not include_inactive: query = query.filter(EpistemicClaim.status == "active")
        return [serialize(row) for row in query.order_by(EpistemicClaim.updated_at.desc()).limit(max(1, min(int(limit), 500))).all()]

    def claim_lineage(self, owner, claim_id):
        """Return an owner-scoped evidence/claim/conclusion projection.

        References are intentionally opaque IDs or source references. This
        exposes provenance and contradiction structure without exposing model
        chain-of-thought or silently resolving competing claims.
        """
        claim = self._one(EpistemicClaim, owner, claim_id, "claim")
        related_ids = set(claim.contradicting_references or [])
        related_ids.update(x for x in (claim.derived_from or []) if isinstance(x, str))
        related = []
        if related_ids:
            rows = self.db.query(EpistemicClaim).filter(EpistemicClaim.owner == owner, EpistemicClaim.id.in_(sorted(related_ids))).all()
            related = [serialize(row) for row in rows]
        provenance = dict(claim.provenance or {})
        return {
            "claim": serialize(claim),
            "evidence": list(claim.evidence_references or []),
            "contradictions": [row for row in related if row["id"] in set(claim.contradicting_references or [])],
            "derived_claims": [row for row in related if row["id"] in set(claim.derived_from or [])],
            "resolution_status": provenance.get("resolution_status", "unresolved"),
            "authority_unchanged": True,
        }

    def supersede_claim(self, owner, claim_id, replacement_id=None):
        row = self._one(EpistemicClaim, owner, claim_id, "claim")
        row.status = "superseded"
        row.updated_at = now()
        self.event(owner, "claim.superseded", run_id=row.run_id, payload={"claim_id": row.id, "replacement_id": replacement_id})
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def review_claim(self, owner, claim_id, *, decision, note="", replacement_claim_id=None):
        """Persist an explicit owner review without deleting epistemic history.

        This is intentionally a small canonical review primitive used by
        domain projections such as OSINT.  It never turns tainted report text
        into a claim and it cannot alter another owner's claim.  A correction
        is recorded in provenance/history; supersession or retraction changes
        only the current projection status while the original evidence stays
        queryable with ``include_inactive``.
        """
        decision = str(decision or "").strip().lower()
        allowed = {"confirmed", "stale", "retracted", "superseded", "unresolved"}
        if decision not in allowed:
            raise WorkError("invalid claim review decision")
        row = self._one(EpistemicClaim, owner, claim_id, "claim")
        replacement = None
        if replacement_claim_id:
            replacement = self._one(EpistemicClaim, owner, str(replacement_claim_id), "replacement claim")
            if replacement.id == row.id or replacement.subject_ref != row.subject_ref:
                raise WorkError("replacement claim must be a different claim in the same scope")
        if decision == "superseded" and replacement is None:
            raise WorkError("superseded review requires a replacement claim")
        if decision == "superseded":
            row.status = "superseded"
        elif decision == "retracted":
            row.status = "retracted"
        elif row.status in {"superseded", "retracted"} and decision in {"confirmed", "unresolved"}:
            row.status = "active"
        provenance = dict(row.provenance or {})
        history = list(provenance.get("review_history") or [])
        entry = {
            "decision": decision,
            "actor_class": "USER_CONFIRMATION" if decision == "confirmed" else "USER_CORRECTION",
            "recorded_at": now().isoformat(),
            "note": str(note or "")[:1000],
        }
        if replacement is not None:
            entry["replacement_claim_id"] = replacement.id
        history.append(entry)
        provenance["review_history"] = history[-25:]
        provenance["resolution_status"] = {"confirmed": "OWNER_CONFIRMED", "stale": "STALE", "retracted": "OWNER_CORRECTED", "superseded": "SUPERSEDED", "unresolved": "UNRESOLVED"}[decision]
        if decision == "stale":
            provenance["state"] = "stale"
        elif decision == "confirmed":
            provenance["state"] = "confirmed"
        elif decision in {"retracted", "superseded"}:
            provenance["state"] = "superseded" if decision == "superseded" else "retracted"
        row.provenance = provenance
        row.updated_at = now()
        self.event(owner, "claim.reviewed", run_id=row.run_id, payload={"claim_id": row.id, "decision": decision, "replacement_claim_id": replacement.id if replacement else None})
        self.db.commit(); self.db.refresh(row)
        return serialize(row)

    def epistemic_context(self, owner, *, subject_ref=None, at=None, limit=100):
        moment = parse_dt(at) if at else now()
        claims = self.list_claims(owner, subject_ref=subject_ref, include_inactive=False, limit=limit)
        current = []
        stale = []
        for claim in claims:
            until = parse_dt(claim.get("valid_until")) or parse_dt(claim.get("expires_at"))
            if until and until < moment or (claim.get("provenance") or {}).get("state") in {"stale", "unknown"}: stale.append(claim)
            elif claim.get("valid_from") and parse_dt(claim["valid_from"]) > moment: continue
            else: current.append(claim)
        return {"at": moment.isoformat(), "current": current, "stale": stale, "claim_count": len(current)}

    def record_contradiction(self, owner, claim_id, contradicting_claim_id, *, resolution=None):
        """Link competing claims without deleting either historical assertion."""
        claim = self._one(EpistemicClaim, owner, claim_id, "claim")
        other = self._one(EpistemicClaim, owner, contradicting_claim_id, "contradicting claim")
        refs = list(claim.contradicting_references or [])
        if other.id not in refs: refs.append(other.id)
        claim.contradicting_references = refs[-100:]
        provenance = dict(claim.provenance or {})
        provenance.update({"resolution_status": str(resolution or "unresolved")[:32], "contradiction_updated_at": now().isoformat()})
        claim.provenance = provenance
        other_refs = list(other.contradicting_references or [])
        if claim.id not in other_refs: other_refs.append(claim.id)
        other.contradicting_references = other_refs[-100:]
        other_provenance = dict(other.provenance or {})
        other_provenance.setdefault("resolution_status", str(resolution or "unresolved")[:32])
        other.provenance = other_provenance
        self.event(owner, "claim.contradiction_recorded", run_id=claim.run_id, payload={"claim_id": claim.id, "contradicting_claim_id": other.id, "resolution": resolution or "unresolved"})
        self.db.commit(); self.db.refresh(claim)
        return serialize(claim)

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
        return serialize(run) | {"actions": [serialize(x) for x in self.db.query(WorkAction).filter_by(run_id=run.id).order_by(WorkAction.sequence).all()], "results": [serialize(x) for x in self.db.query(WorkResult).filter_by(run_id=run.id).all()], "artifacts": [serialize(x) for x in self.db.query(WorkArtifact).filter_by(run_id=run.id).all()], "locks": [serialize(x) for x in self.db.query(WorkLock).filter_by(owner=owner, run_id=run.id).order_by(WorkLock.acquired_at).all()], "events": [serialize(x) for x in self.db.query(WorkEvent).filter_by(owner=owner, run_id=run.id).order_by(WorkEvent.created_at).all()]}

    def list_records(self, owner, model, status=None, domain=None):
        query = self.db.query(model).filter_by(owner=owner)
        if status and hasattr(model, "status"): query = query.filter_by(status=status)
        if domain and model is WorkRun: query = query.filter_by(domain=domain)
        return [serialize(x) for x in query.order_by(model.updated_at.desc() if hasattr(model, "updated_at") else model.created_at.desc()).limit(200).all()]
