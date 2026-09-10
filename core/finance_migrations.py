"""Versioned bootstrap for the private Finance foundation."""

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from core.finance_models import FINANCE_TABLES, FinanceConnection, PlaidItem, PlaidLinkSession
from core.schema_migrations import (
    SchemaMigration,
    migration_checksum,
    register_schema_migration,
)


FINANCE_V1_VERSION = "20260909_001_finance_household_foundation"
FINANCE_V1_DEFINITION = """finance-household-foundation-v1
private-owner-finance-accounts
private-owner-finance-transactions
explicit-household-memberships
explicit-revocable-shared-expense-projection
decimal-currency-qualified-money
provider-identity-idempotency
"""
FINANCE_V1_CHECKSUM = migration_checksum(FINANCE_V1_DEFINITION)

FINANCE_V2_VERSION = "20260909_002_plaid_readonly_finance"
FINANCE_V2_DEFINITION = """finance-plaid-readonly-v1
encrypted-owner-scoped-plaid-item
transaction-direction-and-provider-lifecycle
shared-expense-reconciliation-flag
"""
FINANCE_V2_CHECKSUM = migration_checksum(FINANCE_V2_DEFINITION)

FINANCE_V3_VERSION = "20260910_003_plaid_link_owner_binding"
FINANCE_V3_DEFINITION = """finance-plaid-link-v1
owner-bound-short-lived-link-session
hashed-link-token-only
"""
FINANCE_V3_CHECKSUM = migration_checksum(FINANCE_V3_DEFINITION)

FINANCE_V4_VERSION = "20260910_004_provider_connection_lifecycle"
FINANCE_V4_DEFINITION = """finance-provider-connection-lifecycle-v1
owner-scoped-canonical-lifecycle
authorization-correlation-and-continuation
"""
FINANCE_V4_CHECKSUM = migration_checksum(FINANCE_V4_DEFINITION)


def apply_finance_v1(connection: Connection) -> None:
    for table in FINANCE_TABLES:
        table.create(bind=connection, checkfirst=True)
    inspector = inspect(connection)
    missing = [table.name for table in FINANCE_TABLES if not inspector.has_table(table.name)]
    if missing:
        raise RuntimeError(f"finance v1 migration did not create tables: {', '.join(missing)}")


register_schema_migration(
    SchemaMigration(
        version=FINANCE_V1_VERSION,
        checksum=FINANCE_V1_CHECKSUM,
        apply=apply_finance_v1,
    )
)


def apply_finance_v4(connection: Connection) -> None:
    """Add canonical lifecycle state without exposing provider credentials."""
    FinanceConnection.__table__.create(bind=connection, checkfirst=True)
    inspector = inspect(connection)
    plaid_columns = {column["name"] for column in inspector.get_columns("finance_plaid_items")}
    if "connection_id" not in plaid_columns:
        connection.exec_driver_sql("ALTER TABLE finance_plaid_items ADD COLUMN connection_id VARCHAR(255)")
    link_columns = {column["name"] for column in inspector.get_columns("finance_plaid_link_sessions")}
    additions = (
        ("connection_id", "VARCHAR(255)"),
        ("authorization_state_hash", "VARCHAR(64)"),
        ("mode", "VARCHAR(16) NOT NULL DEFAULT 'create'"),
        ("continuation", "JSON"),
    )
    for name, definition in additions:
        if name not in link_columns:
            connection.exec_driver_sql(f"ALTER TABLE finance_plaid_link_sessions ADD COLUMN {name} {definition}")


register_schema_migration(SchemaMigration(
    version=FINANCE_V4_VERSION, checksum=FINANCE_V4_CHECKSUM, apply=apply_finance_v4,
))


def apply_finance_v3(connection: Connection) -> None:
    """Add owner-bound Link-session state without storing the Link token."""
    PlaidLinkSession.__table__.create(bind=connection, checkfirst=True)
    if not inspect(connection).has_table(PlaidLinkSession.__tablename__):
        raise RuntimeError("finance v3 migration did not create Plaid Link session state")


register_schema_migration(
    SchemaMigration(
        version=FINANCE_V3_VERSION,
        checksum=FINANCE_V3_CHECKSUM,
        apply=apply_finance_v3,
    )
)


def apply_finance_v2(connection: Connection) -> None:
    """Add the small Plaid lifecycle surface to existing Finance databases.

    These additions are intentionally additive and use SQLite/Postgres-compatible
    ALTER TABLE forms. Fresh databases receive the same columns from metadata.
    """
    inspector = inspect(connection)
    transaction_columns = {column["name"] for column in inspector.get_columns("finance_transactions")}
    additions = (
        ("direction", "VARCHAR(8) NOT NULL DEFAULT 'outflow'"),
        ("pending_transaction_id", "VARCHAR(255)"),
        ("superseded_by_transaction_id", "VARCHAR(255)"),
        ("provider_removed", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("provider_removed_at", "DATETIME"),
        ("provider_category", "VARCHAR(255)"),
        ("category_metadata", "JSON NOT NULL DEFAULT '{}'"),
    )
    for name, definition in additions:
        if name not in transaction_columns:
            connection.exec_driver_sql(
                f"ALTER TABLE finance_transactions ADD COLUMN {name} {definition}"
            )
    shared_columns = {column["name"] for column in inspector.get_columns("finance_shared_expenses")}
    if "needs_reconciliation" not in shared_columns:
        connection.exec_driver_sql(
            "ALTER TABLE finance_shared_expenses ADD COLUMN needs_reconciliation BOOLEAN NOT NULL DEFAULT FALSE"
        )
    PlaidItem.__table__.create(bind=connection, checkfirst=True)
    inspector = inspect(connection)
    if not inspector.has_table("finance_plaid_items"):
        raise RuntimeError("finance v2 migration did not create Plaid item state")


register_schema_migration(
    SchemaMigration(
        version=FINANCE_V2_VERSION,
        checksum=FINANCE_V2_CHECKSUM,
        apply=apply_finance_v2,
    )
)
