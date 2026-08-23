"""Owner-scoped service for bounded, authorization-aware assessments.

The service is deliberately a ledger and policy boundary.  It plans and
records safe work; it does not invoke scanners, shells, exploit code, or
credential tooling.
"""

from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import json
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy.orm import Session

from core.security_assessment_models import (
    SecurityAuthorization, SecurityEngagement, SecurityEvidence,
    SecurityFinding, SecurityReport, SecurityRun, SecurityScope, SecurityTarget,
)


SAFE_RUN_CLASSES = frozenset({
    "posture_review", "reconnaissance", "host_discovery", "service_enumeration",
    "configuration_review", "vulnerability_observation", "remediation_validation",
})
ACTION_CLASSES = frozenset({"read", "reconnaissance", "enumeration", "configuration_review", "observation"})
SEVERITIES = frozenset({"informational", "low", "medium", "high", "critical"})
FINDING_STATUSES = frozenset({
    "draft", "confirmed", "accepted_risk", "remediation_planned", "remediated",
    "verification_pending", "verified", "false_positive", "closed",
})


class SecurityAssessmentError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _dt(value: Any, label: str, *, required: bool = False) -> datetime | None:
    if value in (None, ""):
        if required:
            raise SecurityAssessmentError(f"{label} is required")
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise SecurityAssessmentError(f"{label} must be ISO-8601") from exc
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def _json(value: Any, label: str, *, maximum: int = 100) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise SecurityAssessmentError(f"{label} must be a list of at most {maximum} entries")
    return value


def _serialize(row: Any) -> dict[str, Any]:
    data = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        data[column.name] = value.isoformat() if isinstance(value, datetime) else value
    return data


def _entry(entry: Any) -> tuple[str, str]:
    if isinstance(entry, str) and entry.strip():
        return "value", entry.strip()
    if isinstance(entry, dict):
        kind = str(entry.get("kind") or entry.get("type") or "value").strip().casefold()
        value = str(entry.get("value") or entry.get("target") or "").strip()
        if value:
            return kind, value
    raise SecurityAssessmentError("scope entries require a kind and value")


def _target_matches(entry: Any, target: SecurityTarget) -> bool:
    kind, value = _entry(entry)
    if kind in {"asset", "cmdb_asset", "canonical_asset_id"}:
        return bool(target.canonical_asset_id and target.canonical_asset_id == value)
    if kind in {"hostname", "host"}:
        return target.target_kind in {"host", "hostname"} and target.target_value.casefold() == value.casefold()
    if kind in {"ip", "address"}:
        return target.target_value == value
    if kind in {"cidr", "network"}:
        try:
            return ipaddress.ip_address(target.target_value) in ipaddress.ip_network(value, strict=False)
        except ValueError:
            return False
    if kind in {"url", "domain", "application"}:
        target_value = target.target_value.casefold().rstrip("/")
        wanted = value.casefold().rstrip("/")
        if kind == "url":
            return target_value == wanted or target_value.startswith(wanted + "/")
        hostname = urlparse(target_value if "://" in target_value else "https://" + target_value).hostname or target_value
        return hostname == wanted or hostname.endswith("." + wanted)
    return target.target_value == value


