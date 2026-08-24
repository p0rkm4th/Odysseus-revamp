"""Versioned schema for local intelligence and owner-granted developer mode."""
from sqlalchemy.engine import Connection
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration
from core.local_intelligence_models import DeveloperLease
VERSION = "20260823_006_local_intelligence_developer_v1"
CHECKSUM = migration_checksum("local-intelligence-developer-v1\nowner-scoped-expiring-workspace-lease\n")
def apply(connection: Connection) -> None: DeveloperLease.__table__.create(bind=connection, checkfirst=True)
register_schema_migration(SchemaMigration(VERSION, CHECKSUM, apply))
