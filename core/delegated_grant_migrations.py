from core.delegated_grant_models import DELEGATED_GRANT_TABLES
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration

VERSION = "20260824_011_delegated_grants_v1"
DEFINITION = "delegated-grants-v1\nexact-owner-run-action-digest-scope\nshort-lived-no-credential\n"


def apply(connection):
    for table in DELEGATED_GRANT_TABLES: table.create(bind=connection, checkfirst=True)


register_schema_migration(SchemaMigration(VERSION, migration_checksum(DEFINITION), apply))
