"""Grounded persistent-agent projections and deterministic proactive checks."""
from __future__ import annotations

import os
import platform
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session
from core.persistent_agent_models import AssistantInstance, AssistantRuntimeSnapshot, Episode, Lesson, Monitor, Notification
from core.work_models import WorkCommitment, WorkEvent, WorkGoal, WorkProject, WorkRun, WorkTask
from src.capability_dependencies import capability_health, supported_capabilities
from src.work_engine import WorkEngine


def now() -> datetime:
    return datetime.utcnow()


def ident(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def row_dict(row):
    return {c.name: iso(getattr(row, c.name)) for c in row.__table__.columns}


def monitor_response_policy(consequence_tier: int) -> str:
    """Project bounded Monitor consequence semantics without granting authority."""
    return {0: "observe", 1: "notify", 2: "create_work", 3: "execute_pre_authorized_action"}.get(int(consequence_tier), "notify")


class PersistentAgent:
    def __init__(self, db: Session):
        self.db = db

    def instance(self, owner: str) -> AssistantInstance:
        row = self.db.query(AssistantInstance).filter_by(owner=owner).one_or_none()
        if row:
            return row
        row = AssistantInstance(
            id=ident("assistant"), owner=owner, canonical_name="Hades",
            installation_id=uuid4().hex, accepted_source=os.getenv("HADES_SOURCE_REFERENCE"),
            accepted_runtime=os.getenv("HADES_RUNTIME_REFERENCE"),
        )
        self.db.add(row); self.db.commit(); self.db.refresh(row)
        return row

    def runtime_snapshot(self, owner: str) -> dict:
        instance = self.instance(owner)
        recent = self.db.query(AssistantRuntimeSnapshot).filter_by(owner=owner).order_by(AssistantRuntimeSnapshot.observed_at.desc()).first()
        if recent and recent.observed_at and (now() - recent.observed_at).total_seconds() < 60:
            return row_dict(recent) | {"assistant_instance_id": instance.id, "installation_id": instance.installation_id}
        snapshot = AssistantRuntimeSnapshot(
            id=ident("runtime"), assistant_instance_id=instance.id, owner=owner,
            runtime_version=os.getenv("HADES_RUNTIME_VERSION") or platform.python_version(),
            source_reference=os.getenv("HADES_SOURCE_REFERENCE") or instance.accepted_source,
            image_reference=os.getenv("HADES_IMAGE_REFERENCE") or instance.accepted_runtime,
            model_profile=os.getenv("HADES_PRIMARY_MODEL_PROFILE", "hades-local-test"),
            local_model_health={"status": "configured", "profile": os.getenv("HADES_PRIMARY_MODEL_PROFILE", "hades-local-test")},
            routing_state={"default": "strong-default", "local_first_domains": ["household", "it_assets", "work", "homelab"]},
            database_health="healthy",
            broker_health={"status": "available_if_authorized", "authority": "existing_privileged_broker"},
            execution_environment={"runtime": "containerized_application", "host_operations": "first_class_capabilities", "host_os_family": "projected_only"},
        )
        self.db.add(snapshot); self.db.commit(); self.db.refresh(snapshot)
        return row_dict(snapshot) | {"assistant_instance_id": instance.id, "installation_id": instance.installation_id}

    def capability_health(self):
        result = []
        for name in supported_capabilities():
            health = capability_health(name)
            health["capability"] = name
            result.append(health)
        result.extend([
            {"capability": "local_inference", "status": "configured", "execution_profile": "host"},
            {"capability": "developer.workspace_shell", "status": "available_if_owner_lease", "execution_profile": "workspace_yolo"},
            {"capability": "security.target.resolve", "status": "available", "approval_required": True},
        ])
        return result

    def self_context(self, owner: str, *, since: datetime | None = None) -> dict:
        instance = self.instance(owner)
        goals = self.db.query(WorkGoal).filter(WorkGoal.owner == owner, WorkGoal.status.in_(["active", "blocked", "paused"])).order_by(WorkGoal.updated_at.desc()).limit(20).all()
        projects = self.db.query(WorkProject).filter(WorkProject.owner == owner, WorkProject.status.in_(["active", "blocked", "paused"])).order_by(WorkProject.updated_at.desc()).limit(20).all()
        tasks = self.db.query(WorkTask).filter(WorkTask.owner == owner, WorkTask.status.in_(["pending", "ready", "running", "awaiting_approval", "awaiting_input", "blocked"])).order_by(WorkTask.updated_at.desc()).limit(30).all()
        runs = self.db.query(WorkRun).filter(WorkRun.owner == owner, WorkRun.status.in_(["queued", "running", "awaiting_approval", "awaiting_input", "suspended"])).order_by(WorkRun.updated_at.desc()).limit(20).all()
        commitments = self.db.query(WorkCommitment).filter(WorkCommitment.owner == owner, WorkCommitment.status == "open").order_by(WorkCommitment.due_at.asc()).limit(20).all()
        events_q = self.db.query(WorkEvent).filter(WorkEvent.owner == owner)
        if since: events_q = events_q.filter(WorkEvent.created_at >= since)
        events = events_q.order_by(WorkEvent.created_at.desc()).limit(30).all()
        episodes = self.db.query(Episode).filter_by(owner=owner).order_by(Episode.ended_at.desc()).limit(10).all()
        notifications = self.db.query(Notification).filter_by(owner=owner, read_at=None).order_by(Notification.created_at.desc()).limit(20).all()
        return {
            "identity": {"canonical_name": instance.canonical_name, "assistant_instance_id": instance.id, "installation_id": instance.installation_id},
            "runtime": self.runtime_snapshot(owner),
            "work": {"goals": [row_dict(x) for x in goals], "projects": [row_dict(x) for x in projects], "tasks": [row_dict(x) for x in tasks], "runs": [row_dict(x) for x in runs], "pending_approval": any(x.status == "awaiting_approval" for x in runs), "awaiting_input": any(x.status == "awaiting_input" for x in runs)},
            "commitments": [row_dict(x) for x in commitments],
            "capabilities": self.capability_health(),
            "recent_activity": [row_dict(x) for x in events],
            "episodes": [row_dict(x) for x in episodes],
            "notifications": {"unread": len(notifications), "items": [row_dict(x) for x in notifications]},
        }

    def compact_self_context(self, owner: str) -> dict:
        """Token-budgeted projection for local/weak models.

        The allocation is explicit so capability descriptions cannot evict the
        active Work and recent evidence that establish continuity.
        """
        full = self.self_context(owner)
        return {
            "identity": full["identity"],
            "runtime": full["runtime"],
            "work": {"goals": full["work"]["goals"][:6], "projects": full["work"]["projects"][:6], "tasks": full["work"]["tasks"][:10], "runs": full["work"]["runs"][:8], "pending_approval": full["work"]["pending_approval"], "awaiting_input": full["work"]["awaiting_input"]},
            "commitments": full["commitments"][:8],
            "capabilities": full["capabilities"][:10],
            "recent_activity": full["recent_activity"][:12],
            "episodes": full["episodes"][:6],
            "notifications": {"unread": full["notifications"]["unread"], "items": full["notifications"]["items"][:8]},
            "context_budget": {"identity_runtime_tokens": 500, "work_tokens": 1800, "evidence_tokens": 1200, "capability_tokens": 700, "generation_reserve_tokens": 1024},
        }

    def create_episode(self, owner: str, *, title: str, summary: str, episode_type: str = "work", outcome: str = "observed", source_event_id: str | None = None, source_run_id: str | None = None, evidence_references=None, domain_references=None, significance=60) -> dict:
        if source_event_id:
            existing = self.db.query(Episode).filter_by(owner=owner, source_event_id=source_event_id).one_or_none()
            if existing: return row_dict(existing)
        row = Episode(id=ident("episode"), owner=owner, episode_type=episode_type, title=title[:300], summary=summary[:20000], outcome=outcome, source_event_id=source_event_id, source_run_id=source_run_id, evidence_references=evidence_references or [], domain_references=domain_references or [], significance=int(significance), provenance={"created_by": "hades_persistent_agent", "evidence_required": True})
        self.db.add(row); self.db.commit(); self.db.refresh(row)
        return row_dict(row)

    def episode_from_event(self, owner: str, event_id: str) -> dict:
        event = self.db.query(WorkEvent).filter_by(owner=owner, id=event_id).one_or_none()
        if event is None: raise ValueError("work event not found")
        payload = event.payload or {}
        title = str(payload.get("title") or event.event_type.replace(".", " ").title())
        summary = str(payload.get("summary") or payload.get("message") or f"{event.event_type} was recorded by the Work Engine.")
        return self.create_episode(owner, title=title, summary=summary, episode_type=event.event_type.split(".", 1)[0], outcome="completed" if event.event_type.endswith("completed") else "observed", source_event_id=event.id, source_run_id=event.run_id, evidence_references=[f"work-event:{event.id}"], domain_references=[x for x in (event.goal_id, event.project_id, event.task_id, event.run_id) if x], significance=70)

    def generate_episodes(self, owner: str, limit: int = 20) -> list[dict]:
        qualifying = ("run.completed", "run.failed", "action.completed", "approval.resumed", "commitment.missed", "goal.completed", "task.completed")
        existing = {x[0] for x in self.db.query(Episode.source_event_id).filter(Episode.owner == owner, Episode.source_event_id != None).all()}
        events = self.db.query(WorkEvent).filter(WorkEvent.owner == owner, WorkEvent.event_type.in_(qualifying)).order_by(WorkEvent.created_at.asc()).limit(limit).all()
        created=[]
        for event in events:
            if event.id not in existing:
                created.append(self.episode_from_event(owner, event.id))
        return created

    def propose_lesson(self, owner: str, statement: str, *, domain="general", evidence_episode_refs=None, confidence=50, scope_context=None) -> dict:
        row = Lesson(id=ident("lesson"), owner=owner, statement=statement[:20000], domain=domain[:64], confidence=max(0, min(100, int(confidence))), evidence_episode_refs=evidence_episode_refs or [], status="proposed", provenance={"created_by": "hades_persistent_agent", "requires_confirmation": True}, scope_context=scope_context or {})
        self.db.add(row); self.db.commit(); self.db.refresh(row); return row_dict(row)

    def notify(self, owner: str, *, title: str, body: str, notification_type: str, dedupe_key: str, severity="info", requires_action=False, source_domain=None, source_entity_id=None, source_event_id=None, source_run_id=None, monitor_id=None) -> dict:
        existing = self.db.query(Notification).filter_by(owner=owner, dedupe_key=dedupe_key).one_or_none()
        if existing: return row_dict(existing)
        row = Notification(id=ident("notification"), owner=owner, notification_type=notification_type, severity=severity, title=title[:300], body=body[:20000], dedupe_key=dedupe_key[:300], requires_action=requires_action, source_domain=source_domain, source_entity_id=source_entity_id, source_event_id=source_event_id, source_run_id=source_run_id, monitor_id=monitor_id, delivery_state="web_pending")
        self.db.add(row); self.db.commit(); self.db.refresh(row); return row_dict(row)

    def create_monitor(self, owner: str, data: dict) -> dict:
        tier = int(data.get("consequence_tier", 1))
        if tier not in {0, 1, 2, 3}: raise ValueError("consequence_tier must be 0..3")
        if tier >= 3 and not data.get("explicitly_allowed"): raise ValueError("tier 3 requires explicit allowance")
        row = Monitor(id=ident("monitor"), owner=owner, name=str(data.get("name") or "Monitor")[:200], condition_type=str(data.get("condition_type") or "").strip()[:64], source_domain=str(data.get("source_domain") or "system")[:64], query=data.get("query") or {}, condition=data.get("condition") or {}, consequence_tier=tier, notification_policy=data.get("notification_policy") or {}, cooldown_seconds=max(60, int(data.get("cooldown_seconds", 3600))))
        if not row.condition_type: raise ValueError("condition_type is required")
        self.db.add(row); self.db.commit(); self.db.refresh(row); return row_dict(row)

    def evaluate_monitors(self, owner: str) -> list[dict]:
        result=[]; current=now()
        for monitor in self.db.query(Monitor).filter_by(owner=owner, enabled=True).all():
            monitor.last_evaluated=current
            triggered=False; detail=""
            if monitor.condition_type == "commitment_overdue":
                overdue=self.db.query(WorkCommitment).filter(WorkCommitment.owner==owner, WorkCommitment.status=="open", WorkCommitment.due_at != None, WorkCommitment.due_at < current).count()
                triggered=overdue > 0; detail=f"{overdue} open commitment(s) overdue"
            elif monitor.condition_type == "unidentified_network_device":
                triggered=self.db.query(Episode).filter_by(owner=owner, episode_type="network_discovery").filter(Episode.created_at >= (monitor.last_triggered or datetime.min)).count() > 0; detail="new network discovery evidence is available"
            elif monitor.condition_type == "capability_unavailable":
                capability=str(monitor.condition.get("capability") or ""); health=next((x for x in self.capability_health() if x.get("capability")==capability), {}); triggered=health.get("status") in {"unavailable", "degraded"}; detail=f"{capability} status is {health.get('status')}"
            if triggered and (not monitor.last_triggered or (current-monitor.last_triggered).total_seconds() >= monitor.cooldown_seconds):
                monitor.last_triggered=current
                event = WorkEvent(id=ident("event"), owner=owner, event_type="monitor.triggered", payload={"monitor_id": monitor.id, "condition_type": monitor.condition_type, "detail": detail})
                self.db.add(event); self.db.commit()
                note=self.notify(owner, title=monitor.name, body=detail, notification_type="monitor_trigger", dedupe_key=f"monitor:{monitor.id}:{current.date()}", severity="warning", monitor_id=monitor.id, source_domain=monitor.source_domain, source_event_id=event.id)
                note["response_policy"] = monitor_response_policy(monitor.consequence_tier)
                note["authority_unchanged"] = True
                result.append(note)
            self.db.commit()
        return result

    def evaluate_commitments(self, owner: str) -> dict:
        current = now(); changed=[]; notes=[]
        rows = self.db.query(WorkCommitment).filter_by(owner=owner).filter(WorkCommitment.status == "open", WorkCommitment.due_at != None).all()
        for commitment in rows:
            if commitment.due_at < current:
                commitment.status = "missed"
                event = WorkEvent(id=ident("event"), owner=owner, event_type="commitment.missed", payload={"commitment_id": commitment.id, "text": commitment.text})
                self.db.add(event); self.db.commit(); changed.append(row_dict(commitment))
                notes.append(self.notify(owner, title="Commitment overdue", body=commitment.text, notification_type="commitment_overdue", dedupe_key=f"commitment-overdue:{commitment.id}", severity="warning", requires_action=True, source_domain="work", source_entity_id=commitment.id, source_event_id=event.id))
        return {"changed": changed, "notifications": notes}

    def digest(self, owner: str, since: datetime) -> dict:
        context=self.self_context(owner, since=since)
        return {"since": iso(since), "events": context["recent_activity"], "episodes": [x for x in context["episodes"] if x.get("created_at") and x["created_at"] >= iso(since)], "notifications": context["notifications"]}

    def attention(self, owner: str) -> dict:
        """Project actionable state without creating a second task system."""
        context = self.self_context(owner)
        items = []
        for notification in context["notifications"]["items"]:
            items.append({
                "kind": "notification",
                "priority": "high" if notification.get("requires_action") else notification.get("severity", "info"),
                "status": "unread",
                "id": notification.get("id"),
                "title": notification.get("title"),
                "body": notification.get("body"),
                "source_domain": notification.get("source_domain"),
                "source_entity_id": notification.get("source_entity_id"),
                "source_event_id": notification.get("source_event_id"),
                "source_run_id": notification.get("source_run_id"),
            })
        work = context["work"]
        for run in work["runs"]:
            state = run.get("status")
            if state in {"awaiting_approval", "awaiting_input", "blocked"}:
                items.append({"kind": "work", "priority": "high", "status": state, "id": run.get("id"), "title": run.get("current_step") or state.replace("_", " ").title()})
        for commitment in context["commitments"]:
            due = commitment.get("due_at")
            if due:
                items.append({"kind": "commitment", "priority": "high", "status": "due", "id": commitment.get("id"), "title": commitment.get("text"), "due_at": due})
        return {"items": items, "count": len(items), "generated_at": datetime.utcnow().isoformat() + "Z"}

    def operating_brief(self, owner: str, *, horizon_hours: int = 48, period: str = "day") -> dict:
        """Return a deterministic, source-grounded operating brief.

        This is a projection of existing Self and Work records.  It deliberately
        does not create tasks, notifications, memories, or model-generated
        claims while assembling the brief.
        """
        period = str(period or "day").lower()
        if period not in {"day", "week"}:
            raise ValueError("period must be day or week")
        horizon = 168 if period == "week" else max(1, min(int(horizon_hours), 336))
        context = self.self_context(owner)
        attention = self.attention(owner)
        review = WorkEngine(self.db).life_review(owner, horizon_hours=horizon)
        capabilities = context["capabilities"]
        capability_counts = {}
        for item in capabilities:
            state = str(item.get("status") or "unknown")
            capability_counts[state] = capability_counts.get(state, 0) + 1
        return {
            "period": period,
            "horizon_hours": horizon,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "identity": context["identity"],
            "runtime": context["runtime"],
            "work": {
                "active_goals": context["work"]["goals"][:8],
                "active_projects": context["work"]["projects"][:8],
                "active_tasks": context["work"]["tasks"][:12],
                "active_runs": context["work"]["runs"][:8],
                "review": review,
            },
            "attention": attention,
            "commitments": context["commitments"][:12],
            "recent_activity": context["recent_activity"][:12],
            "episodes": context["episodes"][:8],
            "capabilities": {
                "counts_by_status": capability_counts,
                "items": capabilities,
            },
            "grounding": {
                "canonical_sources": ["assistant_instance", "runtime_snapshot", "work_engine", "notifications", "work_events", "episodes"],
                "model_generated": False,
                "action_claims": False,
            },
        }
