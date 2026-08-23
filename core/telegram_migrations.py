"""Checksum-protected Telegram adapter schema."""

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration
from core.telegram_models import TELEGRAM_TABLES

TELEGRAM_V1_VERSION = "20260822_003_telegram_v1"
TELEGRAM_V1_DEFINITION = """telegram-v1
telegram_pairing_codes:salted-short-lived-one-use
telegram_connections:owner-and-numeric-user-unique
telegram_sessions:owner-connection-chat
telegram_update_receipts:durable-dedup
telegram_media_receipts:bounded-metadata
telegram_approval_callbacks:opaque-exact-expiring
outbound-long-poll:no-token-storage
"""
TELEGRAM_V1_CHECKSUM = migration_checksum(TELEGRAM_V1_DEFINITION)


def apply_telegram_v1(connection: Connection) -> None:
    for table in TELEGRAM_TABLES:
        table.create(bind=connection, checkfirst=True)
    inspector = inspect(connection)
    missing = [table.name for table in TELEGRAM_TABLES if not inspector.has_table(table.name)]
    if missing:
        raise RuntimeError(f"telegram v1 migration did not create tables: {', '.join(missing)}")


register_schema_migration(SchemaMigration(
    version=TELEGRAM_V1_VERSION,
    checksum=TELEGRAM_V1_CHECKSUM,
    apply=apply_telegram_v1,
))
