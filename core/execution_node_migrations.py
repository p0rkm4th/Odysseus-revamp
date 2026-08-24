from core.execution_node_models import EXECUTION_NODE_TABLES
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration

VERSION = "20260824_010_execution_nodes_v1"
DEFINITION = "execution-nodes-v1\nowner-scoped-capability-advertisements\nno-authority-grant\n"


def apply(connection):
    for table in EXECUTION_NODE_TABLES: table.create(bind=connection, checkfirst=True)


register_schema_migration(SchemaMigration(VERSION, migration_checksum(DEFINITION), apply))
