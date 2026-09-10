"""Private Finance truth and explicit household expense projections."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from core.database import Base, EncryptedText, TimestampMixin, utcnow_naive


MONEY_TYPE = Numeric(18, 4)


class Household(TimestampMixin, Base):
    __tablename__ = "finance_households"

    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    owner = Column(String, nullable=False, index=True)


class HouseholdMembership(Base):
    __tablename__ = "finance_household_memberships"

    id = Column(String, primary_key=True)
    household_id = Column(
        String,
        ForeignKey("finance_households.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(String, nullable=False, index=True)
    role = Column(String(16), nullable=False, default="member")
    created_at = Column(DateTime, nullable=False, default=utcnow_naive)

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'member')", name="ck_finance_household_role"),
        UniqueConstraint("household_id", "user_id", name="uq_finance_household_member"),
        Index("ix_finance_household_membership_lookup", "user_id", "household_id"),
    )


class FinanceAccount(TimestampMixin, Base):
    __tablename__ = "finance_accounts"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    provider_account_id = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    account_type = Column(String(64), nullable=True)
    currency = Column(String(3), nullable=True)
    source_created_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    provider_metadata = Column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint(
            "owner", "provider", "provider_account_id",
            name="uq_finance_account_owner_provider_identity",
        ),
        Index("ix_finance_accounts_owner_created", "owner", "created_at"),
    )


class FinanceTransaction(TimestampMixin, Base):
    __tablename__ = "finance_transactions"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    account_id = Column(
        String,
        ForeignKey("finance_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(64), nullable=False)
    provider_transaction_id = Column(String(255), nullable=False)
    amount = Column(MONEY_TYPE, nullable=False)
    currency = Column(String(3), nullable=False)
    transaction_date = Column(Date, nullable=False)
    merchant = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(16), nullable=False)
    direction = Column(String(8), nullable=False, default="outflow")
    pending_transaction_id = Column(String(255), nullable=True)
    superseded_by_transaction_id = Column(String(255), nullable=True)
    provider_removed = Column(Boolean, nullable=False, default=False)
    provider_removed_at = Column(DateTime, nullable=True)
    provider_category = Column(String(255), nullable=True)
    category_metadata = Column(JSON, nullable=False, default=dict)
    provider_metadata = Column(JSON, nullable=False, default=dict)
    provider_created_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'posted')", name="ck_finance_transaction_status"),
        CheckConstraint("direction IN ('inflow', 'outflow')", name="ck_finance_transaction_direction"),
        CheckConstraint("length(currency) = 3", name="ck_finance_transaction_currency"),
        UniqueConstraint(
            "account_id", "provider", "provider_transaction_id",
            name="uq_finance_transaction_provider_identity",
        ),
        Index("ix_finance_transactions_owner_date", "owner", "transaction_date"),
        Index("ix_finance_transactions_account_status", "account_id", "status"),
    )


class SharedExpense(TimestampMixin, Base):
    __tablename__ = "finance_shared_expenses"

    id = Column(String, primary_key=True)
    source_transaction_id = Column(
        String,
        ForeignKey("finance_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    household_id = Column(
        String,
        ForeignKey("finance_households.id", ondelete="CASCADE"),
        nullable=False,
    )
    payer_owner = Column(String, nullable=False)
    amount = Column(MONEY_TYPE, nullable=False)
    currency = Column(String(3), nullable=False)
    transaction_date = Column(Date, nullable=False)
    merchant = Column(String(255), nullable=True)
    label = Column(String(255), nullable=True)
    note = Column(Text, nullable=True)
    shared_at = Column(DateTime, nullable=False, default=utcnow_naive)
    revoked_at = Column(DateTime, nullable=True)
    needs_reconciliation = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint("length(currency) = 3", name="ck_finance_shared_currency"),
        Index("ix_finance_shared_household_active", "household_id", "revoked_at"),
        Index("ix_finance_shared_payer", "payer_owner", "revoked_at"),
    )


class PlaidItem(TimestampMixin, Base):
    """Owner-scoped Plaid connection state; access tokens are encrypted at rest."""

    __tablename__ = "finance_plaid_items"

    id = Column(String, primary_key=True)
    owner = Column(String, nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="plaid")
    item_id = Column(String(255), nullable=False)
    access_token = Column(EncryptedText, nullable=False)
    sync_cursor = Column(Text, nullable=True)
    sync_status = Column(String(32), nullable=False, default="not_synced")
    last_attempted_sync_at = Column(DateTime, nullable=True)
    last_successful_sync_at = Column(DateTime, nullable=True)
    provider_last_successful_update_at = Column(DateTime, nullable=True)
    institution_name = Column(String(255), nullable=True)
    last_error_classification = Column(String(128), nullable=True)

    __table_args__ = (
        UniqueConstraint("owner", "provider", "item_id", name="uq_finance_plaid_owner_item"),
        CheckConstraint(
            "sync_status IN ('not_synced', 'syncing', 'healthy', 'error')",
            name="ck_finance_plaid_sync_status",
        ),
    )


FINANCE_TABLES = (
    Household.__table__,
    HouseholdMembership.__table__,
    FinanceAccount.__table__,
    FinanceTransaction.__table__,
    SharedExpense.__table__,
    PlaidItem.__table__,
)
