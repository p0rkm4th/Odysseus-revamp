"""Versioned schema for owner-scoped Career state."""
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration
from core.career_models import CAREER_TABLES

VERSION = "20260825_001_career_foundation_v1"
DEFINITION = """career-foundation-v1
owner-scoped-profile-search-opportunity-application-interview
provider-adapter-boundary-no-provider-data-as-canonical
"""


def apply(connection):
    for table in CAREER_TABLES:
        table.create(bind=connection, checkfirst=True)


register_schema_migration(SchemaMigration(VERSION, migration_checksum(DEFINITION), apply))
