"""Transactional persistence facade for supervised economic work.

This is a control plane only: it cannot contact a network service, schedule a
task, transfer value, or execute a proposal.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, update
from sqlalchemy.exc import IntegrityError

from core.economic_models import (
    EconomicApprovalReceipt, EconomicAuditReceipt, EconomicBudgetUsage,
    EconomicControl, EconomicJob, EconomicMandateRecord,
)
from src.economic_mandates import (
    ActionDisposition, BudgetUsage, EconomicAction, EconomicMandate,
    EconomicRuntimeControls, classify_economic_action, evaluate_economic_action,
    validate_mandate,
)


class EconomicStoreError(ValueError):
    pass


@dataclass(frozen=True)
class UsageDelta:
    external_actions: int = 0
    messages: int = 0
    submissions: int = 0
    gross_spend_minor: Decimal = Decimal(0)
    committed_value_minor: Decimal = Decimal(0)

    def __post_init__(self):
        for value in (self.external_actions, self.messages, self.submissions):
            if type(value) is not int or value < 0:
                raise EconomicStoreError("usage counts must be non-negative integers")
        for value in (self.gross_spend_minor, self.committed_value_minor):
            if not isinstance(value, Decimal) or value < 0 or value != value.to_integral_value():
                raise EconomicStoreError("monetary usage must be a non-negative whole Decimal minor-unit value")
        if not any((self.external_actions, self.messages, self.submissions,
                    self.gross_spend_minor, self.committed_value_minor)):
            raise EconomicStoreError("usage delta must not be empty")


_TRANSITIONS = {
    "proposed": {"prepared", "awaiting_approval", "cancelled", "failed"},
    "prepared": {"awaiting_approval", "cancelled", "failed"},
    "awaiting_approval": {"approved", "cancelled", "failed"},
    "approved": {"executing", "cancelled", "failed"},
    "executing": {"completed", "failed", "cancelled"},
    "completed": set(), "failed": set(), "cancelled": set(),
}


def _required(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise EconomicStoreError(f"{label} is required")
    return value


def _digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


class EconomicStore:
    def __init__(self, db):
        self.db = db

    def get_controls(self, *, owner: str) -> EconomicControl:
        owner = _required(owner, "owner")
        row = self.db.get(EconomicControl, owner)
        if row is None:
            row = EconomicControl(owner=owner, kill_switch_engaged=True, revision=0)
            self.db.add(row)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                row = self.db.get(EconomicControl, owner)
            if row is None:
                raise EconomicStoreError("could not initialize economic controls")
        return row

    def set_kill_switch(self, *, owner: str, engaged: bool, expected_revision: int) -> EconomicControl:
        owner = _required(owner, "owner")
        if type(engaged) is not bool or type(expected_revision) is not int or expected_revision < 0:
            raise EconomicStoreError("valid switch value and expected revision are required")
        self.get_controls(owner=owner)
        result = self.db.execute(update(EconomicControl).where(
            EconomicControl.owner == owner,
            EconomicControl.revision == expected_revision,
        ).values(kill_switch_engaged=engaged, revision=EconomicControl.revision + 1))
        if result.rowcount != 1:
            self.db.rollback()
            raise EconomicStoreError("economic control revision conflict")
        self._audit(owner, "kill_switch_changed", {"engaged": engaged}, f"switch:{expected_revision + 1}", owner)
        self.db.commit()
        return self.db.get(EconomicControl, owner)

    def create_mandate(self, mandate: EconomicMandate) -> EconomicMandateRecord:
        validate_mandate(mandate)
        existing = self.db.query(EconomicMandateRecord).filter_by(owner=mandate.owner, digest=mandate.digest).one_or_none()
        if existing:
            return existing
        limits = mandate.budgets
        row = EconomicMandateRecord(
            id=mandate.mandate_id, owner=mandate.owner, digest=mandate.digest,
            policy_version=mandate.policy_version, autonomy_tier=mandate.autonomy_tier.value,
            allowed_actions_json=[a.value for a in mandate.allowed_actions], issued_at=mandate.issued_at,
            expires_at=mandate.expires_at, status="inactive",
            external_actions_limit=limits.external_actions, messages_limit=limits.messages,
            submissions_limit=limits.submissions,
            gross_spend_minor_limit=Decimal(limits.gross_spend_minor),
            committed_value_minor_limit=Decimal(limits.committed_value_minor),
        )
        self.db.add(row)
        self._audit(mandate.owner, "mandate_created", {"digest": mandate.digest}, f"mandate:{mandate.digest}", mandate.owner, mandate_id=row.id)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            existing = self.db.query(EconomicMandateRecord).filter_by(owner=mandate.owner, digest=mandate.digest).one_or_none()
            if existing:
                return existing
            raise EconomicStoreError("mandate id is already in use") from exc
        return row

    def activate_mandate(self, *, owner: str, mandate_id: str, now: int | None = None) -> EconomicMandateRecord:
        owner, mandate_id = _required(owner, "owner"), _required(mandate_id, "mandate id")
        timestamp = int(time.time()) if now is None else now
        result = self.db.execute(update(EconomicMandateRecord).where(
            EconomicMandateRecord.id == mandate_id, EconomicMandateRecord.owner == owner,
            EconomicMandateRecord.status == "inactive", EconomicMandateRecord.expires_at > timestamp,
        ).values(status="active"))
        if result.rowcount != 1:
            self.db.rollback(); raise EconomicStoreError("mandate cannot be activated")
        self._audit(owner, "mandate_activated", {}, f"activate:{mandate_id}", owner, mandate_id=mandate_id)
        self.db.commit(); return self._mandate(owner, mandate_id)

    def revoke_mandate(self, *, owner: str, mandate_id: str) -> EconomicMandateRecord:
        owner, mandate_id = _required(owner, "owner"), _required(mandate_id, "mandate id")
        result = self.db.execute(update(EconomicMandateRecord).where(
            EconomicMandateRecord.id == mandate_id, EconomicMandateRecord.owner == owner,
            EconomicMandateRecord.status.in_(("inactive", "active")),
        ).values(status="revoked"))
        if result.rowcount != 1:
            self.db.rollback(); raise EconomicStoreError("mandate cannot be revoked")
        self._audit(owner, "mandate_revoked", {}, f"revoke:{mandate_id}", owner, mandate_id=mandate_id)
        self.db.commit(); return self._mandate(owner, mandate_id)

    def create_job(self, *, owner: str, mandate_id: str, action: str, title: str,
                   proposal: dict[str, Any], idempotency_key: str, kind: str = "job") -> EconomicJob:
        owner, mandate_id = _required(owner, "owner"), _required(mandate_id, "mandate id")
        title, key = _required(title, "title"), _required(idempotency_key, "idempotency key")
        if kind not in {"job", "proposal"} or not isinstance(proposal, dict):
            raise EconomicStoreError("valid job kind and proposal are required")
        try: normalized = EconomicAction(action)
        except ValueError as exc: raise EconomicStoreError("unknown economic action") from exc
        if classify_economic_action(normalized) is ActionDisposition.FORBIDDEN:
            raise EconomicStoreError("forbidden economic actions cannot be persisted as jobs")
        mandate = self._mandate(owner, mandate_id)
        if (mandate.status != "active" or mandate.expires_at <= int(time.time())
                or normalized.value not in mandate.allowed_actions_json):
            raise EconomicStoreError("job is outside an active mandate")
        existing = self.db.query(EconomicJob).filter_by(owner=owner, idempotency_key=key).one_or_none()
        if existing:
            if (existing.mandate_id, existing.action, existing.title, existing.kind,
                    existing.proposal_json) != (mandate_id, normalized.value, title, kind, proposal):
                raise EconomicStoreError("job idempotency key was reused with different content")
            return existing
        row = EconomicJob(id=uuid.uuid4().hex, owner=owner, mandate_id=mandate_id, kind=kind,
                          action=normalized.value, title=title, proposal_json=proposal,
                          result_json={}, idempotency_key=key)
        self.db.add(row)
        self._audit(owner, "job_created", {"action": action}, f"audit:{key}", owner, mandate_id, row.id)
        try: self.db.commit()
        except IntegrityError:
            self.db.rollback(); existing = self.db.query(EconomicJob).filter_by(owner=owner, idempotency_key=key).one_or_none()
            if existing: return existing
            raise
        return row

    def transition_job(self, *, owner: str, job_id: str, expected_state: str, new_state: str) -> EconomicJob:
        owner, job_id = _required(owner, "owner"), _required(job_id, "job id")
        # Approval is not an ordinary state transition.  record_approval()
        # atomically persists the exact-request receipt and advances the job;
        # allowing callers through this method would bypass that invariant.
        if new_state == "approved":
            raise EconomicStoreError("direct job approval is not permitted")
        if new_state not in _TRANSITIONS.get(expected_state, set()):
            raise EconomicStoreError("job transition is not permitted")
        result = self.db.execute(update(EconomicJob).where(
            EconomicJob.id == job_id, EconomicJob.owner == owner, EconomicJob.state == expected_state,
        ).values(state=new_state))
        if result.rowcount != 1:
            self.db.rollback(); raise EconomicStoreError("job state conflict or owner mismatch")
        self._audit(owner, "job_transition", {"from": expected_state, "to": new_state},
                    f"transition:{job_id}:{expected_state}:{new_state}", owner, job_id=job_id)
        self.db.commit(); return self.db.query(EconomicJob).filter_by(id=job_id, owner=owner).one()

    def record_approval(self, *, owner: str, job_id: str, decision: str, actor: str,
                        exact_request: dict[str, Any], idempotency_key: str) -> EconomicApprovalReceipt:
        owner, job_id, actor = _required(owner, "owner"), _required(job_id, "job id"), _required(actor, "actor")
        key = _required(idempotency_key, "idempotency key")
        if decision not in {"approved", "denied"} or not isinstance(exact_request, dict):
            raise EconomicStoreError("valid exact approval decision is required")
        existing = self.db.query(EconomicApprovalReceipt).filter_by(owner=owner, idempotency_key=key).one_or_none()
        request_digest = _digest(exact_request)
        if existing:
            if (existing.job_id, existing.decision, existing.actor, existing.exact_request_digest) != (
                    job_id, decision, actor, request_digest):
                raise EconomicStoreError("approval idempotency key was reused with different content")
            return existing
        job = self.db.query(EconomicJob).filter_by(id=job_id, owner=owner).one_or_none()
        if not job or job.state != "awaiting_approval": raise EconomicStoreError("job is not awaiting approval")
        if request_digest != _digest(job.proposal_json):
            raise EconomicStoreError("approval does not match the exact persisted request")
        mandate = self._mandate(owner, job.mandate_id)
        row = EconomicApprovalReceipt(id=uuid.uuid4().hex, owner=owner, mandate_id=mandate.id,
            job_id=job.id, action=job.action, decision=decision, mandate_digest=mandate.digest,
            exact_request_digest=request_digest, actor=actor, idempotency_key=key)
        self.db.add(row)
        target = "approved" if decision == "approved" else "cancelled"
        updated = self.db.execute(update(EconomicJob).where(EconomicJob.id == job.id,
            EconomicJob.owner == owner, EconomicJob.state == "awaiting_approval").values(state=target))
        if updated.rowcount != 1: self.db.rollback(); raise EconomicStoreError("job approval state conflict")
        try: self.db.commit()
        except IntegrityError:
            self.db.rollback(); existing = self.db.query(EconomicApprovalReceipt).filter_by(owner=owner, idempotency_key=key).one_or_none()
            if existing: return existing
            raise
        return row

    def reserve_usage(self, *, owner: str, mandate_id: str, action: str, delta: UsageDelta,
                      idempotency_key: str, job_id: str | None = None, now: int | None = None) -> EconomicBudgetUsage:
        owner, mandate_id, key = _required(owner, "owner"), _required(mandate_id, "mandate id"), _required(idempotency_key, "idempotency key")
        if not isinstance(delta, UsageDelta): raise EconomicStoreError("valid usage delta is required")
        existing = self.db.query(EconomicBudgetUsage).filter_by(owner=owner, idempotency_key=key).one_or_none()
        if existing:
            expected = (mandate_id, job_id, delta.external_actions, delta.messages,
                        delta.submissions, delta.gross_spend_minor, delta.committed_value_minor)
            actual = (existing.mandate_id, existing.job_id, existing.external_actions_delta,
                      existing.messages_delta, existing.submissions_delta,
                      existing.gross_spend_minor_delta, existing.committed_value_minor_delta)
            if actual != expected:
                raise EconomicStoreError("usage idempotency key was reused with different content")
            return existing
        mandate = self._mandate(owner, mandate_id)
        controls = self.get_controls(owner=owner)
        if job_id is not None:
            job = self.db.query(EconomicJob).filter_by(id=job_id, owner=owner).one_or_none()
            if not job or job.mandate_id != mandate_id or job.action != action:
                raise EconomicStoreError("usage job does not belong to this owner, mandate, and action")
        projected = BudgetUsage(
            external_actions=mandate.external_actions_used + delta.external_actions,
            messages=mandate.messages_used + delta.messages,
            submissions=mandate.submissions_used + delta.submissions,
            gross_spend_minor=int(mandate.gross_spend_minor_used + delta.gross_spend_minor),
            committed_value_minor=int(mandate.committed_value_minor_used + delta.committed_value_minor),
        )
        policy = self._policy_mandate(mandate)
        decision = evaluate_economic_action(policy, action, usage_after_action=projected,
            controls=EconomicRuntimeControls(kill_switch_engaged=controls.kill_switch_engaged),
            owner=owner, now=int(time.time()) if now is None else now)
        # Approval-gated actions require a matching durable approval for this exact job.
        if decision.requires_approval:
            approved = job_id and self.db.query(EconomicApprovalReceipt).filter_by(
                owner=owner, job_id=job_id, action=action, decision="approved", mandate_digest=mandate.digest).first()
            if not approved: raise EconomicStoreError("exact durable approval is required")
        elif not decision.allowed: raise EconomicStoreError(decision.reason)
        conditions = [EconomicMandateRecord.id == mandate_id, EconomicMandateRecord.owner == owner,
            EconomicMandateRecord.status == "active",
            EconomicMandateRecord.external_actions_used + delta.external_actions <= EconomicMandateRecord.external_actions_limit,
            EconomicMandateRecord.messages_used + delta.messages <= EconomicMandateRecord.messages_limit,
            EconomicMandateRecord.submissions_used + delta.submissions <= EconomicMandateRecord.submissions_limit,
            EconomicMandateRecord.gross_spend_minor_used + delta.gross_spend_minor <= EconomicMandateRecord.gross_spend_minor_limit,
            EconomicMandateRecord.committed_value_minor_used + delta.committed_value_minor <= EconomicMandateRecord.committed_value_minor_limit]
        result = self.db.execute(update(EconomicMandateRecord).where(and_(*conditions)).values(
            external_actions_used=EconomicMandateRecord.external_actions_used + delta.external_actions,
            messages_used=EconomicMandateRecord.messages_used + delta.messages,
            submissions_used=EconomicMandateRecord.submissions_used + delta.submissions,
            gross_spend_minor_used=EconomicMandateRecord.gross_spend_minor_used + delta.gross_spend_minor,
            committed_value_minor_used=EconomicMandateRecord.committed_value_minor_used + delta.committed_value_minor))
        if result.rowcount != 1: self.db.rollback(); raise EconomicStoreError("budget reservation conflict or limit exceeded")
        row = EconomicBudgetUsage(id=uuid.uuid4().hex, owner=owner, mandate_id=mandate_id,
            job_id=job_id, idempotency_key=key, external_actions_delta=delta.external_actions,
            messages_delta=delta.messages, submissions_delta=delta.submissions,
            gross_spend_minor_delta=delta.gross_spend_minor,
            committed_value_minor_delta=delta.committed_value_minor)
        self.db.add(row)
        try: self.db.commit()
        except IntegrityError:
            self.db.rollback(); existing = self.db.query(EconomicBudgetUsage).filter_by(owner=owner, idempotency_key=key).one_or_none()
            if existing: return existing
            raise
        return row

    def _mandate(self, owner: str, mandate_id: str) -> EconomicMandateRecord:
        row = self.db.query(EconomicMandateRecord).filter_by(id=mandate_id, owner=owner).one_or_none()
        if not row: raise EconomicStoreError("economic mandate not found")
        return row

    @staticmethod
    def _policy_mandate(row: EconomicMandateRecord) -> EconomicMandate:
        from src.economic_mandates import BudgetLimits
        return EconomicMandate.create(mandate_id=row.id, owner=row.owner, autonomy_tier=row.autonomy_tier,
            allowed_actions=row.allowed_actions_json, issued_at=row.issued_at, expires_at=row.expires_at,
            policy_version=row.policy_version, budgets=BudgetLimits(
                external_actions=row.external_actions_limit, messages=row.messages_limit,
                submissions=row.submissions_limit, gross_spend_minor=int(row.gross_spend_minor_limit),
                committed_value_minor=int(row.committed_value_minor_limit)))

    def _audit(self, owner: str, event: str, detail: dict, key: str, actor: str,
               mandate_id: str | None = None, job_id: str | None = None):
        self.db.add(EconomicAuditReceipt(id=uuid.uuid4().hex, owner=owner, mandate_id=mandate_id,
            job_id=job_id, event_type=event, detail_json=detail, actor=actor, idempotency_key=key))
