"""Authenticated Finance foundation APIs."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from core.database import SessionLocal
from src.auth_helpers import require_user
from src.finance_service import FinanceError, FinanceService
from src.owner_identity import effective_storage_owner


def setup_finance_routes(*, session_factory=SessionLocal) -> APIRouter:
    router = APIRouter(prefix="/api/finance", tags=["finance"])

    def owner(request: Request) -> str:
        value = effective_storage_owner(require_user(request))
        if not value:
            raise HTTPException(401, "an authenticated Finance owner is required")
        return value

    async def tx(request: Request, fn):
        value = owner(request)

        def run():
            with session_factory() as db:
                try:
                    return fn(FinanceService(db), value)
                except FinanceError:
                    db.rollback()
                    raise

        try:
            return await asyncio.to_thread(run)
        except FinanceError as exc:
            message = str(exc)
            status = 404 if "not found" in message or "membership" in message else 400
            raise HTTPException(status, message) from exc

    @router.get("/accounts")
    async def accounts(request: Request):
        return {"accounts": await tx(request, lambda svc, user: svc.list_accounts(user))}

    @router.get("/transactions")
    async def transactions(request: Request):
        return {"transactions": await tx(request, lambda svc, user: svc.list_transactions(user))}

    @router.post("/accounts/import", status_code=201)
    async def import_account(request: Request, payload: dict[str, Any] = Body(...)):
        return {"account": await tx(request, lambda svc, user: svc.import_account(user, payload))}

    @router.post("/transactions/import", status_code=201)
    async def import_transaction(request: Request, payload: dict[str, Any] = Body(...)):
        return {"transaction": await tx(request, lambda svc, user: svc.import_transaction(user, payload))}

    @router.get("/households/memberships")
    async def memberships(request: Request):
        return {"memberships": await tx(request, lambda svc, user: svc.list_memberships(user))}

    @router.post("/households", status_code=201)
    async def create_household(request: Request, payload: dict[str, Any] = Body(...)):
        return {"membership": await tx(
            request, lambda svc, user: svc.create_household(user, str(payload.get("name") or "")),
        )}

    @router.post("/households/{household_id}/members", status_code=201)
    async def add_member(request: Request, household_id: str, payload: dict[str, Any] = Body(...)):
        return {"membership": await tx(
            request,
            lambda svc, user: svc.add_member(user, household_id, str(payload.get("user_id") or "")),
        )}

    @router.get("/households/{household_id}/shared-expenses")
    async def shared_expenses(request: Request, household_id: str):
        return {"expenses": await tx(
            request, lambda svc, user: svc.list_shared_expenses(user, household_id),
        )}

    @router.post("/transactions/{transaction_id}/share", status_code=201)
    async def share_transaction(
        request: Request, transaction_id: str, payload: dict[str, Any] = Body(...),
    ):
        return {"expense": await tx(
            request,
            lambda svc, user: svc.share_transaction(
                user, transaction_id, str(payload.get("household_id") or ""),
                label=payload.get("label"), note=payload.get("note"),
            ),
        )}

    @router.delete("/shared-expenses/{shared_expense_id}", status_code=204)
    async def revoke_shared_expense(request: Request, shared_expense_id: str):
        await tx(request, lambda svc, user: svc.revoke_shared_expense(user, shared_expense_id))

    @router.get("/projection")
    async def projection(request: Request, household_id: str | None = None):
        return await tx(request, lambda svc, user: svc.read_projection(user, household_id))

    return router
