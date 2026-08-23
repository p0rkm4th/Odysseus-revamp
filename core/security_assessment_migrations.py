"""Versioned schema for the bounded security assessment domain."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration
from core.security_assessment_models import SECURITY_ASSESSMENT_TABLES

SECURITY_ASSESSMENT_V1_VERSION = "20260823_003_security_assessment_v1"
SECURITY_ASSESSMENT_V1_DEFINITION = """security-assessment-v1
engagements:owner-authorization-lifecycle
authorizations:independent-validity
scopes:include-exclude-action-boundaries
targets:runs:evidence:findings:reports
no-exploit-no-credential-no-arbitrary-executor
"""
SECURITY_ASSESSMENT_V1_CHECKSUM = migration_checksum(SECURITY_ASSESSMENT_V1_DEFINITION)


def apply_security_assessment_v1(connection: Connection) -> None:
    for table in SECURITY_ASSESSMENT_TABLES:
        table.create(bind=connection, checkfirst=True)
    inspector = inspect(connection)
    missing = [table.name for table in SECURITY_ASSESSMENT_TABLES if not inspector.has_table(table.name)]
    if missing:
        raise RuntimeError("security assessment migration did not create tables: " + ", ".join(missing))


register_schema_migration(SchemaMigration(
    version=SECURITY_ASSESSMENT_V1_VERSION,
    checksum=SECURITY_ASSESSMENT_V1_CHECKSUM,
    apply=apply_security_assessment_v1,
))

SECURITY_ASSESSMENT_V2_VERSION = "20260823_004_security_assessment_context_v1"
SECURITY_ASSESSMENT_V2_DEFINITION = """security-assessment-context-v1
targets:cmdb-resolution-state-context-last-validated
evidence:cmdb-observation-reference
finding-candidates:explicit-review-confirmation
"""
SECURITY_ASSESSMENT_V2_CHECKSUM = migration_checksum(SECURITY_ASSESSMENT_V2_DEFINITION)


def apply_security_assessment_v2(connection: Connection) -> None:
    inspector = inspect(connection)
    columns = {
        "security_targets": {
            "resolution_state": "VARCHAR(32) NOT NULL DEFAULT 'external'",
            "canonical_context_json": "JSON NOT NULL DEFAULT '{}'",
            "last_validated_at": "DATETIME",
        },
        "security_evidence": {"cmdb_observation_id": "VARCHAR(255)", "idempotency_key": "VARCHAR(255)"},
    }
    for table_name, additions in columns.items():
        existing = {column["name"] for column in inspector.get_columns(table_name)} if inspector.has_table(table_name) else set()
        for name, definition in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {definition}"))
    from core.security_assessment_models import SecurityFindingCandidate
    SecurityFindingCandidate.__table__.create(bind=connection, checkfirst=True)
    connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_security_evidence_owner_idempotency ON security_evidence (owner, idempotency_key)"))


register_schema_migration(SchemaMigration(
    version=SECURITY_ASSESSMENT_V2_VERSION,
    checksum=SECURITY_ASSESSMENT_V2_CHECKSUM,
    apply=apply_security_assessment_v2,
))
