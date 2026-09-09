"""Owner-scoped Finance foundation and explicit household projections."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.finance_models import (
    FinanceAccount,
    FinanceTransaction,
    Household,
    HouseholdMembership,
    SharedExpense,
)
from core.database import utcnow_naive


class FinanceError(ValueError):
    """Expected caller/input/domain failure."""


def _required_text(value: Any, field: str, *, max_length: int = 255) -> str:
    text = str(value or "").strip()
    if not text:
        raise FinanceError(f"{field} is required")
    if len(text) > max_length:
        raise FinanceError(f"{field} is too long")
    return text


def _currency(value: Any) -> str:
    currency = _required_text(value, "currency", max_length=3).upper()
    if len(currency) != 3 or not currency.isalpha() or not currency.isascii():
        raise FinanceError("currency must be a three-letter code")
    return currency


def _money(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise FinanceError("amount must be a decimal-safe number")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise FinanceError("amount must be a decimal-safe number") from exc
    if not amount.is_finite():
        raise FinanceError("amount must be finite")
    quantized = amount.quantize(Decimal("0.0001"))
    if amount != quantized:
        raise FinanceError("amount must use at most four decimal places")
    return quantized


def _transaction_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise FinanceError("transaction_date must be an ISO date") from exc


def _optional_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise FinanceError("timestamp must be ISO-8601") from exc


def _membership(db: Session, household_id: str, user_id: str) -> HouseholdMembership | None:
    return db.query(HouseholdMembership).filter(
        HouseholdMembership.household_id == household_id,
        HouseholdMembership.user_id == user_id,
    ).one_or_none()


def _household_or_error(db: Session, household_id: str) -> Household:
    household = db.get(Household, household_id)
    if household is None:
        raise FinanceError("household not found")
    return household


def _public_shared(
    expense: SharedExpense,
    transaction: FinanceTransaction | None = None,
    *,
    include_source: bool = False,
) -> dict[str, Any]:
    """Return only the bounded household projection, never source metadata."""
    result = {
        "id": expense.id,
        "household_id": expense.household_id,
        "payer_owner": expense.payer_owner,
        "amount": str(expense.amount),
        "currency": expense.currency,
        "transaction_date": expense.transaction_date.isoformat(),
        "merchant": expense.merchant,
        "label": expense.label,
        "note": expense.note,
        "status": transaction.status if transaction is not None else None,
        "source_provider": transaction.provider if transaction is not None else None,
        "shared_at": expense.shared_at.isoformat() if expense.shared_at else None,
    }
    if include_source:
        result["source_transaction_id"] = expense.source_transaction_id
    return result


class FinanceService:
    def __init__(self, db: Session):
        self.db = db

    def create_household(self, owner: str, name: str) -> dict[str, Any]:
        owner = _required_text(owner, "owner")
        household = Household(id=uuid4().hex, owner=owner, name=_required_text(name, "name", max_length=200))
        self.db.add(household)
        self.db.flush()
        self.db.add(HouseholdMembership(
            id=uuid4().hex, household_id=household.id, user_id=owner, role="owner",
        ))
        self.db.commit()
        return self.household_membership(owner, household.id)

    def add_member(self, actor: str, household_id: str, user_id: str, role: str = "member") -> dict[str, Any]:
        household = _household_or_error(self.db, household_id)
        if household.owner != actor:
            raise FinanceError("only the household owner can manage membership")
        user_id = _required_text(user_id, "user_id")
        if role != "member":
            raise FinanceError("new memberships must use the member role")
        membership = HouseholdMembership(
            id=uuid4().hex, household_id=household_id, user_id=user_id, role=role,
        )
        self.db.add(membership)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise FinanceError("user is already a household member") from exc
        return self._membership_dict(membership)

    def _membership_dict(self, membership: HouseholdMembership) -> dict[str, Any]:
        return {
            "id": membership.id,
            "household_id": membership.household_id,
            "user_id": membership.user_id,
            "role": membership.role,
        }

    def household_membership(self, user_id: str, household_id: str) -> dict[str, Any]:
        membership = _membership(self.db, household_id, user_id)
        if membership is None:
            raise FinanceError("household membership not found")
        return self._membership_dict(membership)

    def list_memberships(self, user_id: str) -> list[dict[str, Any]]:
        return [self._membership_dict(row) for row in self.db.query(HouseholdMembership).filter(
            HouseholdMembership.user_id == user_id,
        ).order_by(HouseholdMembership.created_at.asc()).all()]

    def import_account(self, owner: str, payload: dict[str, Any]) -> dict[str, Any]:
        provider = _required_text(payload.get("provider"), "provider", max_length=64)
        provider_account_id = _required_text(payload.get("provider_account_id"), "provider_account_id")
        currency = payload.get("currency")
        if currency is not None:
            currency = _currency(currency)
        account = self.db.query(FinanceAccount).filter(
            FinanceAccount.owner == owner,
            FinanceAccount.provider == provider,
            FinanceAccount.provider_account_id == provider_account_id,
        ).one_or_none()
        if account is None:
            account = FinanceAccount(
                id=uuid4().hex, owner=owner, provider=provider,
                provider_account_id=provider_account_id,
            )
            self.db.add(account)
        account.display_name = payload.get("display_name")
        account.account_type = payload.get("account_type")
        account.currency = currency
        account.source_created_at = _optional_datetime(payload.get("source_created_at"))
        account.last_synced_at = _optional_datetime(payload.get("last_synced_at"))
        account.provider_metadata = dict(payload.get("provider_metadata") or {})
        self.db.commit()
        return self._account_dict(account)

    def _account_dict(self, account: FinanceAccount) -> dict[str, Any]:
        return {
            "id": account.id,
            "owner": account.owner,
            "provider": account.provider,
            "provider_account_id": account.provider_account_id,
            "display_name": account.display_name,
            "account_type": account.account_type,
            "currency": account.currency,
            "source_created_at": account.source_created_at.isoformat() if account.source_created_at else None,
            "last_synced_at": account.last_synced_at.isoformat() if account.last_synced_at else None,
        }

    def list_accounts(self, owner: str) -> list[dict[str, Any]]:
        return [self._account_dict(row) for row in self.db.query(FinanceAccount).filter(
            FinanceAccount.owner == owner,
        ).order_by(FinanceAccount.created_at.asc()).all()]

    def import_transaction(self, owner: str, payload: dict[str, Any]) -> dict[str, Any]:
        account_id = _required_text(payload.get("account_id"), "account_id")
        account = self.db.query(FinanceAccount).filter(
            FinanceAccount.id == account_id, FinanceAccount.owner == owner,
        ).one_or_none()
        if account is None:
            raise FinanceError("Finance account not found")
        provider = _required_text(payload.get("provider"), "provider", max_length=64)
        if provider != account.provider:
            raise FinanceError("transaction provider does not match account provider")
        provider_transaction_id = _required_text(payload.get("provider_transaction_id"), "provider_transaction_id")
        amount = _money(payload.get("amount"))
        currency = _currency(payload.get("currency"))
        transaction_date = _transaction_date(payload.get("transaction_date"))
        status = _required_text(payload.get("status"), "status", max_length=16).lower()
        if status not in {"pending", "posted"}:
            raise FinanceError("status must be pending or posted")
        merchant = payload.get("merchant")
        description = payload.get("description")
        if not str(merchant or description or "").strip():
            raise FinanceError("merchant or description is required")
        transaction = self.db.query(FinanceTransaction).filter(
            FinanceTransaction.account_id == account.id,
            FinanceTransaction.provider == provider,
            FinanceTransaction.provider_transaction_id == provider_transaction_id,
        ).one_or_none()
        if transaction is None:
            transaction = FinanceTransaction(
                id=uuid4().hex, owner=owner, account_id=account.id,
                provider=provider, provider_transaction_id=provider_transaction_id,
            )
            self.db.add(transaction)
        transaction.amount = amount
        transaction.currency = currency
        transaction.transaction_date = transaction_date
        transaction.merchant = merchant
        transaction.description = description
        transaction.status = status
        transaction.provider_metadata = dict(payload.get("provider_metadata") or {})
        transaction.provider_created_at = _optional_datetime(payload.get("provider_created_at"))
        self.db.commit()
        return self._transaction_dict(transaction)

    def _transaction_dict(
        self, transaction: FinanceTransaction, *, include_provider_metadata: bool = True,
    ) -> dict[str, Any]:
        result = {
            "id": transaction.id,
            "owner": transaction.owner,
            "account_id": transaction.account_id,
            "provider": transaction.provider,
            "provider_transaction_id": transaction.provider_transaction_id,
            "amount": str(transaction.amount),
            "currency": transaction.currency,
            "transaction_date": transaction.transaction_date.isoformat(),
            "merchant": transaction.merchant,
            "description": transaction.description,
            "status": transaction.status,
        }
        if include_provider_metadata:
            result["provider_metadata"] = transaction.provider_metadata
        return result

    def list_transactions(self, owner: str) -> list[dict[str, Any]]:
        return [self._transaction_dict(row) for row in self.db.query(FinanceTransaction).filter(
            FinanceTransaction.owner == owner,
        ).order_by(FinanceTransaction.transaction_date.desc(), FinanceTransaction.created_at.desc()).all()]

    def share_transaction(
        self, owner: str, transaction_id: str, household_id: str,
        *, label: str | None = None, note: str | None = None,
    ) -> dict[str, Any]:
        transaction = self.db.query(FinanceTransaction).filter(
            FinanceTransaction.id == transaction_id,
            FinanceTransaction.owner == owner,
        ).one_or_none()
        if transaction is None:
            raise FinanceError("private Finance transaction not found")
        _household_or_error(self.db, household_id)
        if _membership(self.db, household_id, owner) is None:
            raise FinanceError("source owner must belong to the household")
        existing = self.db.query(SharedExpense).filter(
            SharedExpense.source_transaction_id == transaction.id,
            SharedExpense.household_id == household_id,
            SharedExpense.revoked_at.is_(None),
        ).one_or_none()
        if existing is not None:
            return _public_shared(existing, transaction)
        projection = SharedExpense(
            id=uuid4().hex,
            source_transaction_id=transaction.id,
            household_id=household_id,
            payer_owner=owner,
            amount=transaction.amount,
            currency=transaction.currency,
            transaction_date=transaction.transaction_date,
            merchant=transaction.merchant,
            label=label,
            note=note,
        )
        self.db.add(projection)
        self.db.commit()
        return _public_shared(projection, transaction)

    def list_shared_expenses(self, user_id: str, household_id: str) -> list[dict[str, Any]]:
        _household_or_error(self.db, household_id)
        if _membership(self.db, household_id, user_id) is None:
            raise FinanceError("household membership not found")
        rows = self.db.query(SharedExpense).filter(
            SharedExpense.household_id == household_id,
            SharedExpense.revoked_at.is_(None),
        ).order_by(SharedExpense.transaction_date.desc(), SharedExpense.created_at.desc()).all()
        return [
            _public_shared(row, self.db.get(FinanceTransaction, row.source_transaction_id))
            for row in rows
        ]

    def revoke_shared_expense(self, owner: str, shared_expense_id: str) -> None:
        projection = self.db.get(SharedExpense, shared_expense_id)
        if projection is None or projection.payer_owner != owner:
            raise FinanceError("shared expense not found")
        if projection.revoked_at is None:
            projection.revoked_at = utcnow_naive()
            self.db.commit()

    def read_projection(self, user_id: str, household_id: str | None = None) -> dict[str, Any]:
        projection: dict[str, Any] = {
            "accounts": self.list_accounts(user_id),
            "private_transactions": [
                self._transaction_dict(row, include_provider_metadata=False)
                for row in self.db.query(FinanceTransaction).filter(
                    FinanceTransaction.owner == user_id,
                ).order_by(
                    FinanceTransaction.transaction_date.desc(),
                    FinanceTransaction.created_at.desc(),
                ).all()
            ],
            "household_memberships": self.list_memberships(user_id),
            "shared_expenses": [],
        }
        if household_id is not None:
            _household_or_error(self.db, household_id)
            if _membership(self.db, household_id, user_id) is None:
                raise FinanceError("household membership not found")
            rows = self.db.query(SharedExpense).filter(
                SharedExpense.household_id == household_id,
                SharedExpense.revoked_at.is_(None),
            ).order_by(SharedExpense.transaction_date.desc(), SharedExpense.created_at.desc()).all()
            projection["shared_expenses"] = [
                _public_shared(
                    row, self.db.get(FinanceTransaction, row.source_transaction_id),
                    include_source=True,
                )
                for row in rows
            ]
        return projection
