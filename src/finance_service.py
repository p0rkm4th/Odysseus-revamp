"""Owner-scoped Finance foundation and explicit household projections."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timedelta
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
    PlaidItem,
    FinanceConnection,
)
from core.database import utcnow_naive
from src.integration_lifecycle import capability_available


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
    text = str(value or "").strip()
    for parser in (
        date.fromisoformat,
        lambda item: datetime.strptime(item, "%m/%d/%Y").date(),
        lambda item: datetime.strptime(item, "%m/%d/%y").date(),
        lambda item: datetime.strptime(item, "%Y/%m/%d").date(),
    ):
        try:
            return parser(text)
        except (TypeError, ValueError):
            continue
    raise FinanceError("transaction_date must be a recognizable date")


def _csv_header(value: Any) -> str:
    """Normalize common bank-export header spelling without guessing semantics."""
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _csv_value(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = str(row.get(name) or "").strip()
        if value:
            return value
    return ""


def _csv_money(value: Any) -> Decimal:
    """Accept harmless formatting used by common bank exports."""
    text = str(value or "").strip()
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    return _money(text.replace(",", "").replace("$", ""))


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
        "needs_reconciliation": bool(expense.needs_reconciliation),
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

    def import_account(self, owner: str, payload: dict[str, Any], *, _commit: bool = True) -> dict[str, Any]:
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
        if _commit:
            self.db.commit()
        else:
            self.db.flush()
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

    def import_transaction(self, owner: str, payload: dict[str, Any], *, _commit: bool = True) -> dict[str, Any]:
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
        direction = _required_text(payload.get("direction") or "outflow", "direction", max_length=8).lower()
        if direction not in {"inflow", "outflow"}:
            raise FinanceError("direction must be inflow or outflow")
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
        transaction.direction = direction
        transaction.pending_transaction_id = payload.get("pending_transaction_id")
        transaction.superseded_by_transaction_id = payload.get("superseded_by_transaction_id")
        transaction.provider_removed = bool(payload.get("provider_removed", False))
        transaction.provider_removed_at = _optional_datetime(payload.get("provider_removed_at"))
        transaction.provider_category = payload.get("provider_category")
        transaction.category_metadata = dict(payload.get("category_metadata") or {})
        transaction.provider_metadata = dict(payload.get("provider_metadata") or {})
        transaction.provider_created_at = _optional_datetime(payload.get("provider_created_at"))
        if _commit:
            self.db.commit()
        else:
            self.db.flush()
        return self._transaction_dict(transaction)

    def import_csv(self, owner: str, csv_text: str, *, account_name: str = "CSV Finance account", currency: str = "USD", source_label: str = "local_csv") -> dict[str, Any]:
        """Import a bounded local CSV snapshot into canonical Finance truth.

        This is a fallback source, not a live-provider assertion. Stable row
        identities make repeated imports idempotent and keep all existing
        deterministic spending/cash-flow reads applicable.
        """
        text = str(csv_text or "")
        source_label = _required_text(source_label or "local_csv", "source_label", max_length=128)
        account_name = _required_text(account_name or "CSV Finance account", "account_name", max_length=200)
        default_currency = _currency(currency)
        if len(text.encode("utf-8")) > 2_000_000:
            raise FinanceError("Finance CSV is limited to 2 MB")
        # Bank exports vary in harmless presentation details. Normalize headers
        # and accept a bounded set of unambiguous aliases, while still refusing
        # rows whose date, identity, or money cannot be represented safely.
        sample = text[:8192]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text, newline=""), dialect=dialect)
        if not reader.fieldnames:
            raise FinanceError("Finance CSV must include a header row")
        rows: list[dict[str, Any]] = []
        for index, raw in enumerate(reader, 1):
            normalized = {_csv_header(key): str(value or "").strip() for key, value in raw.items() if key is not None}
            if not any(normalized.values()):
                continue
            try:
                transaction_date = _transaction_date(_csv_value(
                    normalized, "date", "transaction_date", "posted_date", "trans_date", "posting_date",
                ))
                amount_text = _csv_value(normalized, "amount", "transaction_amount", "value")
                debit = _csv_value(normalized, "debit", "withdrawal", "withdrawals", "money_out")
                credit = _csv_value(normalized, "credit", "deposit", "deposits", "money_in")
                if amount_text:
                    amount = _csv_money(amount_text)
                elif debit or credit:
                    # Canonical Finance uses positive outflows and negative
                    # inflows, matching Plaid's normalized convention.
                    amount = _csv_money(debit or "0") - _csv_money(credit or "0")
                else:
                    raise FinanceError("an amount or debit/credit columns are required")
            except (FinanceError, TypeError, ValueError) as exc:
                raise FinanceError(f"Finance CSV row {index} is invalid: {exc}") from exc
            merchant = _csv_value(
                normalized, "merchant", "merchant_name", "name", "description",
                "transaction_description", "payee", "memo",
            )
            if not merchant:
                raise FinanceError(f"Finance CSV row {index} requires a merchant, name, description, or payee")
            explicit_direction = _csv_value(normalized, "direction", "flow")
            if explicit_direction:
                direction = {
                    "debit": "outflow",
                    "withdrawal": "outflow",
                    "expense": "outflow",
                    "credit": "inflow",
                    "deposit": "inflow",
                    "income": "inflow",
                }.get(explicit_direction.casefold(), explicit_direction.casefold())
            elif debit or credit:
                # Separate debit/credit columns were normalized above to a
                # positive outflow / negative inflow amount.
                direction = "outflow" if amount > 0 else "inflow"
            else:
                # Ordinary bank exports conventionally use negative amounts
                # for money spent and positive amounts for money received.
                # Normalize that CSV convention into HADES's positive amount
                # plus explicit direction representation.
                direction = "outflow" if amount < 0 else "inflow"
            if direction not in {"inflow", "outflow"}:
                raise FinanceError(f"Finance CSV row {index} has invalid direction")
            status = (_csv_value(normalized, "status", "transaction_status", "posting_status") or "posted").casefold()
            if status not in {"pending", "posted"}:
                raise FinanceError(f"Finance CSV row {index} has invalid status")
            row_currency = _currency(_csv_value(
                normalized, "currency", "currency_code", "iso_currency_code", "currency_iso",
            ) or default_currency)
            description = _csv_value(normalized, "description", "transaction_description", "memo")
            category = _csv_value(normalized, "category", "category_name", "type")
            # Preserve the pre-normalization sign-derived identity for rows
            # imported by older HADES versions. Re-uploading a corrected CSV
            # updates those rows instead of creating duplicates.
            identity_direction = direction
            if not explicit_direction and not (debit or credit):
                identity_direction = "inflow" if amount < 0 else "outflow"
            identity = hashlib.sha256(json.dumps({
                "row": index,
                "date": transaction_date.isoformat(), "amount": str(abs(amount)),
                "merchant": merchant, "description": description,
                "currency": row_currency, "direction": identity_direction, "status": status,
            }, sort_keys=True).encode()).hexdigest()[:32]
            rows.append({
                "provider": "csv", "provider_transaction_id": f"{source_label}:{identity}",
                "amount": abs(amount), "currency": row_currency,
                "transaction_date": transaction_date.isoformat(), "merchant": merchant,
                "description": description, "direction": direction,
                "status": status, "provider_category": category,
                "provider_metadata": {"source": "local_csv", "source_label": source_label},
            })
        # A snapshot is one canonical import operation. Do not leave an
        # account or prefix of its rows behind if a later row or the final
        # commit fails.
        try:
            account = self.import_account(owner, {
                "provider": "csv", "provider_account_id": hashlib.sha256(f"{owner}:{source_label}".encode()).hexdigest()[:32],
                "display_name": account_name, "currency": default_currency,
                "last_synced_at": utcnow_naive(),
                "provider_metadata": {"source": "local_csv", "source_label": source_label},
            }, _commit=False)
            imported = [self.import_transaction(owner, {**row, "account_id": account["id"]}, _commit=False) for row in rows]
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"source": "local_csv", "source_label": source_label, "account": account, "imported_count": len(imported), "transactions": imported, "live_provider": False}

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
            "direction": transaction.direction,
            "pending_transaction_id": transaction.pending_transaction_id,
            "provider_removed": bool(transaction.provider_removed),
            "provider_category": transaction.provider_category,
        }
        if include_provider_metadata:
            result["provider_metadata"] = transaction.provider_metadata
        return result

    def list_transactions(self, owner: str) -> list[dict[str, Any]]:
        return [self._transaction_dict(row) for row in self.db.query(FinanceTransaction).filter(
            FinanceTransaction.owner == owner,
            FinanceTransaction.provider_removed.is_(False),
        ).order_by(FinanceTransaction.transaction_date.desc(), FinanceTransaction.created_at.desc()).all()]

    def create_plaid_item(self, owner: str, item_id: str, access_token: str, institution_name: str | None = None, connection_id: str | None = None) -> dict[str, Any]:
        owner = _required_text(owner, "owner")
        item_id = _required_text(item_id, "item_id")
        access_token = _required_text(access_token, "access_token")
        item = self.db.query(PlaidItem).filter(
            PlaidItem.owner == owner, PlaidItem.provider == "plaid", PlaidItem.item_id == item_id,
        ).one_or_none()
        if item is None:
            connection = self.db.query(FinanceConnection).filter_by(id=connection_id, owner=owner, provider="plaid").one_or_none() if connection_id else self.db.query(FinanceConnection).filter(
                FinanceConnection.owner == owner, FinanceConnection.provider == "plaid",
            ).order_by(FinanceConnection.created_at.desc()).first()
            if connection is None:
                connection = FinanceConnection(id=uuid4().hex, owner=owner, provider="plaid")
                self.db.add(connection)
                self.db.flush()
            item = PlaidItem(id=uuid4().hex, connection_id=connection.id, owner=owner, provider="plaid", item_id=item_id, access_token=access_token)
            self.db.add(item)
        else:
            item.access_token = access_token
        connection = self.db.query(FinanceConnection).filter(FinanceConnection.id == item.connection_id).one_or_none()
        if connection is None:
            connection = FinanceConnection(id=uuid4().hex, owner=owner, provider="plaid")
            self.db.add(connection); self.db.flush(); item.connection_id = connection.id
        connection.lifecycle_state = "CONNECTED"
        connection.provider_health = "UNKNOWN"
        connection.capability_available = False
        connection.credential_ref = item.id
        item.institution_name = institution_name
        self.db.commit()
        return self._plaid_item_dict(item)

    def _plaid_item_dict(self, item: PlaidItem) -> dict[str, Any]:
        return {
            "id": item.id, "owner": item.owner, "provider": item.provider,
            "connection_id": item.connection_id, "item_id": item.item_id, "institution_name": item.institution_name,
            "sync_cursor_present": bool(item.sync_cursor), "sync_status": item.sync_status,
            "lifecycle_state": self._connection_state(item),
            "capability_available": bool(self._connection_for(item) and capability_available(self._connection_for(item))),
            "last_attempted_sync_at": item.last_attempted_sync_at.isoformat() if item.last_attempted_sync_at else None,
            "last_successful_sync_at": item.last_successful_sync_at.isoformat() if item.last_successful_sync_at else None,
            "provider_last_successful_update_at": item.provider_last_successful_update_at.isoformat() if item.provider_last_successful_update_at else None,
            "last_error_classification": item.last_error_classification,
        }

    def _connection_for(self, item: PlaidItem) -> FinanceConnection | None:
        return self.db.query(FinanceConnection).filter(FinanceConnection.id == item.connection_id).one_or_none() if item.connection_id else None

    def _connection_state(self, item: PlaidItem) -> str:
        connection = self._connection_for(item)
        if connection:
            return connection.lifecycle_state
        return "HEALTHY" if item.sync_status == "healthy" else "DEGRADED" if item.sync_status == "error" else "CONNECTED"

    def connection_projection(self, owner: str) -> dict[str, Any]:
        connections = self.db.query(FinanceConnection).filter(
            FinanceConnection.owner == owner, FinanceConnection.provider == "plaid",
        ).order_by(FinanceConnection.created_at.desc()).all()
        # A cancelled/expired Link attempt is historical state, not a second
        # owner-facing connection. Prefer a real provider-backed connection;
        # otherwise expose the newest pending attempt without assuming it is
        # healthy. This keeps multiple abandoned attempts from breaking the
        # Integration Center projection.
        provider_backed = [item for item in connections if item.lifecycle_state in {
            "CONNECTED", "SYNCING", "HEALTHY", "DEGRADED", "RECONNECT_REQUIRED",
        }]
        connection = (provider_backed[0] if provider_backed else (connections[0] if connections else None))
        if connection is None:
            return {
                "provider": "plaid", "lifecycle_state": "NOT_CONFIGURED",
                "capability_available": False, "connections": [],
                "connection_count": 0, "abandoned_authorization_count": 0,
            }
        connection_rows = [{
            "id": row.id,
            "provider": row.provider,
            "lifecycle_state": row.lifecycle_state,
            "provider_health": row.provider_health,
            "capability_available": capability_available(row),
            "last_successful_sync_at": row.last_successful_sync_at.isoformat() if row.last_successful_sync_at else None,
            "last_error_classification": row.last_error_classification,
        } for row in connections]
        # The aggregate is a readiness summary, not merely the newest row.
        # One unhealthy owned connection must prevent the owner-facing
        # projection from advertising Finance as ready.
        severity = {
            "NOT_CONFIGURED": 0, "AUTHORIZATION_REQUIRED": 1,
            "AUTHORIZATION_IN_PROGRESS": 2, "CONNECTED": 3,
            "SYNCING": 4, "HEALTHY": 5, "DEGRADED": 6,
            "RECONNECT_REQUIRED": 7,
        }
        representative = max(provider_backed or connections, key=lambda row: severity.get(row.lifecycle_state, 99))
        projection = {
            "id": representative.id, "provider": representative.provider,
            "lifecycle_state": representative.lifecycle_state,
            "provider_health": representative.provider_health,
            "capability_available": bool(provider_backed) and all(
                row.lifecycle_state in {"CONNECTED", "HEALTHY"} and capability_available(row)
                for row in provider_backed
            ),
            "last_successful_sync_at": representative.last_successful_sync_at.isoformat() if representative.last_successful_sync_at else None,
            "last_error_classification": representative.last_error_classification,
            "connections": connection_rows,
        }
        projection["connection_count"] = len(connections)
        projection["abandoned_authorization_count"] = sum(
            item.lifecycle_state == "AUTHORIZATION_IN_PROGRESS" for item in connections
        )
        return projection

    def list_plaid_items(self, owner: str) -> list[dict[str, Any]]:
        return [self._plaid_item_dict(item) for item in self.db.query(PlaidItem).filter(
            PlaidItem.owner == owner, PlaidItem.provider == "plaid",
        ).order_by(PlaidItem.created_at.asc()).all()]

    def coverage(self, owner: str, start: date | None = None, end: date | None = None) -> dict[str, Any]:
        query = self.db.query(FinanceTransaction).filter(
            FinanceTransaction.owner == owner, FinanceTransaction.provider_removed.is_(False),
        )
        rows = query.order_by(FinanceTransaction.transaction_date.asc()).all()
        dates = [row.transaction_date for row in rows]
        items = self.db.query(PlaidItem).filter(PlaidItem.owner == owner, PlaidItem.provider == "plaid").all()
        imported_accounts = self.db.query(FinanceAccount).filter(
            FinanceAccount.owner == owner, FinanceAccount.provider == "csv",
        ).all()
        # Inspect the canonical connection table independently of exchanged
        # PlaidItems. An authorization-required connection can legitimately
        # exist before token exchange, and its unhealthy state must still be
        # visible in Finance coverage rather than disappearing because there
        # is no provider item row yet.
        connections = self.db.query(FinanceConnection).filter(
            FinanceConnection.owner == owner, FinanceConnection.provider == "plaid",
        ).all()
        unhealthy = [
            connection for connection in connections
            if connection is not None and connection.lifecycle_state not in {"HEALTHY", "CONNECTED"}
        ]
        successful_items = [item for item in items if item.last_successful_sync_at is not None]
        imported_sources = [account for account in imported_accounts if account.last_synced_at is not None]
        requested_exceeds = (
            not dates
            or bool(start and start < dates[0])
            or bool(end and end > dates[-1])
        )
        limitations: list[str] = []
        if not items and not imported_accounts:
            limitations.append("no Plaid connection has been configured")
        if not successful_items and not imported_sources:
            limitations.append("transaction ingestion has not completed successfully")
        if unhealthy:
            limitations.append("one or more Plaid connections are unhealthy or require attention")
        if requested_exceeds:
            limitations.append("the requested date range extends beyond canonical transaction coverage")
        if limitations:
            coverage_state = "UNKNOWN" if not dates or not (successful_items or imported_sources) else "LIMITED"
        else:
            coverage_state = "AVAILABLE"
        successful_sync_times = [
            item.last_successful_sync_at
            for item in self.db.query(PlaidItem).filter(PlaidItem.owner == owner).all()
            if item.last_successful_sync_at
        ] + [
            account.last_synced_at
            for account in imported_sources
            if account.last_synced_at
        ]
        return {
            # `as_of` is the newest canonical ingestion timestamp regardless
            # of whether the owner used Plaid or a local CSV snapshot. It is
            # not a claim that CSV data is live-provider data.
            "as_of": max(successful_sync_times, default=None),
            "account_count": self.db.query(FinanceAccount).filter(FinanceAccount.owner == owner).count(),
            "transaction_date_start": dates[0].isoformat() if dates else None,
            "transaction_date_end": dates[-1].isoformat() if dates else None,
            "posted_count": sum(row.status == "posted" for row in rows),
            "pending_count": sum(row.status == "pending" for row in rows),
            "requested_range_exceeds_coverage": requested_exceeds,
            "coverage_state": coverage_state,
            "coverage_limitations": limitations,
            "ingestion_complete": bool(successful_items or imported_sources) and not unhealthy,
            "data_sources": [
                *({"source": "plaid", "live": True} for _ in successful_items),
                *({"source": "local_csv", "live": False} for _ in imported_sources),
            ],
            "connection": self.connection_projection(owner),
            "sync": self.list_plaid_items(owner),
        }

    def query_transactions(self, owner: str, *, start: date | None = None, end: date | None = None,
                           account_id: str | None = None, merchant: str | None = None,
                           status: str | None = None, limit: int = 50) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        query = self.db.query(FinanceTransaction).filter(
            FinanceTransaction.owner == owner, FinanceTransaction.provider_removed.is_(False),
        )
        if start: query = query.filter(FinanceTransaction.transaction_date >= start)
        if end: query = query.filter(FinanceTransaction.transaction_date <= end)
        if account_id: query = query.filter(FinanceTransaction.account_id == account_id)
        if merchant: query = query.filter(FinanceTransaction.merchant.ilike(f"%{merchant[:100]}%"))
        if status:
            status = status.lower()
            if status not in {"pending", "posted"}: raise FinanceError("status must be pending or posted")
            query = query.filter(FinanceTransaction.status == status)
        rows = query.order_by(FinanceTransaction.transaction_date.desc(), FinanceTransaction.created_at.desc()).limit(limit).all()
        return {"transactions": [self._transaction_dict(row, include_provider_metadata=False) for row in rows], "limit": limit, "coverage": self.coverage(owner, start, end)}

    def spending(self, owner: str, start: date, end: date, *, merchant: str | None = None, category: str | None = None) -> dict[str, Any]:
        query = self.db.query(FinanceTransaction).filter(
            FinanceTransaction.owner == owner, FinanceTransaction.provider_removed.is_(False),
            FinanceTransaction.status == "posted", FinanceTransaction.transaction_date >= start,
            FinanceTransaction.transaction_date <= end,
        )
        if merchant:
            query = query.filter(FinanceTransaction.merchant.ilike(f"%{merchant[:100]}%"))
        rows = query.all()
        totals: dict[str, Decimal] = {}
        by_category: dict[str, dict[str, Decimal]] = {}
        for row in rows:
            if row.direction != "outflow" or (category and row.provider_category != category): continue
            totals[row.currency] = totals.get(row.currency, Decimal("0")) + Decimal(row.amount)
            bucket = by_category.setdefault(row.provider_category or "uncategorized", {})
            bucket[row.currency] = bucket.get(row.currency, Decimal("0")) + Decimal(row.amount)
        result = {"start": start.isoformat(), "end": end.isoformat(), "posted_outflow_by_currency": {key: str(value) for key, value in totals.items()}, "posted_outflow_by_category": {category: {currency: str(value) for currency, value in values.items()} for category, values in by_category.items()}, "coverage": self.coverage(owner, start, end)}
        if merchant:
            result["merchant"] = merchant[:100]
        if category:
            result["category"] = category[:100]
        return result

    def cash_flow(self, owner: str, start: date, end: date) -> dict[str, Any]:
        rows = self.db.query(FinanceTransaction).filter(
            FinanceTransaction.owner == owner, FinanceTransaction.provider_removed.is_(False),
            FinanceTransaction.status == "posted", FinanceTransaction.transaction_date >= start,
            FinanceTransaction.transaction_date <= end,
        ).all()
        totals: dict[str, dict[str, Decimal]] = {}
        for row in rows:
            bucket = totals.setdefault(row.currency, {"inflow": Decimal("0"), "outflow": Decimal("0")})
            bucket[row.direction] += Decimal(row.amount)
        return {"start": start.isoformat(), "end": end.isoformat(), "by_currency": {
            currency: {"posted_inflow": str(values["inflow"]), "posted_outflow": str(values["outflow"]), "net_raw_flow": str(values["inflow"] - values["outflow"])}
            for currency, values in totals.items()
        }, "coverage": self.coverage(owner, start, end)}

    def read_finance(self, owner: str, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(params or {})
        today = date.today()
        start = _transaction_date(params.get("start")) if params.get("start") else today.replace(day=1)
        end = _transaction_date(params.get("end")) if params.get("end") else today
        if action == "coverage": return self.coverage(owner, start, end)
        if action == "transactions": return self.query_transactions(owner, start=start, end=end, merchant=params.get("merchant"), status=params.get("status"), limit=params.get("limit", 50))
        if action == "spending": return self.spending(owner, start, end, merchant=params.get("merchant"), category=params.get("category"))
        if action == "cash_flow": return self.cash_flow(owner, start, end)
        if action == "shared_expenses": return {"shared_expenses": self.list_shared_expenses(owner, _required_text(params.get("household_id"), "household_id"))}
        raise FinanceError("unsupported Finance read action")

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
                    FinanceTransaction.provider_removed.is_(False),
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
