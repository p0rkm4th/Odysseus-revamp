"""Transactional state for Telegram pairing and replay protection.

This module stores no bot token and performs no network or agent operation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from core.telegram_models import (
    TelegramApprovalCallback, TelegramConnection, TelegramMediaReceipt,
    TelegramPairingCode, TelegramSession, TelegramUpdateReceipt,
)

_USERNAME = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_FILE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,256}$")
_OPAQUE = re.compile(r"^[A-Za-z0-9_-]{16,32}$")


class TelegramStoreError(ValueError):
    pass


@dataclass(frozen=True)
class IssuedPairingCode:
    code: str
    expires_at: datetime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _required(value: str, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise TelegramStoreError(f"valid {label} is required")
    return value


def _numeric_id(value: int, label: str) -> int:
    if type(value) is not int or value <= 0 or value > 9_223_372_036_854_775_807:
        raise TelegramStoreError(f"{label} must be a positive numeric Telegram ID")
    return value


def _hash_secret(secret: str, salt_hex: str) -> str:
    return hashlib.scrypt(
        secret.encode("ascii"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32,
    ).hex()


def _payload_digest(payload: object) -> str:
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    except (TypeError, ValueError) as exc:
        raise TelegramStoreError("update payload must be canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


class TelegramStore:
    def __init__(self, db):
        self.db = db

    def issue_pairing_code(
        self, *, owner: str, lifetime_seconds: int = 600, now: datetime | None = None,
    ) -> IssuedPairingCode:
        owner = _required(owner, "owner", maximum=128)
        if type(lifetime_seconds) is not int or not 60 <= lifetime_seconds <= 900:
            raise TelegramStoreError("pairing lifetime must be between 60 and 900 seconds")
        if self.db.query(TelegramConnection).filter_by(owner=owner, active=1).one_or_none():
            raise TelegramStoreError("owner already has an active Telegram connection")
        timestamp = now or _utcnow()
        # Keep at most one usable code per owner.  Revocation is represented by
        # ``used_at`` so code material remains auditable without storing it in
        # plaintext or deleting lifecycle evidence.
        self.db.execute(update(TelegramPairingCode).where(
            TelegramPairingCode.owner == owner,
            TelegramPairingCode.used_at.is_(None),
        ).values(used_at=timestamp))
        pair_id = secrets.token_urlsafe(6)
        secret = secrets.token_urlsafe(10)
        salt = secrets.token_hex(16)
        expires_at = timestamp + timedelta(seconds=lifetime_seconds)
        self.db.add(TelegramPairingCode(
            id=pair_id, owner=owner, salt=salt, code_hash=_hash_secret(secret, salt),
            expires_at=expires_at, attempts=0,
        ))
        self.db.commit()
        return IssuedPairingCode(code=f"{pair_id}.{secret}", expires_at=expires_at)

    def revoke_pairing_codes(self, *, owner: str, now: datetime | None = None) -> int:
        """Invalidate every unclaimed code for an owner without deleting audit state."""
        owner = _required(owner, "owner", maximum=128)
        revoked = self.db.execute(update(TelegramPairingCode).where(
            TelegramPairingCode.owner == owner,
            TelegramPairingCode.used_at.is_(None),
        ).values(used_at=now or _utcnow()))
        self.db.commit()
        return int(revoked.rowcount)

    def lifecycle_status(self, *, owner: str, now: datetime | None = None) -> dict:
        """Return an owner-safe lifecycle projection; never return credential material."""
        owner = _required(owner, "owner", maximum=128)
        timestamp = now or _utcnow()
        connection = self.db.query(TelegramConnection).filter_by(owner=owner).one_or_none()
        pending = self.db.query(TelegramPairingCode).filter(
            TelegramPairingCode.owner == owner,
            TelegramPairingCode.used_at.is_(None),
            TelegramPairingCode.expires_at > timestamp,
        ).order_by(TelegramPairingCode.expires_at.desc()).first()
        sessions = []
        if connection is not None and connection.active:
            rows = self.db.query(TelegramSession).filter_by(
                owner=owner, connection_id=connection.id,
            ).order_by(TelegramSession.created_at.asc()).all()
            sessions = [{
                "odysseus_session_id": row.odysseus_session_id,
                "telegram_chat_id": row.telegram_chat_id,
                "revision": row.revision,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            } for row in rows]
        return {
            "connected": bool(connection is not None and connection.active),
            "telegram_user_id": connection.telegram_user_id if connection is not None and connection.active else None,
            "display_username": connection.display_username if connection is not None and connection.active else None,
            "pending_pairing": pending is not None,
            "pairing_expires_at": pending.expires_at if pending is not None else None,
            "sessions": sessions,
        }

    def disconnect(self, *, owner: str, now: datetime | None = None) -> bool:
        """Deactivate an owner's connection and revoke pending remote approvals."""
        owner = _required(owner, "owner", maximum=128)
        timestamp = now or _utcnow()
        connection = self.db.query(TelegramConnection).filter_by(owner=owner, active=1).one_or_none()
        self.revoke_pairing_codes(owner=owner, now=timestamp)
        if connection is None:
            return False
        connection.active = 0
        self.db.execute(update(TelegramApprovalCallback).where(
            TelegramApprovalCallback.owner == owner,
            TelegramApprovalCallback.consumed_at.is_(None),
        ).values(consumed_at=timestamp))
        self.db.commit()
        return True

    def claim_pairing_code(
        self, *, code: str, telegram_user_id: int, private_chat_id: int,
        display_username: str | None = None, now: datetime | None = None,
    ) -> TelegramConnection:
        code = _required(code, "pairing code", maximum=64)
        telegram_user_id = _numeric_id(telegram_user_id, "Telegram user ID")
        private_chat_id = _numeric_id(private_chat_id, "Telegram private chat ID")
        if telegram_user_id != private_chat_id:
            raise TelegramStoreError("pairing is allowed only from the user's private chat")
        if display_username is not None and not _USERNAME.fullmatch(display_username):
            raise TelegramStoreError("invalid display username")
        try:
            pair_id, secret = code.split(".", 1)
        except ValueError as exc:
            raise TelegramStoreError("invalid or expired pairing code") from exc
        if not pair_id or not secret or len(secret) > 32:
            raise TelegramStoreError("invalid or expired pairing code")
        row = self.db.get(TelegramPairingCode, pair_id)
        timestamp = now or _utcnow()
        if row is None or row.used_at is not None or row.expires_at <= timestamp or row.attempts >= 8:
            raise TelegramStoreError("invalid or expired pairing code")
        valid = hmac.compare_digest(_hash_secret(secret, row.salt), row.code_hash)
        if not valid:
            self.db.execute(update(TelegramPairingCode).where(
                TelegramPairingCode.id == row.id, TelegramPairingCode.used_at.is_(None),
                TelegramPairingCode.attempts < 8,
            ).values(attempts=TelegramPairingCode.attempts + 1))
            self.db.commit()
            raise TelegramStoreError("invalid or expired pairing code")
        existing_id = self.db.query(TelegramConnection).filter_by(
            telegram_user_id=telegram_user_id,
        ).one_or_none()
        existing_owner = self.db.query(TelegramConnection).filter_by(owner=row.owner).one_or_none()
        reconnect = (
            existing_owner is not None
            and not existing_owner.active
            and existing_owner.telegram_user_id == telegram_user_id
            and (existing_id is None or existing_id.id == existing_owner.id)
        )
        if (existing_id or existing_owner) and not reconnect:
            raise TelegramStoreError("Telegram identity or owner is already paired")
        claimed = self.db.execute(update(TelegramPairingCode).where(
            TelegramPairingCode.id == row.id,
            TelegramPairingCode.used_at.is_(None),
            TelegramPairingCode.expires_at > timestamp,
            TelegramPairingCode.attempts < 8,
        ).values(used_at=timestamp))
        if claimed.rowcount != 1:
            self.db.rollback()
            raise TelegramStoreError("invalid or expired pairing code")
        if reconnect:
            connection = existing_owner
            connection.active = 1
            connection.display_username = display_username
        else:
            connection = TelegramConnection(
                id=uuid.uuid4().hex, owner=row.owner, telegram_user_id=telegram_user_id,
                display_username=display_username, active=1,
            )
            self.db.add(connection)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise TelegramStoreError("Telegram identity or owner is already paired") from exc
        return connection

    def require_connection(self, *, owner: str, telegram_user_id: int) -> TelegramConnection:
        owner = _required(owner, "owner", maximum=128)
        telegram_user_id = _numeric_id(telegram_user_id, "Telegram user ID")
        row = self.db.query(TelegramConnection).filter_by(
            owner=owner, telegram_user_id=telegram_user_id, active=1,
        ).one_or_none()
        if row is None:
            raise TelegramStoreError("active Telegram connection not found")
        return row

    def bind_session(
        self, *, owner: str, telegram_user_id: int, private_chat_id: int,
        odysseus_session_id: str,
    ) -> TelegramSession:
        connection = self.require_connection(owner=owner, telegram_user_id=telegram_user_id)
        private_chat_id = _numeric_id(private_chat_id, "Telegram private chat ID")
        if private_chat_id != telegram_user_id:
            raise TelegramStoreError("group and channel sessions are not supported")
        session_id = _required(odysseus_session_id, "Odysseus session ID", maximum=128)
        existing = self.db.query(TelegramSession).filter_by(
            connection_id=connection.id, telegram_chat_id=private_chat_id,
        ).one_or_none()
        if existing:
            if existing.owner != owner:
                raise TelegramStoreError("session owner mismatch")
            if existing.odysseus_session_id != session_id:
                raise TelegramStoreError("Telegram session is already bound")
            return existing
        row = TelegramSession(
            id=uuid.uuid4().hex, owner=owner, connection_id=connection.id,
            telegram_chat_id=private_chat_id, odysseus_session_id=session_id,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def get_session(
        self, *, owner: str, telegram_user_id: int, private_chat_id: int,
    ) -> TelegramSession | None:
        """Return the owner-bound private session, if one has been configured."""
        connection = self.require_connection(owner=owner, telegram_user_id=telegram_user_id)
        private_chat_id = _numeric_id(private_chat_id, "Telegram private chat ID")
        if private_chat_id != telegram_user_id:
            raise TelegramStoreError("group and channel sessions are not supported")
        return self.db.query(TelegramSession).filter_by(
            owner=owner, connection_id=connection.id, telegram_chat_id=private_chat_id,
        ).one_or_none()

    def advance_session_revision(
        self, *, owner: str, telegram_user_id: int, private_chat_id: int,
        expected_revision: int,
    ) -> TelegramSession:
        """Acquire the next durable serialization position using compare-and-swap."""
        connection = self.require_connection(owner=owner, telegram_user_id=telegram_user_id)
        private_chat_id = _numeric_id(private_chat_id, "Telegram private chat ID")
        if private_chat_id != telegram_user_id:
            raise TelegramStoreError("group and channel sessions are not supported")
        if type(expected_revision) is not int or expected_revision < 0:
            raise TelegramStoreError("valid expected session revision is required")
        advanced = self.db.execute(update(TelegramSession).where(
            TelegramSession.owner == owner,
            TelegramSession.connection_id == connection.id,
            TelegramSession.telegram_chat_id == private_chat_id,
            TelegramSession.revision == expected_revision,
        ).values(revision=TelegramSession.revision + 1))
        if advanced.rowcount != 1:
            self.db.rollback()
            raise TelegramStoreError("Telegram session revision conflict")
        self.db.commit()
        return self.db.query(TelegramSession).filter_by(
            owner=owner, connection_id=connection.id, telegram_chat_id=private_chat_id,
        ).one()

    def record_update(
        self, *, owner: str, telegram_user_id: int, update_id: int, payload: object,
    ) -> bool:
        connection = self.require_connection(owner=owner, telegram_user_id=telegram_user_id)
        if type(update_id) is not int or update_id < 0:
            raise TelegramStoreError("update ID must be a non-negative integer")
        digest = _payload_digest(payload)
        existing = self.db.query(TelegramUpdateReceipt).filter_by(
            connection_id=connection.id, update_id=update_id,
        ).one_or_none()
        if existing:
            if existing.payload_digest != digest:
                raise TelegramStoreError("update ID replayed with different content")
            return False
        self.db.add(TelegramUpdateReceipt(
            id=uuid.uuid4().hex, owner=owner, connection_id=connection.id,
            update_id=update_id, payload_digest=digest,
        ))
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.db.query(TelegramUpdateReceipt).filter_by(
                connection_id=connection.id, update_id=update_id,
            ).one_or_none()
            if existing and existing.payload_digest == digest:
                return False
            raise TelegramStoreError("update ID replayed with different content")
        return True

    def record_media(
        self, *, owner: str, telegram_user_id: int, update_id: int, file_id: str,
        file_unique_id: str, media_kind: str, mime_type: str | None = None,
        byte_size: int | None = None,
    ) -> TelegramMediaReceipt:
        connection = self.require_connection(owner=owner, telegram_user_id=telegram_user_id)
        if type(update_id) is not int or update_id < 0:
            raise TelegramStoreError("invalid media update ID")
        if not _FILE_TOKEN.fullmatch(file_id) or not _FILE_TOKEN.fullmatch(file_unique_id):
            raise TelegramStoreError("invalid Telegram file identifier")
        if media_kind not in {"photo", "voice", "document"}:
            raise TelegramStoreError("unsupported Telegram media kind")
        if mime_type is not None and (not mime_type or len(mime_type) > 128 or any(c.isspace() for c in mime_type)):
            raise TelegramStoreError("invalid media MIME type")
        if byte_size is not None and (type(byte_size) is not int or not 0 <= byte_size <= 25 * 1024 * 1024):
            raise TelegramStoreError("Telegram media exceeds the metadata size limit")
        row = TelegramMediaReceipt(
            id=uuid.uuid4().hex, owner=owner, connection_id=connection.id,
            update_id=update_id, file_id=file_id, file_unique_id=file_unique_id,
            media_kind=media_kind, mime_type=mime_type, byte_size=byte_size,
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.db.query(TelegramMediaReceipt).filter_by(
                connection_id=connection.id, update_id=update_id,
                file_unique_id=file_unique_id,
            ).one_or_none()
            if existing:
                expected = (file_id, media_kind, mime_type, byte_size)
                actual = (existing.file_id, existing.media_kind, existing.mime_type, existing.byte_size)
                if actual == expected:
                    return existing
                raise TelegramStoreError("media identity was replayed with different metadata")
            raise
        return row

    def create_approval_callback(
        self, *, owner: str, telegram_user_id: int, private_chat_id: int,
        odysseus_session_id: str, approval_digest: str, allowed_decision: str,
        lifetime_seconds: int = 300, now: datetime | None = None,
    ) -> TelegramApprovalCallback:
        connection = self.require_connection(owner=owner, telegram_user_id=telegram_user_id)
        private_chat_id = _numeric_id(private_chat_id, "Telegram private chat ID")
        if private_chat_id != telegram_user_id:
            raise TelegramStoreError("approval callbacks are private-chat only")
        session_id = _required(odysseus_session_id, "Odysseus session ID", maximum=128)
        if not re.fullmatch(r"[0-9a-f]{64}", approval_digest):
            raise TelegramStoreError("approval digest must be an exact SHA-256 digest")
        if allowed_decision not in {"approve", "deny"}:
            raise TelegramStoreError("invalid callback decision")
        if type(lifetime_seconds) is not int or not 30 <= lifetime_seconds <= 600:
            raise TelegramStoreError("callback lifetime must be between 30 and 600 seconds")
        row = TelegramApprovalCallback(
            opaque_id=secrets.token_urlsafe(18), owner=owner, connection_id=connection.id,
            telegram_user_id=telegram_user_id, telegram_chat_id=private_chat_id,
            odysseus_session_id=session_id, approval_digest=approval_digest,
            allowed_decision=allowed_decision,
            expires_at=(now or _utcnow()) + timedelta(seconds=lifetime_seconds),
        )
        self.db.add(row)
        self.db.commit()
        return row

    def consume_approval_callback(
        self, *, owner: str, telegram_user_id: int, private_chat_id: int,
        callback_data: str, now: datetime | None = None,
    ) -> TelegramApprovalCallback:
        self.require_connection(owner=owner, telegram_user_id=telegram_user_id)
        private_chat_id = _numeric_id(private_chat_id, "Telegram private chat ID")
        if private_chat_id != telegram_user_id or not isinstance(callback_data, str) or not callback_data.startswith("a:"):
            raise TelegramStoreError("invalid approval callback")
        opaque_id = callback_data[2:]
        if not _OPAQUE.fullmatch(opaque_id):
            raise TelegramStoreError("invalid approval callback")
        timestamp = now or _utcnow()
        updated = self.db.execute(update(TelegramApprovalCallback).where(
            TelegramApprovalCallback.opaque_id == opaque_id,
            TelegramApprovalCallback.owner == owner,
            TelegramApprovalCallback.telegram_user_id == telegram_user_id,
            TelegramApprovalCallback.telegram_chat_id == private_chat_id,
            TelegramApprovalCallback.expires_at > timestamp,
            TelegramApprovalCallback.consumed_at.is_(None),
        ).values(consumed_at=timestamp))
        if updated.rowcount != 1:
            self.db.rollback()
            raise TelegramStoreError("invalid, expired, or already used approval callback")
        self.db.commit()
        return self.db.get(TelegramApprovalCallback, opaque_id)