class SecurityAssessmentService:
    def __init__(self, db: Session):
        self.db = db

    def _engagement(self, owner: str, engagement_id: str) -> SecurityEngagement:
        row = self.db.query(SecurityEngagement).filter_by(id=engagement_id, owner=owner).one_or_none()
        if row is None:
            raise SecurityAssessmentError("engagement not found")
        return row

    def _scope(self, owner: str, scope_id: str) -> SecurityScope:
        row = self.db.query(SecurityScope).filter_by(id=scope_id, owner=owner).one_or_none()
        if row is None:
            raise SecurityAssessmentError("scope not found")
        return row

    def create_engagement(self, owner: str, created_by: str, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()
        if not name or len(name) > 200:
            raise SecurityAssessmentError("engagement name is required")
        row = SecurityEngagement(
            id=_id("eng"), owner=owner, name=name,
            description=str(data.get("description") or "")[:10000],
            assessment_type=str(data.get("assessment_type") or "security_review")[:64],
            starts_at=_dt(data.get("starts_at"), "starts_at"), expires_at=_dt(data.get("expires_at"), "expires_at"),
            rules_of_engagement=str(data.get("rules_of_engagement") or "")[:20000],
            created_by=created_by,
        )
        self.db.add(row); self.db.commit(); self.db.refresh(row)
        return _serialize(row)

    def list_engagements(self, owner: str) -> list[dict[str, Any]]:
        return [_serialize(row) for row in self.db.query(SecurityEngagement).filter_by(owner=owner).order_by(SecurityEngagement.updated_at.desc()).all()]

    def get_engagement(self, owner: str, engagement_id: str) -> dict[str, Any]:
        row = self._engagement(owner, engagement_id)
        result = _serialize(row)
        result["authorizations"] = [_serialize(x) for x in self.db.query(SecurityAuthorization).filter_by(owner=owner, engagement_id=row.id).all()]
        result["scopes"] = [_serialize(x) for x in self.db.query(SecurityScope).filter_by(owner=owner, engagement_id=row.id).all()]
        result["targets"] = [_serialize(x) for x in self.db.query(SecurityTarget).filter_by(owner=owner, engagement_id=row.id).all()]
        result["runs"] = [_serialize(x) for x in self.db.query(SecurityRun).filter_by(owner=owner, engagement_id=row.id).order_by(SecurityRun.created_at.desc()).all()]
        result["findings"] = [_serialize(x) for x in self.db.query(SecurityFinding).filter_by(owner=owner, engagement_id=row.id).order_by(SecurityFinding.updated_at.desc()).all()]
        return result

    def authorize(self, owner: str, engagement_id: str, actor: str, data: dict[str, Any]) -> dict[str, Any]:
        row = self._engagement(owner, engagement_id)
        reference = str(data.get("reference") or "").strip()
        if not reference:
            raise SecurityAssessmentError("authorization reference is required")
        expires = _dt(data.get("expires_at") or row.expires_at, "expires_at", required=True)
        now = _now()
        if expires <= now:
            raise SecurityAssessmentError("authorization must expire in the future")
        auth = SecurityAuthorization(
            id=_id("auth"), engagement_id=row.id, owner=owner, status="authorized",
            reference=reference[:300], notes=str(data.get("notes") or "")[:20000],
            valid_from=_dt(data.get("valid_from"), "valid_from") or now,
            expires_at=expires, approved_by=actor,
        )
        row.authorization_status = "authorized"; row.status = "authorized"; row.authorization_reference = reference[:300]
        row.authorization_notes = str(data.get("notes") or "")[:20000]; row.revision += 1
        self.db.add(auth); self.db.commit(); self.db.refresh(auth)
        return _serialize(auth)

    def add_scope(self, owner: str, engagement_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = self._engagement(owner, engagement_id)
        includes = _json(data.get("includes"), "includes")
        if not includes:
            raise SecurityAssessmentError("scope requires at least one included target")
        scope = SecurityScope(
            id=_id("scope"), engagement_id=row.id, owner=owner,
            includes_json=includes, exclusions_json=_json(data.get("exclusions"), "exclusions"),
            allowed_actions_json=_json(data.get("allowed_actions"), "allowed_actions"),
            prohibited_actions_json=_json(data.get("prohibited_actions"), "prohibited_actions"),
            valid_from=_dt(data.get("valid_from"), "valid_from"), expires_at=_dt(data.get("expires_at"), "expires_at"),
            notes=str(data.get("notes") or "")[:10000],
        )
        self.db.add(scope); self.db.commit(); self.db.refresh(scope)
        return _serialize(scope)

    def add_target(self, owner: str, engagement_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = self._engagement(owner, engagement_id)
        scope = self._scope(owner, str(data.get("scope_id") or ""))
        if scope.engagement_id != row.id:
            raise SecurityAssessmentError("scope does not belong to engagement")
        kind = str(data.get("target_kind") or "").strip().casefold()
        value = str(data.get("target_value") or "").strip()
        if kind not in {"asset", "host", "network", "web_application", "domain", "endpoint", "service"} or not value:
            raise SecurityAssessmentError("target kind and value are required")
        target = SecurityTarget(
            id=_id("target"), engagement_id=row.id, scope_id=scope.id, owner=owner,
            target_kind=kind, target_value=value[:500], canonical_asset_id=data.get("canonical_asset_id"),
            inventory_item_id=data.get("inventory_item_id"), metadata_json=data.get("metadata") or {},
        )
        if not self._scope_contains(scope, target):
            raise SecurityAssessmentError("target is outside the explicit scope")
        self.db.add(target); self.db.commit(); self.db.refresh(target)
        return _serialize(target)

    def _scope_allows(self, scope: SecurityScope, target: SecurityTarget, action_class: str) -> bool:
        if not self._scope_contains(scope, target):
            return False
        allowed = {str(x).casefold() for x in (scope.allowed_actions_json or [])}
        prohibited = {str(x).casefold() for x in (scope.prohibited_actions_json or [])}
        return action_class.casefold() not in prohibited and (not allowed or action_class.casefold() in allowed)

    def _scope_contains(self, scope: SecurityScope, target: SecurityTarget) -> bool:
        now = _now()
        if scope.valid_from and now < scope.valid_from: return False
        if scope.expires_at and now >= scope.expires_at: return False
        if any(_target_matches(entry, target) for entry in (scope.exclusions_json or [])): return False
        if not any(_target_matches(entry, target) for entry in (scope.includes_json or [])): return False
        return True

    def plan_run(self, owner: str, requester: str, engagement_id: str, data: dict[str, Any]) -> dict[str, Any]:
        engagement = self._engagement(owner, engagement_id)
        now = _now()
        if engagement.authorization_status != "authorized" or engagement.status in {"cancelled", "expired"}:
            raise SecurityAssessmentError("engagement is not authorized for runs")
        if engagement.expires_at and now >= engagement.expires_at:
            engagement.status = "expired"; self.db.commit()
            raise SecurityAssessmentError("engagement authorization has expired")
        target = self.db.query(SecurityTarget).filter_by(id=str(data.get("target_id") or ""), owner=owner, engagement_id=engagement_id).one_or_none()
        if target is None: raise SecurityAssessmentError("target not found")
        scope = self._scope(owner, target.scope_id)
        run_class = str(data.get("run_class") or "").strip().casefold()
        if run_class not in SAFE_RUN_CLASSES: raise SecurityAssessmentError("unsupported safe assessment run class")
        action_class = "reconnaissance" if run_class in {"reconnaissance", "host_discovery"} else "enumeration" if run_class == "service_enumeration" else "observation"
        if not self._scope_allows(scope, target, action_class): raise SecurityAssessmentError("run target or action is outside the explicit scope")
        run = SecurityRun(
            id=_id("run"), engagement_id=engagement_id, target_id=target.id, scope_id=scope.id, owner=owner,
            run_class=run_class, capability_id="security.run.plan", action_id="plan",
            status="planned", requester=requester, authorization_decision="authorized",
            approval_reference=data.get("approval_reference"), result_summary_json={"mode": "bounded_plan_only", "action_class": action_class},
        )
        self.db.add(run); self.db.commit(); self.db.refresh(run)
        return _serialize(run)

    def complete_run(self, owner: str, run_id: str, data: dict[str, Any]) -> dict[str, Any]:
        run = self.db.query(SecurityRun).filter_by(id=run_id, owner=owner).one_or_none()
        if run is None: raise SecurityAssessmentError("run not found")
        if run.status not in {"planned", "approved", "running"}: raise SecurityAssessmentError("run is not completable")
        summary = data.get("result_summary") or {}
        if not isinstance(summary, dict) or len(json.dumps(summary)) > 20000: raise SecurityAssessmentError("result summary is invalid")
        run.status = "completed"; run.started_at = run.started_at or _now(); run.ended_at = _now(); run.result_summary_json = summary; run.revision += 1
        self.db.commit(); self.db.refresh(run)
        return _serialize(run)

    def add_evidence(self, owner: str, requester: str, engagement_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._engagement(owner, engagement_id)
        run_id = data.get("run_id")
        if run_id and self.db.query(SecurityRun).filter_by(id=run_id, owner=owner, engagement_id=engagement_id).one_or_none() is None: raise SecurityAssessmentError("run not found")
        row = SecurityEvidence(
            id=_id("evidence"), engagement_id=engagement_id, run_id=run_id, target_id=data.get("target_id"), owner=owner,
            evidence_kind=str(data.get("evidence_kind") or "structured_observation")[:64], reference=str(data.get("reference") or "").strip()[:1000],
            structured_facts_json=data.get("facts") or {}, observed_at=_dt(data.get("observed_at"), "observed_at") or _now(),
            source_trust=str(data.get("source_trust") or "system")[:32], confidence=str(data.get("confidence") or "medium")[:32], content_digest=data.get("content_digest"),
        )
        if not row.reference: raise SecurityAssessmentError("evidence reference is required")
        self.db.add(row); self.db.commit(); self.db.refresh(row)
        return _serialize(row)

    def add_finding(self, owner: str, created_by: str, engagement_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._engagement(owner, engagement_id)
        severity = str(data.get("severity") or "informational").casefold()
        if severity not in SEVERITIES: raise SecurityAssessmentError("invalid severity")
        refs = _json(data.get("evidence_refs"), "evidence_refs")
        row = SecurityFinding(
            id=_id("finding"), engagement_id=engagement_id, target_id=data.get("target_id"), run_id=data.get("run_id"), owner=owner,
            title=str(data.get("title") or "").strip()[:300], description=str(data.get("description") or "")[:20000],
            category=str(data.get("category") or "observation")[:64], severity=severity, confidence=str(data.get("confidence") or "medium")[:32],
            status="draft", evidence_refs_json=refs, remediation=str(data.get("remediation") or "")[:20000], created_by=created_by,
        )
        if not row.title or not row.description: raise SecurityAssessmentError("finding title and description are required")
        self.db.add(row); self.db.commit(); self.db.refresh(row)
        return _serialize(row)

    def update_finding(self, owner: str, finding_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = self.db.query(SecurityFinding).filter_by(id=finding_id, owner=owner).one_or_none()
        if row is None: raise SecurityAssessmentError("finding not found")
        if "status" in data and str(data["status"]) not in FINDING_STATUSES: raise SecurityAssessmentError("invalid finding status")
        if "severity" in data and str(data["severity"]).casefold() not in SEVERITIES: raise SecurityAssessmentError("invalid severity")
        for key in ("status", "severity", "remediation", "verification_state", "confidence"):
            if key in data: setattr(row, key, str(data[key]))
        if "evidence_refs" in data: row.evidence_refs_json = _json(data["evidence_refs"], "evidence_refs")
        row.revision += 1; row.last_seen = _now(); self.db.commit(); self.db.refresh(row)
        return _serialize(row)

    def report(self, owner: str, generated_by: str, engagement_id: str) -> dict[str, Any]:
        engagement = self._engagement(owner, engagement_id)
        scopes = [_serialize(x) for x in self.db.query(SecurityScope).filter_by(owner=owner, engagement_id=engagement_id).all()]
        targets = [_serialize(x) for x in self.db.query(SecurityTarget).filter_by(owner=owner, engagement_id=engagement_id).all()]
        runs = [_serialize(x) for x in self.db.query(SecurityRun).filter_by(owner=owner, engagement_id=engagement_id).all()]
        findings = [_serialize(x) for x in self.db.query(SecurityFinding).filter_by(owner=owner, engagement_id=engagement_id).all()]
        evidence = [_serialize(x) for x in self.db.query(SecurityEvidence).filter_by(owner=owner, engagement_id=engagement_id).all()]
        projection = {"engagement": _serialize(engagement), "authorization_scope": scopes, "targets": targets, "methodology_runs": runs, "findings": findings, "evidence_references": evidence, "limitations": ["V1 records bounded plans and observations; it does not execute exploits, credential attacks, or arbitrary network commands."], "timeline": sorted(runs + evidence, key=lambda x: x.get("created_at") or "")}
        row = SecurityReport(id=_id("report"), engagement_id=engagement_id, owner=owner, generated_by=generated_by, projection_json=projection, source_revision=engagement.revision)
        self.db.add(row); self.db.commit(); self.db.refresh(row)
        return _serialize(row) | {"projection": projection}
