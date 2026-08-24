"""Versioned migrations for durable evaluation records."""
from sqlalchemy.engine import Connection
from core.evaluation_models import EVALUATION_TABLES
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration

EVALUATION_V1_VERSION = "20260824_004_evaluation_corpus_v1"
EVALUATION_V1_DEFINITION = """evaluation-corpus-v1
owner-scoped-scenarios-trajectory-runs-supervised-failures
sanitized-expected-properties-not-exact-prose
"""
EVALUATION_V1_CHECKSUM = migration_checksum(EVALUATION_V1_DEFINITION)


def apply_evaluation_v1(connection: Connection) -> None:
    for table in EVALUATION_TABLES:
        table.create(bind=connection, checkfirst=True)


register_schema_migration(SchemaMigration(EVALUATION_V1_VERSION, EVALUATION_V1_CHECKSUM, apply_evaluation_v1))
