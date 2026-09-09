"""Versioned bootstrap for the private Finance foundation."""

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from core.finance_models import FINANCE_TABLES
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
