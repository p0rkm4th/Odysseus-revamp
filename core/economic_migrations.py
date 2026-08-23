"""Checksum-protected schema migration for supervised economic work."""
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from core.economic_models import ECONOMIC_TABLES
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration

ECONOMIC_V1_VERSION = "20260822_002_economic_work_v1"
ECONOMIC_V1_DEFINITION = """economic-work-v1
economic_controls:default-kill-switch-engaged
economic_mandates:owner-digest-budget-counters
economic_jobs:owner-idempotent
economic_budget_usage:append-only-owner-idempotent
economic_approval_receipts:append-only-owner-idempotent
economic_audit_receipts:append-only-owner-idempotent
"""
ECONOMIC_V1_CHECKSUM = migration_checksum(ECONOMIC_V1_DEFINITION)

def apply_economic_v1(connection: Connection) -> None:
    for table in ECONOMIC_TABLES:
        table.create(bind=connection, checkfirst=True)
    inspector = inspect(connection)
    missing = [table.name for table in ECONOMIC_TABLES if not inspector.has_table(table.name)]
    if missing:
        raise RuntimeError(f"economic work v1 migration did not create tables: {', '.join(missing)}")

register_schema_migration(SchemaMigration(
    version=ECONOMIC_V1_VERSION, checksum=ECONOMIC_V1_CHECKSUM, apply=apply_economic_v1,
))
