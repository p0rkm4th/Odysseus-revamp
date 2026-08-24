"""Durable owner-scoped evaluation corpus and supervised failure workflow."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy.orm import Session
from core.evaluation_models import EvaluationFailure, EvaluationRun, EvaluationScenario

FAILURE_TAXONOMY = {
    "canonical_data_hallucination", "environment_assumption", "tool_exposure_failure",
    "generic_shell_fallback", "action_narration", "referent_failure", "continuity_failure",
    "memory_crowding", "cmdb_identity_error", "approval_digest_mutation", "action_replay",
    "scope_violation", "duplicate_read_loop", "provider_error", "unknown",
}


class EvaluationError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _id(prefix):
    return f"{prefix}_{uuid4().hex}"


def _serialize(row):
    return {column.name: (getattr(row, column.name).isoformat() if isinstance(getattr(row, column.name), datetime) else getattr(row, column.name)) for column in row.__table__.columns}


class EvaluationService:
    def __init__(self, db: Session):
        self.db = db

    def _scenario(self, owner, scenario_id):
        row = self.db.query(EvaluationScenario).filter_by(owner=owner, id=scenario_id).one_or_none()
        if row is None: raise EvaluationError("evaluation scenario not found")
        return row

    def create_scenario(self, owner: str, data: dict[str, Any]):
        key = str(data.get("scenario_key") or "").strip()
        title = str(data.get("title") or "").strip()
        domain = str(data.get("domain") or "").strip()
        task_class = str(data.get("task_class") or "").strip()
        if not key or not title or not domain or not task_class: raise EvaluationError("scenario key, title, domain, and task class are required")
        if self.db.query(EvaluationScenario).filter_by(owner=owner, scenario_key=key).first(): raise EvaluationError("scenario key already exists")
        row = EvaluationScenario(id=_id("eval_scenario"), owner=owner, scenario_key=key[:200], domain=domain[:64], task_class=task_class[:128], title=title[:300], initial_state=data.get("initial_state") or {}, initial_epistemic_state=data.get("initial_epistemic_state") or {}, user_intent=str(data.get("user_intent") or "")[:20000], available_capabilities=data.get("available_capabilities") or [], available_models=data.get("available_models") or [], authority=data.get("authority") or {}, expected=data.get("expected") or {}, forbidden=data.get("forbidden") or {}, scoring=data.get("scoring") or {}, source_failure_id=data.get("source_failure_id"))
        self.db.add(row); self.db.commit(); self.db.refresh(row); return _serialize(row)

    def record_run(self, owner: str, scenario_id: str, data: dict[str, Any]):
        scenario = self._scenario(owner, scenario_id)
        failure = str(data.get("failure_category") or "none")
        if failure not in FAILURE_TAXONOMY and failure != "none": raise EvaluationError("unknown evaluation failure taxonomy")
        score = data.get("score") or {}
        passed = data.get("passed")
        if passed is not None: passed = 1 if bool(passed) else 0
        row = EvaluationRun(id=_id("eval_run"), owner=owner, scenario_id=scenario.id, work_run_id=data.get("work_run_id"), model=data.get("model") or {}, trajectory=data.get("trajectory") or {}, score=score, metrics=data.get("metrics") or {}, artifacts=data.get("artifacts") or [], failure_category=failure, status=str(data.get("status") or "completed"), passed=passed, ended_at=_now())
        self.db.add(row); self.db.commit(); self.db.refresh(row); return _serialize(row)

    def record_failure(self, owner: str, data: dict[str, Any]):
        taxonomy = str(data.get("taxonomy") or "unknown")
        if taxonomy not in FAILURE_TAXONOMY: raise EvaluationError("unknown failure taxonomy")
        title = str(data.get("title") or "").strip()
        if not title: raise EvaluationError("failure title is required")
        row = EvaluationFailure(id=_id("eval_failure"), owner=owner, evaluation_run_id=data.get("evaluation_run_id"), work_run_id=data.get("work_run_id"), title=title[:300], taxonomy=taxonomy, impact=str(data.get("impact") or "low")[:32], reproducibility=str(data.get("reproducibility") or "unknown")[:32], sanitized_context=data.get("sanitized_context") or {}, expected_behavior=data.get("expected_behavior") or {}, actual_behavior=data.get("actual_behavior") or {}, proposed_scenario=data.get("proposed_scenario") or {})
        self.db.add(row); self.db.commit(); self.db.refresh(row); return _serialize(row)

    def review_failure(self, owner: str, failure_id: str, *, decision: str, reviewed_by: str):
        row = self.db.query(EvaluationFailure).filter_by(owner=owner, id=failure_id).one_or_none()
        if row is None: raise EvaluationError("evaluation failure not found")
        if decision not in {"admitted", "rejected"}: raise EvaluationError("failure review decision is invalid")
        row.status = decision; row.reviewed_by = str(reviewed_by or "")[:200] or None; row.reviewed_at = _now(); self.db.commit(); self.db.refresh(row); return _serialize(row)

    def list_scenarios(self, owner: str, *, domain=None, status=None, limit=200):
        query = self.db.query(EvaluationScenario).filter_by(owner=owner)
        if domain: query = query.filter_by(domain=domain)
        if status: query = query.filter_by(status=status)
        return [_serialize(row) for row in query.order_by(EvaluationScenario.updated_at.desc()).limit(max(1, min(int(limit), 500))).all()]

    def list_failures(self, owner: str, *, status=None, taxonomy=None, limit=200):
        query = self.db.query(EvaluationFailure).filter_by(owner=owner)
        if status: query = query.filter_by(status=status)
        if taxonomy: query = query.filter_by(taxonomy=taxonomy)
        return [_serialize(row) for row in query.order_by(EvaluationFailure.updated_at.desc()).limit(max(1, min(int(limit), 500))).all()]
