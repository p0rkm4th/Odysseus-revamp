"""Versioned Incident/Change tables; execution remains Work-owned."""
from core.incident_models import INCIDENT_TABLES
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration

VERSION = "20260824_008_incident_change_v1"
CHECKSUM = migration_checksum("incident-change-v1\nowner-scoped-incident-hypotheses-and-change-projections\n")


def apply(connection):
    for table in INCIDENT_TABLES:
        table.create(bind=connection, checkfirst=True)


register_schema_migration(SchemaMigration(VERSION, CHECKSUM, apply))
