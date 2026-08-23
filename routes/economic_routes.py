"""Authenticated, owner-scoped control APIs for supervised economic work.

These endpoints only manage authority, proposals, receipts, and accounting.
They deliberately contain no scheduler or external execution connector.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from fastapi import APIRouter, Body, HTTPException, Query, Request

from core.database import SessionLocal
from core.economic_models import (
    EconomicApprovalReceipt,
    EconomicBudgetUsage,
    EconomicJob,
    EconomicMandateRecord,
)
from src.auth_helpers import require_user
from src.economic_mandates import (
    BudgetLimits,
    BudgetUsage,
    EconomicMandate,
    EconomicRuntimeControls,
    evaluate_economic_action,
)
from src.economic_store import EconomicStore, EconomicStoreError, UsageDelta
from src.owner_identity import effective_storage_owner


def _owner(request: Request) -> str:
    owner = effective_storage_owner(require_user(request))
    if not owner:
        raise HTTPException(401, "An authenticated economic-work owner is required")
    return owner


def _safe_error(exc: Exception) -> HTTPException:
    message = str(exc)
    if "not found" in message or "owner mismatch" in message:
        return HTTPException(404, "Economic record not found")
    if "conflict" in message or "cannot be" in message or "not permitted" in message:
        return HTTPException(409, "Economic control state conflict")
    return HTTPException(400, "Economic request was rejected")


def _money(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise EconomicStoreError(f"{label} is invalid")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise EconomicStoreError(f"{label} is invalid") from exc
    if parsed < 0 or parsed != parsed.to_integral_value():
        raise EconomicStoreError(f"{label} is invalid")
    return parsed


def _mandate_json(row: EconomicMandateRecord) -> dict[str, Any]:
    return {
        "id": row.id, "digest": row.digest, "policy_version": row.policy_version,
        "autonomy_tier": row.autonomy_tier,
        "allowed_actions": list(row.allowed_actions_json), "issued_at": row.issued_at,
        "expires_at": row.expires_at, "status": row.status,
        "budgets": {
            "external_actions": {"used": row.external_actions_used, "limit": row.external_actions_limit},
            "messages": {"used": row.messages_used, "limit": row.messages_limit},
            "submissions": {"used": row.submissions_used, "limit": row.submissions_limit},
            "gross_spend_minor": {"used": str(row.gross_spend_minor_used), "limit": str(row.gross_spend_minor_limit)},
            "committed_value_minor": {"used": str(row.committed_value_minor_used), "limit": str(row.committed_value_minor_limit)},
        },
    }


def _job_json(row: EconomicJob) -> dict[str, Any]:
    return {
        "id": row.id, "mandate_id": row.mandate_id, "kind": row.kind,
        "action": row.action, "title": row.title, "state": row.state,
        "proposal": row.proposal_json, "result": row.result_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _approval_json(row: EconomicApprovalReceipt) -> dict[str, Any]:
    return {
        "id": row.id, "mandate_id": row.mandate_id, "job_id": row.job_id,
        "action": row.action, "decision": row.decision,
        "mandate_digest": row.mandate_digest,
        "exact_request_digest": row.exact_request_digest, "actor": row.actor,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    }


def setup_economic_routes(*, session_factory=SessionLocal):
    router = APIRouter(prefix="/api/economic", tags=["economic-control"])

    async def transact(owner: str, operation: Callable[[EconomicStore], Any]):
        def run():
            with session_factory() as db:
                try:
                    return operation(EconomicStore(db))
                except Exception:
                    db.rollback()
                    raise
        try:
            return await asyncio.to_thread(run)
        except EconomicStoreError as exc:
            raise _safe_error(exc) from exc

    @router.get("/status")
    async def status(request: Request):
        owner = _owner(request)
        def read(store):
            controls = store.get_controls(owner=owner)
            active = store.db.query(EconomicMandateRecord).filter_by(owner=owner, status="active").count()
            return {"kill_switch_engaged": controls.kill_switch_engaged,
                    "revision": controls.revision, "active_mandates": active,
                    "external_execution_available": False}
        return await transact(owner, read)

    @router.put("/kill-switch")
    async def set_kill_switch(request: Request, payload: dict = Body(...)):
        owner = _owner(request)
        row = await transact(owner, lambda store: store.set_kill_switch(
            owner=owner, engaged=payload.get("engaged"),
            expected_revision=payload.get("expected_revision"),
        ))
        return {"kill_switch_engaged": row.kill_switch_engaged, "revision": row.revision}

    @router.post("/mandates", status_code=201)
    async def create_mandate(request: Request, payload: dict = Body(...)):
        owner, now = _owner(request), int(time.time())
        try:
            duration = payload.get("duration_seconds", 3600)
            if type(duration) is not int:
                raise ValueError("invalid duration")
            budgets = payload.get("budgets", {})
            if not isinstance(budgets, dict):
                raise ValueError("invalid budgets")
            mandate = EconomicMandate.create(
                mandate_id=payload.get("id") or uuid.uuid4().hex, owner=owner,
                autonomy_tier=payload.get("autonomy_tier", "off"),
                allowed_actions=payload.get("allowed_actions", []),
                budgets=BudgetLimits(**budgets), issued_at=now, expires_at=now + duration,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "Economic request was rejected") from exc
        return _mandate_json(await transact(owner, lambda store: store.create_mandate(mandate)))

    @router.get("/mandates")
    async def list_mandates(request: Request, status: str | None = None,
                            limit: int = Query(100, ge=1, le=500)):
        owner = _owner(request)
        def read(store):
            query = store.db.query(EconomicMandateRecord).filter_by(owner=owner)
            if status is not None:
                if status not in {"inactive", "active", "revoked", "expired"}:
                    raise EconomicStoreError("invalid mandate status")
                query = query.filter_by(status=status)
            return [_mandate_json(row) for row in query.order_by(EconomicMandateRecord.created_at.desc()).limit(limit)]
        return {"mandates": await transact(owner, read)}

    @router.get("/mandates/{mandate_id}")
    async def get_mandate(request: Request, mandate_id: str):
        owner = _owner(request)
        return _mandate_json(await transact(owner, lambda store: store._mandate(owner, mandate_id)))

    @router.post("/mandates/{mandate_id}/activate")
    async def activate_mandate(request: Request, mandate_id: str):
        owner = _owner(request)
        return _mandate_json(await transact(owner, lambda store: store.activate_mandate(owner=owner, mandate_id=mandate_id)))

    @router.post("/mandates/{mandate_id}/revoke")
    async def revoke_mandate(request: Request, mandate_id: str):
        owner = _owner(request)
        return _mandate_json(await transact(owner, lambda store: store.revoke_mandate(owner=owner, mandate_id=mandate_id)))

    @router.get("/mandates/{mandate_id}/usage")
    async def mandate_usage(request: Request, mandate_id: str):
        owner = _owner(request)
        return _mandate_json(await transact(owner, lambda store: store._mandate(owner, mandate_id)))["budgets"]

    @router.post("/jobs", status_code=201)
    async def create_job(request: Request, payload: dict = Body(...)):
        owner = _owner(request)
        row = await transact(owner, lambda store: store.create_job(
            owner=owner, mandate_id=payload.get("mandate_id"), action=payload.get("action"),
            title=payload.get("title"), proposal=payload.get("proposal"),
            idempotency_key=payload.get("idempotency_key"), kind=payload.get("kind", "job"),
        ))
        return _job_json(row)

    @router.get("/jobs")
    async def list_jobs(request: Request, state: str | None = None,
                        limit: int = Query(100, ge=1, le=500)):
        owner = _owner(request)
        def read(store):
            query = store.db.query(EconomicJob).filter_by(owner=owner)
            if state is not None:
                if state not in {"proposed", "prepared", "awaiting_approval", "approved",
                                 "executing", "completed", "failed", "cancelled"}:
                    raise EconomicStoreError("invalid job state")
                query = query.filter_by(state=state)
            return [_job_json(row) for row in query.order_by(EconomicJob.created_at.desc()).limit(limit)]
        return {"jobs": await transact(owner, read)}

    @router.get("/jobs/{job_id}")
    async def get_job(request: Request, job_id: str):
        owner = _owner(request)
        def read(store):
            row = store.db.query(EconomicJob).filter_by(id=job_id, owner=owner).one_or_none()
            if row is None:
                raise EconomicStoreError("economic job not found")
            return _job_json(row)
        return await transact(owner, read)

    @router.post("/jobs/{job_id}/transition")
    async def transition_job(request: Request, job_id: str, payload: dict = Body(...)):
        owner = _owner(request)
        expected, target = payload.get("expected_state"), payload.get("new_state")
        def change(store):
            # The only path into approved is record_approval(), which binds a
            # durable receipt to the exact persisted proposal digest.
            if target == "approved":
                raise EconomicStoreError("direct job approval is not permitted")
            if target == "executing":
                controls = store.get_controls(owner=owner)
                job = store.db.query(EconomicJob).filter_by(id=job_id, owner=owner).one_or_none()
                if job is None:
                    raise EconomicStoreError("economic job not found")
                mandate = store._mandate(owner, job.mandate_id)
                decision = evaluate_economic_action(
                    store._policy_mandate(mandate), job.action,
                    usage_after_action=BudgetUsage(
                        external_actions=mandate.external_actions_used,
                        messages=mandate.messages_used, submissions=mandate.submissions_used,
                        gross_spend_minor=int(mandate.gross_spend_minor_used),
                        committed_value_minor=int(mandate.committed_value_minor_used),
                    ), controls=EconomicRuntimeControls(
                        kill_switch_engaged=controls.kill_switch_engaged), owner=owner,
                )
                if decision.requires_approval:
                    approved = store.db.query(EconomicApprovalReceipt).filter_by(
                        owner=owner, job_id=job_id, decision="approved",
                        mandate_digest=mandate.digest, action=job.action,
                    ).one_or_none()
                    if approved is None:
                        raise EconomicStoreError("exact durable approval is required")
                elif not decision.allowed:
                    raise EconomicStoreError(decision.reason)
            return _job_json(store.transition_job(owner=owner, job_id=job_id,
                                                   expected_state=expected, new_state=target))
        return await transact(owner, change)

    @router.post("/jobs/{job_id}/approval", status_code=201)
    async def approve_job(request: Request, job_id: str, payload: dict = Body(...)):
        owner = _owner(request)
        receipt = await transact(owner, lambda store: store.record_approval(
            owner=owner, job_id=job_id, decision=payload.get("decision"), actor=owner,
            exact_request=payload.get("exact_request"),
            idempotency_key=payload.get("idempotency_key"),
        ))
        return _approval_json(receipt)

    @router.get("/jobs/{job_id}/approvals")
    async def list_job_approvals(request: Request, job_id: str):
        owner = _owner(request)
        def read(store):
            job = store.db.query(EconomicJob.id).filter_by(id=job_id, owner=owner).one_or_none()
            if job is None:
                raise EconomicStoreError("economic job not found")
            rows = store.db.query(EconomicApprovalReceipt).filter_by(
                owner=owner, job_id=job_id,
            ).order_by(EconomicApprovalReceipt.decided_at.asc()).all()
            return [_approval_json(row) for row in rows]
        return {"approvals": await transact(owner, read)}

    @router.post("/usage", status_code=201)
    async def reserve_usage(request: Request, payload: dict = Body(...)):
        owner = _owner(request)
        try:
            delta = UsageDelta(
                external_actions=payload.get("external_actions", 0),
                messages=payload.get("messages", 0), submissions=payload.get("submissions", 0),
                gross_spend_minor=_money(payload.get("gross_spend_minor", 0), "gross spend"),
                committed_value_minor=_money(payload.get("committed_value_minor", 0), "committed value"),
            )
        except EconomicStoreError as exc:
            raise _safe_error(exc) from exc
        row = await transact(owner, lambda store: store.reserve_usage(
            owner=owner, mandate_id=payload.get("mandate_id"), action=payload.get("action"),
            delta=delta, idempotency_key=payload.get("idempotency_key"), job_id=payload.get("job_id"),
        ))
        return {"id": row.id, "mandate_id": row.mandate_id, "job_id": row.job_id,
                "external_actions": row.external_actions_delta, "messages": row.messages_delta,
                "submissions": row.submissions_delta,
                "gross_spend_minor": str(row.gross_spend_minor_delta),
                "committed_value_minor": str(row.committed_value_minor_delta)}

    return router
