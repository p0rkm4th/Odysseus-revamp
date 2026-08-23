"""Durable owner-scoped state for the outbound-only Telegram adapter."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String,
    UniqueConstraint, event, inspect,
)

from core.database import Base, TimestampMixin, utcnow_naive


class TelegramPairingCode(TimestampMixin, Base):
    __tablename__ = "telegram_pairing_codes"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    salt = Column(String(64), nullable=False)
    code_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    __table_args__ = (
        CheckConstraint("attempts >= 0 AND attempts <= 8", name="ck_telegram_pair_attempts"),
        Index("ix_telegram_pair_owner_expiry", "owner", "expires_at"),
    )


class TelegramConnection(TimestampMixin, Base):
    __tablename__ = "telegram_connections"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, unique=True, index=True)
    telegram_user_id = Column(BigInteger, nullable=False, unique=True)
    display_username = Column(String(64), nullable=True)
    active = Column(Integer, nullable=False, default=1)
    __table_args__ = (
        CheckConstraint("telegram_user_id > 0", name="ck_telegram_connection_user_id"),
        CheckConstraint("active IN (0,1)", name="ck_telegram_connection_active"),
    )


class TelegramSession(TimestampMixin, Base):
    __tablename__ = "telegram_sessions"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    connection_id = Column(String, ForeignKey("telegram_connections.id", ondelete="CASCADE"), nullable=False)
    telegram_chat_id = Column(BigInteger, nullable=False)
    odysseus_session_id = Column(String, nullable=False)
    revision = Column(Integer, nullable=False, default=0)
    __table_args__ = (
        UniqueConstraint("connection_id", "telegram_chat_id", name="uq_telegram_session_connection_chat"),
        CheckConstraint("telegram_chat_id > 0", name="ck_telegram_session_private_chat"),
        CheckConstraint("revision >= 0", name="ck_telegram_session_revision"),
    )


class TelegramUpdateReceipt(Base):
    __tablename__ = "telegram_update_receipts"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    connection_id = Column(String, ForeignKey("telegram_connections.id", ondelete="CASCADE"), nullable=False)
    update_id = Column(BigInteger, nullable=False)
    payload_digest = Column(String(64), nullable=False)
    received_at = Column(DateTime, nullable=False, default=utcnow_naive)
    __table_args__ = (
        UniqueConstraint("connection_id", "update_id", name="uq_telegram_update_connection_id"),
        CheckConstraint("update_id >= 0", name="ck_telegram_update_id"),
    )


class TelegramMediaReceipt(Base):
    __tablename__ = "telegram_media_receipts"
    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    connection_id = Column(String, ForeignKey("telegram_connections.id", ondelete="CASCADE"), nullable=False)
    update_id = Column(BigInteger, nullable=False)
    file_id = Column(String(256), nullable=False)
    file_unique_id = Column(String(128), nullable=False)
    media_kind = Column(String(16), nullable=False)
    mime_type = Column(String(128), nullable=True)
    byte_size = Column(Integer, nullable=True)
    received_at = Column(DateTime, nullable=False, default=utcnow_naive)
    __table_args__ = (
        UniqueConstraint("connection_id", "update_id", "file_unique_id", name="uq_telegram_media_update_file"),
        CheckConstraint("media_kind IN ('photo','voice','document')", name="ck_telegram_media_kind"),
        CheckConstraint("byte_size IS NULL OR (byte_size >= 0 AND byte_size <= 26214400)", name="ck_telegram_media_size"),
    )


class TelegramApprovalCallback(TimestampMixin, Base):
    __tablename__ = "telegram_approval_callbacks"
    opaque_id = Column(String(32), primary_key=True)
    owner = Column(String, nullable=False, index=True)
    connection_id = Column(String, ForeignKey("telegram_connections.id", ondelete="CASCADE"), nullable=False)
    telegram_user_id = Column(BigInteger, nullable=False)
    telegram_chat_id = Column(BigInteger, nullable=False)
    odysseus_session_id = Column(String, nullable=False)
    approval_digest = Column(String(64), nullable=False)
    allowed_decision = Column(String(8), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    __table_args__ = (
        CheckConstraint("allowed_decision IN ('approve','deny')", name="ck_telegram_callback_decision"),
        Index("ix_telegram_callback_owner_expiry", "owner", "expires_at"),
    )


TELEGRAM_TABLES = tuple(model.__table__ for model in (
    TelegramPairingCode, TelegramConnection, TelegramSession,
    TelegramUpdateReceipt, TelegramMediaReceipt, TelegramApprovalCallback,
))


def _reject_identity_change(_mapper, _connection, target):
    state = inspect(target)
    identity_fields = {
        TelegramConnection: ("owner", "telegram_user_id"),
        TelegramSession: ("owner", "connection_id", "telegram_chat_id"),
    }[type(target)]
    if any(state.attrs[field].history.has_changes() for field in identity_fields):
        raise RuntimeError("Telegram numeric identity and owner bindings are immutable")


def _reject_receipt_change(*_args, **_kwargs):
    raise RuntimeError("Telegram update and media receipts are append-only")


for _identity_model in (TelegramConnection, TelegramSession):
    event.listen(_identity_model, "before_update", _reject_identity_change)
for _receipt_model in (TelegramUpdateReceipt, TelegramMediaReceipt):
    event.listen(_receipt_model, "before_update", _reject_receipt_change)
    event.listen(_receipt_model, "before_delete", _reject_receipt_change)
