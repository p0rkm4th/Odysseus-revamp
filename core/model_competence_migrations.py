from core.model_competence_models import COMPETENCE_TABLES
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration

VERSION = "20260824_009_model_competence_v1"
CHECKSUM = migration_checksum("model-competence-v1\nowner-scoped-evaluation-derived-qualification\n")


def apply(connection):
    for table in COMPETENCE_TABLES: table.create(bind=connection, checkfirst=True)


register_schema_migration(SchemaMigration(VERSION, CHECKSUM, apply))
