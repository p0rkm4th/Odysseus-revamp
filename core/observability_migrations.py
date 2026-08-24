"""Versioned migrations for the redacted trace projection."""
from sqlalchemy.engine import Connection
from core.observability_models import OBSERVABILITY_TABLES
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration

OBSERVABILITY_V1_VERSION = "20260824_005_observability_trace_v1"
OBSERVABILITY_V1_DEFINITION = """observability-v1
otel-shaped-redacted-trace-spans
bounded-owner-run-indexed-projection
"""
OBSERVABILITY_V1_CHECKSUM = migration_checksum(OBSERVABILITY_V1_DEFINITION)


def apply_observability_v1(connection: Connection) -> None:
    for table in OBSERVABILITY_TABLES:
        table.create(bind=connection, checkfirst=True)


register_schema_migration(SchemaMigration(OBSERVABILITY_V1_VERSION, OBSERVABILITY_V1_CHECKSUM, apply_observability_v1))
