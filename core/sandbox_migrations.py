from core.sandbox_models import SANDBOX_TABLES
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration

VERSION = "20260824_011_sandbox_v1"
DEFINITION = "sandbox-session-metadata-v1\nno-runtime-or-authority\n"


def apply(connection):
    for table in SANDBOX_TABLES:
        table.create(bind=connection, checkfirst=True)


register_schema_migration(SchemaMigration(VERSION, migration_checksum(DEFINITION), apply))
