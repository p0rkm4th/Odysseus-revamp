"""Authenticated Finance foundation APIs."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from core.database import SessionLocal, utcnow_naive
from core.finance_models import FinanceConnection, PlaidItem, PlaidLinkSession
from src.auth_helpers import require_user
from src.finance_service import FinanceError, FinanceService
from src.plaid_sync import PlaidSyncService
from src.plaid_transport import PlaidTransport, PlaidError
from src.owner_identity import effective_storage_owner
from src.plaid_config import public_status, save_configuration


def setup_finance_routes(*, session_factory=SessionLocal, plaid_transport_factory=PlaidTransport) -> APIRouter:
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

    def link_owner_id(owner_name: str) -> str:
        # Plaid requires a stable identifier but explicitly disallows PII.
        # A one-way digest keeps HADES usernames/emails out of provider logs.
        return hashlib.sha256(("hades-plaid-owner:" + owner_name).encode("utf-8")).hexdigest()[:32]

    def link_hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def is_admin(request: Request, user: str) -> bool:
        auth_manager = getattr(request.app.state, "auth_manager", None)
        return bool(auth_manager and auth_manager.is_admin(user))

    @router.get("/plaid/config")
    async def plaid_config_status(request: Request):
        user = owner(request)
        return {**public_status(), "can_configure": is_admin(request, user)}

    @router.put("/plaid/config")
    async def plaid_configure(request: Request, payload: dict[str, Any] = Body(...)):
        user = owner(request)
        if not is_admin(request, user):
            raise HTTPException(403, "Only an administrator can configure Plaid application credentials")
        try:
            return await asyncio.to_thread(
                save_configuration,
                client_id=payload.get("client_id", ""),
                secret=payload.get("secret", ""),
                environment=payload.get("environment", "sandbox"),
                client_name=payload.get("client_name", "HADES"),
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/plaid/link-token")
    async def plaid_link_token(request: Request):
        user = owner(request)
        requested_connection = str(request.query_params.get("connection_id") or "").strip() or None

        def run():
            transport = plaid_transport_factory()
            with session_factory() as db:
                connection = db.query(FinanceConnection).filter_by(id=requested_connection, owner=user, provider="plaid").one_or_none() if requested_connection else None
                if requested_connection and connection is None:
                    raise FinanceError("Finance connection is unavailable")
                access_token = None
                mode = "create"
                if connection:
                    item = db.query(PlaidItem).filter_by(connection_id=connection.id, owner=user, provider="plaid").one_or_none()
                    if item is not None:
                        mode = "update"
                        access_token = item.access_token
                if connection is None:
                    connection = FinanceConnection(id=secrets.token_hex(16), owner=user, provider="plaid", lifecycle_state="AUTHORIZATION_REQUIRED")
                    db.add(connection); db.flush()
                state = secrets.token_urlsafe(32)
                connection.lifecycle_state = "AUTHORIZATION_IN_PROGRESS"
                connection.authorization_correlation_hash = link_hash(state)
                connection.authorization_expires_at = utcnow_naive() + timedelta(minutes=30)
                db.commit()
                connection_id = connection.id
            try:
                body = transport.link_token_create(link_owner_id(user), access_token=access_token)
            except PlaidError as exc:
                with session_factory() as db:
                    failed = db.query(FinanceConnection).filter_by(id=connection_id, owner=user, provider="plaid").one_or_none()
                    if failed is not None:
                        failed.lifecycle_state = "RECONNECT_REQUIRED" if mode == "update" else "AUTHORIZATION_REQUIRED"
                        failed.provider_health = "DEGRADED"
                        failed.capability_available = False
                        failed.last_error_classification = exc.classification[:128]
                        failed.authorization_correlation_hash = None
                        failed.authorization_expires_at = None
                        db.commit()
                raise
            link_token = str(body.get("link_token") or "").strip()
            if not link_token:
                raise PlaidError("MALFORMED_PROVIDER_RESPONSE")
            now = utcnow_naive()
            with session_factory() as db:
                # Expired/consumed rows are harmless historical evidence but
                # should not accumulate on repeated Link opens.
                db.query(PlaidLinkSession).filter(
                    PlaidLinkSession.owner == user,
                    (PlaidLinkSession.expires_at < now) | PlaidLinkSession.consumed_at.is_not(None),
                ).delete(synchronize_session=False)
                row = PlaidLinkSession(
                    id=secrets.token_hex(16),
                    owner=user,
                    connection_id=connection_id,
                    link_token_hash=link_hash(link_token),
                    authorization_state_hash=link_hash(state),
                    mode=mode,
                    continuation={"kind": "finance.plaid.connect", "connection_id": connection_id},
                    expires_at=now + timedelta(minutes=30),
                )
                db.add(row)
                db.commit()
                expires_at = row.expires_at
            # The temporary Link token is intentionally the only secret in
            # this response; permanent access tokens never reach the browser.
            return {"link_token": link_token, "authorization_state": state, "connection_id": connection_id, "expires_at": expires_at.isoformat()}

        try:
            return await asyncio.to_thread(run)
        except (FinanceError, PlaidError) as exc:
            raise HTTPException(400 if isinstance(exc, FinanceError) else 503, str(exc)) from exc

    @router.post("/plaid/link-exchange")
    async def plaid_link_exchange(request: Request, payload: dict[str, Any] = Body(...)):
        user = owner(request)
        public_token = str(payload.get("public_token") or "").strip()
        link_token = str(payload.get("link_token") or "").strip()
        authorization_state = str(payload.get("authorization_state") or "").strip()
        if not link_token or not authorization_state:
            raise HTTPException(400, "link_token and authorization_state are required")

        def run():
            now = utcnow_naive()
            with session_factory() as db:
                row = db.query(PlaidLinkSession).filter(
                    PlaidLinkSession.owner == user,
                    PlaidLinkSession.link_token_hash == link_hash(link_token),
                    PlaidLinkSession.authorization_state_hash == link_hash(authorization_state),
                    PlaidLinkSession.consumed_at.is_(None),
                    PlaidLinkSession.expires_at > now,
                ).one_or_none()
                if row is None:
                    raise FinanceError("Plaid Link session is invalid or belongs to another owner")

                connection = db.query(FinanceConnection).filter_by(id=row.connection_id, owner=user, provider="plaid").one_or_none()
                if connection is None:
                    raise FinanceError("Plaid connection is unavailable")
                transport = plaid_transport_factory()
                item = db.query(PlaidItem).filter_by(connection_id=connection.id, owner=user, provider="plaid").one_or_none()
                if row.mode == "update":
                    if item is None:
                        raise FinanceError("Plaid reconnect target is unavailable")
                    item_id = item.item_id
                else:
                    # If a worker died after committing the credential but
                    # before consuming the continuation, the credential is a
                    # safe recovery point. Never exchange the public token a
                    # second time; resume from the committed item instead.
                    recovering_committed_item = item is not None and row.exchange_status in {"IN_PROGRESS", "UNCERTAIN"}
                    if not recovering_committed_item:
                        if row.exchange_status != "UNSTARTED":
                            raise FinanceError(
                                "Plaid authorization is already being completed or needs attention"
                            )
                        claimed = db.query(PlaidLinkSession).filter(
                            PlaidLinkSession.id == row.id,
                            PlaidLinkSession.exchange_status == "UNSTARTED",
                        ).update(
                            {"exchange_status": "IN_PROGRESS", "exchange_claimed_at": now},
                            synchronize_session=False,
                        )
                        if claimed != 1:
                            raise FinanceError(
                                "Plaid authorization is already being completed or needs attention"
                            )
                        db.commit()
                        db.refresh(row)
                        if not public_token:
                            raise FinanceError("public_token is required for a new Plaid connection")
                        try:
                            exchanged = transport.item_public_token_exchange(public_token)
                        except Exception as exc:
                            # The provider outcome is not safely knowable here.
                            # Preserve the claim so a callback replay cannot
                            # blindly dispatch the same public token again.
                            row.exchange_status = "UNCERTAIN"
                            row.consumed_at = now
                            classification = str(getattr(exc, "classification", "EXCHANGE_UNCERTAIN"))[:128]
                            connection.lifecycle_state = (
                                "RECONNECT_REQUIRED"
                                if classification in {"ITEM_LOGIN_REQUIRED", "ITEM_LOCKED", "INVALID_CREDENTIALS", "ACCESS_NOT_GRANTED"}
                                else "DEGRADED"
                            )
                            connection.provider_health = "RECONNECT_REQUIRED" if connection.lifecycle_state == "RECONNECT_REQUIRED" else "DEGRADED"
                            connection.capability_available = False
                            connection.last_error_classification = classification
                            db.commit()
                            raise
                        access_token = str(exchanged.get("access_token") or "").strip()
                        item_id = str(exchanged.get("item_id") or "").strip()
                        if not access_token or not item_id:
                            row.exchange_status = "UNCERTAIN"
                            row.consumed_at = now
                            connection.lifecycle_state = "DEGRADED"
                            connection.provider_health = "DEGRADED"
                            connection.capability_available = False
                            connection.last_error_classification = "MALFORMED_PROVIDER_RESPONSE"
                            db.commit()
                            raise PlaidError("MALFORMED_PROVIDER_RESPONSE")
                        FinanceService(db).create_plaid_item(user, item_id, access_token, connection_id=connection.id)
                        # The permanent credential is now committed. The
                        # following sync is a separate verifiable phase.
                        row.exchange_status = "COMPLETED"
                        db.commit()
                    else:
                        item_id = item.item_id
                # This is the existing bounded read-only reconciliation seam;
                # Link completion never grants a financial mutation.
                try:
                    sync_result = PlaidSyncService(db, transport).sync(user, item_id)
                except Exception:
                    # Exchange is a one-use provider operation. Even when the
                    # first sync fails, consume the Link continuation and let
                    # the canonical connection health/reconnect state describe
                    # the next safe action; never replay a public token blindly.
                    row.consumed_at = now
                    connection.authorization_correlation_hash = None
                    connection.authorization_expires_at = None
                    db.commit()
                    raise
                row.consumed_at = now
                row.exchange_status = "COMPLETED"
                connection.authorization_correlation_hash = None
                connection.authorization_expires_at = None
                db.commit()
                item_projection = next(
                    item for item in FinanceService(db).list_plaid_items(user)
                    if item["item_id"] == item_id
                )
                return {"item": item_projection, "sync": sync_result}

        try:
            return await asyncio.to_thread(run)
        except FinanceError as exc:
            raise HTTPException(400, str(exc)) from exc
        except PlaidError as exc:
            raise HTTPException(503, str(exc)) from exc

    @router.get("/accounts")
    async def accounts(request: Request):
        return {"accounts": await tx(request, lambda svc, user: svc.list_accounts(user))}

    @router.get("/transactions")
    async def transactions(request: Request):
        return {"transactions": await tx(request, lambda svc, user: svc.list_transactions(user))}

    @router.get("/coverage")
    async def coverage(request: Request):
        return await tx(request, lambda svc, user: svc.coverage(user))

    @router.get("/analysis/{action}")
    async def analysis(request: Request, action: str):
        params = dict(request.query_params)
        return await tx(request, lambda svc, user: svc.read_finance(user, action, params))

    @router.get("/plaid/items")
    async def plaid_items(request: Request):
        return {"items": await tx(request, lambda svc, user: svc.list_plaid_items(user))}

    @router.get("/plaid/connection")
    async def plaid_connection(request: Request):
        """Return the authenticated owner's canonical Plaid lifecycle projection."""
        return {"connection": await tx(request, lambda svc, user: svc.connection_projection(user))}

    @router.post("/plaid/items", status_code=201)
    async def plaid_item(request: Request, payload: dict[str, Any] = Body(...)):
        return {"item": await tx(request, lambda svc, user: svc.create_plaid_item(user, str(payload.get("item_id") or ""), str(payload.get("access_token") or ""), payload.get("institution_name")))}

    @router.post("/plaid/items/{item_id}/sync")
    async def plaid_sync(request: Request, item_id: str):
        user = owner(request)
        def run():
            with session_factory() as db:
                return PlaidSyncService(db, plaid_transport_factory()).sync(user, item_id)
        try:
            return await asyncio.to_thread(run)
        except (FinanceError, PlaidError) as exc:
            raise HTTPException(503 if isinstance(exc, PlaidError) else 400, str(exc)) from exc

    @router.post("/accounts/import", status_code=201)
    async def import_account(request: Request, payload: dict[str, Any] = Body(...)):
        return {"account": await tx(request, lambda svc, user: svc.import_account(user, payload))}

    @router.post("/transactions/import", status_code=201)
    async def import_transaction(request: Request, payload: dict[str, Any] = Body(...)):
        return {"transaction": await tx(request, lambda svc, user: svc.import_transaction(user, payload))}

    @router.post("/csv/import", status_code=201)
    async def import_csv(request: Request, payload: dict[str, Any] = Body(...)):
        """Import a bounded local CSV snapshot when Plaid is unavailable."""
        csv_text = str(payload.get("csv") or payload.get("csv_text") or "")
        return {"import": await tx(request, lambda svc, user: svc.import_csv(
            user, csv_text,
            account_name=str(payload.get("account_name") or "CSV Finance account"),
            currency=str(payload.get("currency") or "USD"),
            source_label=str(payload.get("source_label") or "local_csv"),
        ))}

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
