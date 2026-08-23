"""Checksum-protected migration for the safe-improvement registry."""

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from core.improvement_models import IMPROVEMENT_TABLES
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration


IMPROVEMENT_V1_VERSION = "20260822_004_safe_improvement_v1"
IMPROVEMENT_V1_DEFINITION = """safe-improvement-v1
improvement_candidates:immutable-owner-policy-version-artifact-digest-failure-counts
improvement_evaluations:immutable-held-out-reports-policy-verdict-digests
active_improvement_policies:owner-policy-atomic-revision-pointer
improvement_promotion_events:immutable-human-approved-history-idempotency
"""
IMPROVEMENT_V1_CHECKSUM = migration_checksum(IMPROVEMENT_V1_DEFINITION)


def apply_improvement_v1(connection: Connection) -> None:
    for table in IMPROVEMENT_TABLES:
        table.create(bind=connection, checkfirst=True)
    inspector = inspect(connection)
    missing = [table.name for table in IMPROVEMENT_TABLES if not inspector.has_table(table.name)]
    if missing:
        raise RuntimeError(f"safe improvement v1 migration did not create tables: {', '.join(missing)}")


register_schema_migration(SchemaMigration(
    version=IMPROVEMENT_V1_VERSION,
    checksum=IMPROVEMENT_V1_CHECKSUM,
    apply=apply_improvement_v1,
))
