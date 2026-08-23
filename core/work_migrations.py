"""Versioned migration for the domain-neutral Work Engine."""
from sqlalchemy.engine import Connection
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration
from core.work_models import WORK_TABLES

WORK_V1_VERSION = "20260823_005_work_engine_v1"
WORK_V1_DEFINITION = """work-engine-v1
goal-project-task-run-action-result-artifact-event-commitment
durable-resumption
domain-neutral-owner-scoped
"""
WORK_V1_CHECKSUM = migration_checksum(WORK_V1_DEFINITION)

def apply_work_v1(connection: Connection) -> None:
    for table in WORK_TABLES:
        table.create(bind=connection, checkfirst=True)

register_schema_migration(SchemaMigration(WORK_V1_VERSION, WORK_V1_CHECKSUM, apply_work_v1))
