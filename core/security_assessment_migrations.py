"""Versioned schema for the bounded security assessment domain."""

from sqlalchemy import inspect
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
