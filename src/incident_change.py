"""Incident/Change service; WorkEngine remains the execution authority."""
from core.incident_models import Change, Incident, IncidentHypothesis
from core.work_models import WorkRun
from src.run_planner import RunPlanner
from src.work_engine import WorkError, ident, now, parse_dt, serialize

INCIDENT_STATUSES = {"reported", "triage", "investigating", "monitoring", "resolved", "reviewed", "cancelled"}
CHANGE_STATUSES = {"draft", "validated", "awaiting_approval", "scheduled", "executing", "verifying", "completed", "failed", "compensated", "cancelled"}


class IncidentChangeService:
    def __init__(self, db): self.db = db

    def _incident(self, owner, incident_id):
        row = self.db.query(Incident).filter_by(owner=owner, id=incident_id).one_or_none()
        if row is None: raise WorkError("incident not found")
        return row

    def create_incident(self, owner, data):
        title = str(data.get("title") or "").strip()
        if not title: raise WorkError("incident title is required")
        status = str(data.get("status") or "reported")
        if status not in INCIDENT_STATUSES: raise WorkError("invalid incident status")
        row = Incident(id=ident("incident"), owner=owner, title=title[:300], severity=str(data.get("severity") or "moderate")[:32], status=status, symptoms=data.get("symptoms") or [], affected_entities=data.get("affected_entities") or [], evidence_references=data.get("evidence_references") or [])
        self.db.add(row); self.db.commit(); self.db.refresh(row); return serialize(row)

    def list_incidents(self, owner, *, status=None, limit=200):
        query = self.db.query(Incident).filter_by(owner=owner)
        if status: query = query.filter_by(status=status)
        return [serialize(row) for row in query.order_by(Incident.updated_at.desc()).limit(max(1, min(int(limit), 500))).all()]

    def get_incident(self, owner, incident_id):
        row = self._incident(owner, incident_id)
        result = serialize(row)
        result["hypotheses"] = self.list_hypotheses(owner, incident_id)
        result["changes"] = self.list_changes(owner, incident_id=incident_id)
        result["runs"] = []
        for change in result["changes"]:
            if not change.get("run_id"): continue
            run = self.db.query(WorkRun).filter_by(owner=owner, id=change["run_id"]).one_or_none()
            if run is not None:
                result["runs"].append({"id": run.id, "status": run.status, "lifecycle_state": run.lifecycle_state, "result_summary": run.result_summary or {}, "verification": run.verification or {}})
        result["canonical_refs"] = {"incident": f"incident://{row.id}", "evidence": list(row.evidence_references or [])}
        return result

    def add_hypothesis(self, owner, incident_id, data):
        incident = self._incident(owner, incident_id); statement = str(data.get("statement") or "").strip()
        if not statement: raise WorkError("hypothesis statement is required")
        row = IncidentHypothesis(id=ident("hypothesis"), owner=owner, incident_id=incident.id, statement=statement[:20000], status=str(data.get("status") or "open"), confidence_class=str(data.get("confidence_class") or "unknown")[:32], supporting_evidence=data.get("supporting_evidence") or [], contradicting_evidence=data.get("contradicting_evidence") or [])
        if row.status not in {"open", "supported", "rejected", "superseded"}: raise WorkError("invalid hypothesis status")
        self.db.add(row); timeline=list(incident.timeline or []); timeline.append({"kind":"hypothesis_added","hypothesis_id":row.id,"at":now().isoformat()}); incident.timeline=timeline[-200:]
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def list_hypotheses(self, owner, incident_id):
        self._incident(owner, incident_id)
        return [serialize(row) for row in self.db.query(IncidentHypothesis).filter_by(owner=owner, incident_id=incident_id).order_by(IncidentHypothesis.created_at).all()]

    def update_incident(self, owner, incident_id, data):
        row = self._incident(owner, incident_id)
        if "status" in data and data["status"] not in INCIDENT_STATUSES: raise WorkError("invalid incident status")
        for key in ("status", "severity", "root_cause", "outcome"):
            if key in data: setattr(row, key, str(data[key])[:20000])
        for key in ("symptoms", "affected_entities", "evidence_references"):
            if key in data: setattr(row, key, data[key] or [])
        if row.status in {"resolved", "reviewed", "cancelled"}: row.closed_at = row.closed_at or now()
        self.db.commit(); self.db.refresh(row); return serialize(row)

    def create_change(self, owner, data):
        objective = str(data.get("objective") or "").strip()
        if not objective: raise WorkError("change objective is required")
        incident_id = data.get("incident_id")
        if incident_id: self._incident(owner, incident_id)
        run_id = data.get("run_id")
        preview = data.get("preview") or {}
        if run_id:
            if self.db.query(WorkRun).filter_by(owner=owner, id=run_id).one_or_none() is None: raise WorkError("run not found")
            planner = RunPlanner(self.db)
            preview = planner.compile(owner, run_id)
            validation = planner.validate(owner, run_id)
            preview = {**preview, "validation": {"valid": validation["valid"], "failures": validation["failures"], "warnings": validation["warnings"]}}
        blast_radius = data.get("blast_radius") or preview.get("blast_radius") or {}
        row = Change(id=ident("change"), owner=owner, incident_id=incident_id, run_id=run_id, objective=objective[:20000], status=str(data.get("status") or "draft"), targets=data.get("targets") or [], desired_state=data.get("desired_state") or {}, preview=preview, prechecks=data.get("prechecks") or [], action_ids=data.get("action_ids") or [], resources=data.get("resources") or [], risk=str(data.get("risk") or "low")[:32], blast_radius=blast_radius, approval=data.get("approval") or {}, compensation=data.get("compensation") or {}, verification=data.get("verification") or {})
        if row.status not in CHANGE_STATUSES: raise WorkError("invalid change status")
        self.db.add(row); self.db.commit(); self.db.refresh(row); return serialize(row)

    def list_changes(self, owner, *, status=None, incident_id=None, limit=200):
        query=self.db.query(Change).filter_by(owner=owner)
        if status: query=query.filter_by(status=status)
        if incident_id: query=query.filter_by(incident_id=incident_id)
        return [serialize(row) for row in query.order_by(Change.updated_at.desc()).limit(max(1,min(int(limit),500))).all()]

    def get_change(self, owner, change_id):
        row = self.db.query(Change).filter_by(owner=owner, id=change_id).one_or_none()
        if row is None: raise WorkError("change not found")
        result = serialize(row)
        if row.run_id:
            run = self.db.query(WorkRun).filter_by(owner=owner, id=row.run_id).one_or_none()
            if run is not None:
                result["run_state"] = {"status": run.status, "lifecycle_state": run.lifecycle_state, "result_summary": run.result_summary or {}, "verification": run.verification or {}, "error_summary": run.error_summary}
        result["canonical_refs"] = {"change": f"change://{row.id}", "run": f"run://{row.run_id}" if row.run_id else None, "incident": f"incident://{row.incident_id}" if row.incident_id else None}
        return result
