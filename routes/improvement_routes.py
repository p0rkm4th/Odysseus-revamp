"""Authenticated metadata-only control plane for safe policy improvement.

This surface never accepts or resolves artifact content.  Candidates identify
separately reviewed immutable artifacts only by kind, version, and SHA-256.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from core.database import SessionLocal
from core.middleware import require_admin
from src.auth_helpers import require_user
from src.improvement_registry import (
    ConcurrentPromotionError,
    ImprovementRegistry,
    ImprovementRegistryError,
)


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateCreate(_ClosedModel):
    policy_key: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=128)
    parent_version: str | None = Field(default=None, max_length=128)
    artifact_kind: str
    artifact_digest: str = Field(min_length=64, max_length=64)
    source_failure_counts: dict[str, int] = Field(default_factory=dict)


class BenchmarkMetric(_ClosedModel):
    mean: float | None = None
    p50: float | None = None
    p95: float | None = None
    samples: int | None = None


class BenchmarkCase(_ClosedModel):
    case_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    category: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    passed: bool
    score: float


class BenchmarkSummary(_ClosedModel):
    schema_version: int
    suite: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    case_count: int
    record_count: int
    success_rate: float
    weighted_score: float
    category_scores: dict[str, float]
    failure_categories: dict[str, int]
    metrics: dict[str, BenchmarkMetric]
    cases: list[BenchmarkCase]

    @field_validator("category_scores", "metrics")
    @classmethod
    def closed_summary_keys(cls, value):
        if any(not isinstance(key, str) or not key or len(key) > 80
               or not key[0].islower()
               or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_.-" for char in key)
               for key in value):
            raise ValueError("summary keys must be lower-case identifiers")
        return value


class EvaluationCreate(_ClosedModel):
    baseline_report: BenchmarkSummary
    candidate_report: BenchmarkSummary


class PromoteRequest(_ClosedModel):
    approval_digest: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=200)


class RollbackRequest(_ClosedModel):
    target_candidate_id: str = Field(min_length=1, max_length=128)
    approval_digest: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=200)


def _admin_owner(request: Request) -> str:
    """Return the real, currently authenticated administrator identity."""
    actor = require_user(request)
    require_admin(request)
    if not actor or getattr(request.state, "api_token", False) or actor == "internal-tool":
        raise HTTPException(401, "A signed-in administrator is required")
    return actor


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def _candidate(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "policy_key": row.policy_key,
        "version": row.version,
        "parent_version": row.parent_version,
        "artifact_kind": row.artifact_kind,
        "artifact_digest": row.artifact_digest,
        "source_failure_counts": dict(row.source_failure_counts_json or {}),
        "created_by": row.created_by,
        "created_at": _iso(row.created_at),
    }


def _evaluation(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "candidate_id": row.candidate_id,
        "baseline_digest": row.baseline_digest,
        "candidate_report_digest": row.candidate_report_digest,
        "evidence_policy": row.evidence_policy_json,
        "verdict": row.verdict_json,
        "passed": bool(row.passed),
        "evaluated_at": _iso(row.evaluated_at),
    }


def _event(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "policy_key": row.policy_key,
        "event_type": row.event_type,
        "from_candidate_id": row.from_candidate_id,
        "to_candidate_id": row.to_candidate_id,
        "evaluation_id": row.evaluation_id,
        "approved_by": row.approved_by,
        "approval_digest": row.approval_digest,
        "idempotency_key": row.idempotency_key,
        "occurred_at": _iso(row.occurred_at),
    }


def _validate(model, payload: Any):
    """Validate without reflecting untrusted rejected values in an error."""
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(422, "Request does not match the closed metadata schema") from exc


def setup_improvement_routes(*, session_factory=SessionLocal, registry=None) -> APIRouter:
    """Build the router; callers explicitly register it with the application."""
    router = APIRouter(prefix="/api/admin/improvements", tags=["improvements"])
    service = registry or ImprovementRegistry(session_factory)

    async def call(method, **kwargs):
        try:
            return await asyncio.to_thread(method, **kwargs)
        except ConcurrentPromotionError as exc:
            raise HTTPException(409, "The active policy changed; refresh and approve the new switch") from exc
        except ImprovementRegistryError as exc:
            # Registry messages describe closed validation outcomes and never DB/provider details.
            raise HTTPException(400, str(exc)) from exc

    @router.get("/candidates")
    async def list_candidates(
        request: Request, policy_key: str | None = None,
        limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    ):
        owner = _admin_owner(request)
        rows = await call(service.list_candidates, owner=owner, policy_key=policy_key,
                          limit=limit, offset=offset)
        return {"candidates": [_candidate(row) for row in rows]}

    @router.post("/candidates", status_code=201)
    async def create_candidate(request: Request, payload: dict[str, Any]):
        owner = _admin_owner(request)
        payload = _validate(CandidateCreate, payload)
        row = await call(
            service.create_candidate, owner=owner, created_by=owner,
            **payload.model_dump(),
        )
        return {"candidate": _candidate(row)}

    @router.get("/candidates/{candidate_id}")
    async def inspect_candidate(request: Request, candidate_id: str):
        owner = _admin_owner(request)
        row = await call(service.get_candidate, owner=owner, candidate_id=candidate_id)
        if row is None:
            raise HTTPException(404, "Candidate not found")
        evaluations = await call(service.list_evaluations, owner=owner,
                                 candidate_id=candidate_id, limit=100)
        return {"candidate": _candidate(row), "evaluations": [_evaluation(item) for item in evaluations]}

    @router.post("/candidates/{candidate_id}/evaluations", status_code=201)
    async def record_evaluation(request: Request, candidate_id: str, payload: dict[str, Any]):
        owner = _admin_owner(request)
        payload = _validate(EvaluationCreate, payload)
        row = await call(
            service.record_evaluation, owner=owner, candidate_id=candidate_id,
            baseline_report=payload.baseline_report.model_dump(exclude_none=True),
            candidate_report=payload.candidate_report.model_dump(exclude_none=True),
        )
        return {"evaluation": _evaluation(row)}

    @router.get("/active/{policy_key}")
    async def active(request: Request, policy_key: str):
        owner = _admin_owner(request)
        row = await call(service.active_candidate, owner=owner, policy_key=policy_key)
        return {"candidate": _candidate(row) if row else None}

    @router.get("/history")
    async def history(request: Request, policy_key: str | None = None,
                      limit: int = Query(100, ge=1, le=500)):
        owner = _admin_owner(request)
        rows = await call(service.promotion_history, owner=owner,
                          policy_key=policy_key, limit=limit)
        return {"events": [_event(row) for row in rows]}

    @router.post("/evaluations/{evaluation_id}/promote")
    async def promote(request: Request, evaluation_id: str, payload: dict[str, Any]):
        owner = _admin_owner(request)
        payload = _validate(PromoteRequest, payload)
        row = await call(service.promote, owner=owner, evaluation_id=evaluation_id,
                         approved_by=owner, **payload.model_dump())
        return {"event": _event(row)}

    @router.post("/active/{policy_key}/rollback")
    async def rollback(request: Request, policy_key: str, payload: dict[str, Any]):
        owner = _admin_owner(request)
        payload = _validate(RollbackRequest, payload)
        row = await call(service.rollback, owner=owner, policy_key=policy_key,
                         approved_by=owner, **payload.model_dump())
        return {"event": _event(row)}

    return router
