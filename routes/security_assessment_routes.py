"""Authenticated API for the bounded Security Assessments workspace."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from fastapi import APIRouter, Body, HTTPException, Query, Request

from core.database import SessionLocal
from core.security_assessment_models import SecurityFinding
from src.auth_helpers import require_user
from src.owner_identity import effective_storage_owner
from src.security_assessment import SecurityAssessmentError, SecurityAssessmentService, _serialize


def _owner(request: Request) -> tuple[str, str]:
    user = require_user(request)
    owner = effective_storage_owner(user)
    if not owner:
        raise HTTPException(401, "an authenticated assessment owner is required")
    return owner, user


def setup_security_assessment_routes(*, session_factory=SessionLocal):
    router = APIRouter(prefix="/api/security", tags=["security-assessment"])

    async def transact(operation: Callable[[SecurityAssessmentService, str, str], Any], request: Request):
        owner, user = _owner(request)
        def run():
            with session_factory() as db:
                try:
                    return operation(SecurityAssessmentService(db), owner, user)
                except Exception:
                    db.rollback()
                    raise
        try:
            return await asyncio.to_thread(run)
        except SecurityAssessmentError as exc:
            message = str(exc)
            status = 409 if any(word in message for word in ("authorized", "scope", "expired", "outside", "lifecycle", "not completable", "canonical target")) else 400
            raise HTTPException(status, message) from exc

    @router.get("/engagements")
    async def list_engagements(request: Request):
        return {"engagements": await transact(lambda svc, owner, user: svc.list_engagements(owner), request)}

    @router.post("/engagements", status_code=201)
    async def create_engagement(request: Request, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.create_engagement(owner, user, payload), request)

    @router.get("/engagements/{engagement_id}")
    async def get_engagement(request: Request, engagement_id: str):
        return await transact(lambda svc, owner, user: svc.get_engagement(owner, engagement_id), request)

    @router.post("/engagements/{engagement_id}/authorize")
    async def authorize(request: Request, engagement_id: str, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.authorize(owner, engagement_id, user, payload), request)

    @router.post("/engagements/{engagement_id}/scopes", status_code=201)
    async def add_scope(request: Request, engagement_id: str, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.add_scope(owner, engagement_id, payload), request)

    @router.post("/engagements/{engagement_id}/targets", status_code=201)
    async def add_target(request: Request, engagement_id: str, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.add_target(owner, engagement_id, payload), request)

    @router.post("/targets/{target_id}/revalidate")
    async def revalidate_target(request: Request, target_id: str):
        return await transact(lambda svc, owner, user: svc.revalidate_target(owner, target_id), request)

    @router.post("/engagements/{engagement_id}/runs/plan", status_code=201)
    async def plan_run(request: Request, engagement_id: str, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.plan_run(owner, user, engagement_id, payload), request)

    @router.post("/runs/{run_id}/complete")
    async def complete_run(request: Request, run_id: str, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.complete_run(owner, run_id, payload), request)

    @router.post("/runs/{run_id}/homelab-observation", status_code=201)
    async def ingest_homelab_observation(request: Request, run_id: str, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.ingest_homelab_observation(owner, user, run_id, payload), request)

    @router.post("/engagements/{engagement_id}/evidence", status_code=201)
    async def add_evidence(request: Request, engagement_id: str, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.add_evidence(owner, user, engagement_id, payload), request)

    @router.get("/findings")
    async def list_findings(request: Request, status: str | None = None, severity: str | None = None, limit: int = Query(100, ge=1, le=500)):
        def read(svc, owner, user):
            query = svc.db.query(SecurityFinding).filter_by(owner=owner)
            if status: query = query.filter_by(status=status)
            if severity: query = query.filter_by(severity=severity)
            return [_serialize(row) for row in query.order_by(SecurityFinding.updated_at.desc()).limit(limit).all()]
        return {"findings": await transact(read, request)}

    @router.post("/engagements/{engagement_id}/findings", status_code=201)
    async def add_finding(request: Request, engagement_id: str, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.add_finding(owner, user, engagement_id, payload), request)

    @router.patch("/findings/{finding_id}")
    async def update_finding(request: Request, finding_id: str, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.update_finding(owner, finding_id, payload), request)

    @router.post("/engagements/{engagement_id}/finding-candidates", status_code=201)
    async def propose_finding(request: Request, engagement_id: str, payload: dict[str, Any] = Body(...)):
        return await transact(lambda svc, owner, user: svc.propose_finding(owner, user, engagement_id, payload), request)

    @router.post("/finding-candidates/{candidate_id}/confirm")
    async def confirm_finding_candidate(request: Request, candidate_id: str):
        return await transact(lambda svc, owner, user: svc.confirm_candidate(owner, user, candidate_id), request)

    @router.post("/engagements/{engagement_id}/reports", status_code=201)
    async def generate_report(request: Request, engagement_id: str):
        return await transact(lambda svc, owner, user: svc.report(owner, user, engagement_id), request)

    return router
