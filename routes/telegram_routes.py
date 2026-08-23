"""Authenticated, owner-scoped Telegram lifecycle controls.

This surface deliberately cannot accept bot tokens, claim pairing codes, start a
poller, invoke Telegram, process callbacks, or expose a webhook.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from core.database import SessionLocal
from core.telegram_models import TelegramConnection
from src.auth_helpers import require_user
from src.owner_identity import effective_storage_owner
from src.telegram_store import TelegramStore, TelegramStoreError


def _owner(request: Request) -> str:
    owner = effective_storage_owner(require_user(request))
    if not owner:
        raise HTTPException(401, "An authenticated Telegram owner is required")
    return owner


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def setup_telegram_routes(*, session_factory=SessionLocal, session_manager=None):
    router = APIRouter(prefix="/api/telegram", tags=["telegram"])

    async def transact(operation, **kwargs):
        def run():
            db = session_factory()
            try:
                return operation(TelegramStore(db), **kwargs)
            finally:
                db.close()

        try:
            return await asyncio.to_thread(run)
        except TelegramStoreError as exc:
            # Store errors are intentionally bounded validation/conflict text;
            # unexpected database details are not returned to clients.
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(500, "Telegram lifecycle operation failed") from exc

    @router.get("/status")
    async def status(request: Request):
        result = await transact(
            lambda store, **values: store.lifecycle_status(**values), owner=_owner(request),
        )
        return _json_safe(result)

    @router.post("/pairing-codes", status_code=201)
    async def create_pairing_code(request: Request, payload: dict[str, Any] = Body(default={})):
        unknown = set(payload) - {"lifetime_seconds"}
        if unknown:
            raise HTTPException(400, "unsupported pairing option")
        lifetime = payload.get("lifetime_seconds", 600)
        try:
            issued = await transact(
                lambda store, **values: store.issue_pairing_code(**values),
                owner=_owner(request), lifetime_seconds=lifetime,
            )
        except HTTPException as exc:
            if exc.status_code == 409 and "lifetime" in str(exc.detail):
                raise HTTPException(400, exc.detail) from exc
            raise
        return {"pairing_code": issued.code, "expires_at": issued.expires_at.isoformat()}

    @router.delete("/pairing-codes")
    async def revoke_pairing_codes(request: Request):
        count = await transact(
            lambda store, **values: store.revoke_pairing_codes(**values), owner=_owner(request),
        )
        return {"revoked": count > 0}

    @router.delete("/connection")
    async def disconnect(request: Request):
        disconnected = await transact(
            lambda store, **values: store.disconnect(**values), owner=_owner(request),
        )
        return {"disconnected": disconnected}

    @router.post("/session")
    async def bind_session(request: Request, payload: dict[str, Any] = Body(default={})):
        unknown = set(payload) - {"odysseus_session_id"}
        if unknown or not isinstance(payload.get("odysseus_session_id"), str):
            raise HTTPException(400, "a valid odysseus_session_id is required")
        if session_manager is None:
            raise HTTPException(503, "Telegram session binding is unavailable")
        owner = _owner(request)
        session_id = payload["odysseus_session_id"].strip()
        if not session_id or len(session_id) > 128:
            raise HTTPException(400, "a valid odysseus_session_id is required")
        try:
            session = await asyncio.to_thread(session_manager.get_session, session_id)
        except KeyError as exc:
            raise HTTPException(404, "Odysseus session was not found") from exc
        except Exception as exc:
            raise HTTPException(500, "Telegram session binding failed") from exc
        session_owner = str(getattr(session, "owner", "") or "").strip()
        if owner and session_owner and session_owner != owner:
            raise HTTPException(403, "Odysseus session belongs to another owner")

        def bind():
            db = session_factory()
            try:
                connection = db.query(TelegramConnection).filter_by(
                    owner=owner, active=1,
                ).one_or_none()
                if connection is None:
                    raise TelegramStoreError("active Telegram connection not found")
                return TelegramStore(db).bind_session(
                    owner=owner,
                    telegram_user_id=connection.telegram_user_id,
                    private_chat_id=connection.telegram_user_id,
                    odysseus_session_id=session_id,
                )
            finally:
                db.close()

        try:
            bound = await asyncio.to_thread(bind)
        except TelegramStoreError as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(500, "Telegram session binding failed") from exc
        return _json_safe({
            "odysseus_session_id": bound.odysseus_session_id,
            "telegram_chat_id": bound.telegram_chat_id,
            "revision": bound.revision,
        })

    return router
