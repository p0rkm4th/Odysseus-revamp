"""Versioned migration for the domain-neutral Work Engine."""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from core.schema_migrations import SchemaMigration, migration_checksum, register_schema_migration
from core.work_models import WORK_TABLES

WORK_V1_VERSION = "20260823_005_work_engine_v1"
WORK_V1_DEFINITION = """work-engine-v1
goal-project-task-run-action-result-artifact-event-commitment
durable-resumption
domain-neutral-owner-scoped
"""
WORK_V1_CHECKSUM = migration_checksum(WORK_V1_DEFINITION)

def apply_work_v1(connection: Connection) -> None:
    for table in WORK_TABLES:
        table.create(bind=connection, checkfirst=True)

register_schema_migration(SchemaMigration(WORK_V1_VERSION, WORK_V1_CHECKSUM, apply_work_v1))

WORK_V2_VERSION = "20260824_001_work_run_action_contract_v2"
WORK_V2_DEFINITION = """work-engine-v2
durable-run-lifecycle-intent-plan-assumptions-costs-checkpoints-verification
action-contract-targets-preconditions-locks-retry-rollback-postconditions
backward-compatible-additive-columns
"""
WORK_V2_CHECKSUM = migration_checksum(WORK_V2_DEFINITION)

def apply_work_v2(connection: Connection) -> None:
    """Add contract/lifecycle columns to existing Work tables.

    The columns are intentionally additive and nullable for upgraded databases;
    ORM defaults supply the canonical shape for newly-created records.
    """
    additions = {
        "work_runs": {
            "lifecycle_state": "VARCHAR(32)", "intent": "JSON", "plan": "JSON",
            "assumptions": "JSON", "costs": "JSON", "checkpoints": "JSON",
            "verification": "JSON",
        },
        "work_actions": {
            "target_resources": "JSON", "preconditions": "JSON", "locks": "JSON",
            "risk_level": "VARCHAR(32)", "idempotency_key": "VARCHAR(300)",
            "retry_policy": "JSON", "timeout_seconds": "INTEGER",
            "rollback_capability": "VARCHAR(300)", "compensating_action": "JSON",
            "postconditions": "JSON", "verification": "JSON",
        },
    }
    inspector = inspect(connection)
    for table_name, columns in additions.items():
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, column_type in columns.items():
            if column_name not in existing:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))

register_schema_migration(SchemaMigration(WORK_V2_VERSION, WORK_V2_CHECKSUM, apply_work_v2))

WORK_V3_VERSION = "20260824_002_work_resource_locks_v3"
WORK_V3_DEFINITION = """work-engine-v3
owner-scoped-shared-exclusive-resource-locks
action-run-collision-prevention
"""
WORK_V3_CHECKSUM = migration_checksum(WORK_V3_DEFINITION)

def apply_work_v3(connection: Connection) -> None:
    from core.work_models import WorkLock
    WorkLock.__table__.create(bind=connection, checkfirst=True)

register_schema_migration(SchemaMigration(WORK_V3_VERSION, WORK_V3_CHECKSUM, apply_work_v3))

WORK_V4_VERSION = "20260824_003_epistemic_claims_v4"
WORK_V4_DEFINITION = """work-engine-v4
owner-scoped-epistemic-claims
claim-class-confidence-evidence-contradiction
valid-time-and-record-time-projections
"""
WORK_V4_CHECKSUM = migration_checksum(WORK_V4_DEFINITION)

def apply_work_v4(connection: Connection) -> None:
    from core.work_models import EpistemicClaim
    EpistemicClaim.__table__.create(bind=connection, checkfirst=True)

register_schema_migration(SchemaMigration(WORK_V4_VERSION, WORK_V4_CHECKSUM, apply_work_v4))

WORK_V5_VERSION = "20260824_006_world_relationships_v5"
WORK_V5_DEFINITION = """work-engine-v5
owner-scoped-evidence-backed-world-relationships
typed-status-valid-time-and-bounded-traversal-foundation
"""
WORK_V5_CHECKSUM = migration_checksum(WORK_V5_DEFINITION)

def apply_work_v5(connection: Connection) -> None:
    from core.work_models import WorldRelationship
    WorldRelationship.__table__.create(bind=connection, checkfirst=True)

register_schema_migration(SchemaMigration(WORK_V5_VERSION, WORK_V5_CHECKSUM, apply_work_v5))

WORK_V6_VERSION = "20260825_002_work_run_completion_v6"
WORK_V6_DEFINITION = """work-engine-v6
durable-deliverable-and-completion-criteria
generic-run-completion-projection
backward-compatible-additive-column
"""
WORK_V6_CHECKSUM = migration_checksum(WORK_V6_DEFINITION)

def apply_work_v6(connection: Connection) -> None:
    inspector = inspect(connection)
    existing = {column["name"] for column in inspector.get_columns("work_runs")}
    if "completion_criteria" not in existing:
        connection.execute(text("ALTER TABLE work_runs ADD COLUMN completion_criteria JSON"))

register_schema_migration(SchemaMigration(WORK_V6_VERSION, WORK_V6_CHECKSUM, apply_work_v6))
