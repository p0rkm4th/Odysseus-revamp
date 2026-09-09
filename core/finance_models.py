"""Private Finance truth and explicit household expense projections."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
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

from core.database import Base, TimestampMixin, utcnow_naive


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
    provider_metadata = Column(JSON, nullable=False, default=dict)
    provider_created_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'posted')", name="ck_finance_transaction_status"),
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

    __table_args__ = (
        CheckConstraint("length(currency) = 3", name="ck_finance_shared_currency"),
        Index("ix_finance_shared_household_active", "household_id", "revoked_at"),
        Index("ix_finance_shared_payer", "payer_owner", "revoked_at"),
    )


FINANCE_TABLES = (
    Household.__table__,
    HouseholdMembership.__table__,
    FinanceAccount.__table__,
    FinanceTransaction.__table__,
    SharedExpense.__table__,
)
