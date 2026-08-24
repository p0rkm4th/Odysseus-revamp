"""Versioned schema for the persistent Hades agent state."""
from sqlalchemy.engine import Connection
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration
from core.persistent_agent_models import ASSISTANT_TABLES

VERSION = "20260824_007_persistent_agent_v1"
CHECKSUM = migration_checksum("persistent-agent-v1\nself-episodes-lessons-monitors-notifications\n")


def apply(connection: Connection) -> None:
    for table in ASSISTANT_TABLES:
        table.create(bind=connection, checkfirst=True)


register_schema_migration(SchemaMigration(VERSION, CHECKSUM, apply))
