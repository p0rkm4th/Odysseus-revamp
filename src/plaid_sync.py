"""Bounded, atomic Plaid Transactions Sync reconciliation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.database import utcnow_naive
from core.finance_models import FinanceAccount, FinanceConnection, FinanceTransaction, PlaidItem, SharedExpense
from src.finance_service import FinanceError, _currency, _money, _transaction_date
from src.plaid_transport import PlaidError, PlaidTransport
from src.integration_lifecycle import set_connection_state


class PlaidSyncService:
    def __init__(self, db: Session, transport: PlaidTransport):
        self.db = db
        self.transport = transport

    def _item(self, owner: str, item_id: str) -> PlaidItem:
        item = self.db.query(PlaidItem).filter(PlaidItem.owner == owner, or_(PlaidItem.id == item_id, PlaidItem.item_id == item_id)).one_or_none()
        if item is None:
            raise FinanceError("Plaid item not found")
        return item

    @staticmethod
    def _safe_account(row: dict[str, Any]) -> dict[str, Any]:
        currency = row.get("currency") or row.get("balances", {}).get("iso_currency_code")
        return {
            "provider_account_id": row.get("account_id"), "display_name": row.get("name") or row.get("official_name"),
            "account_type": ":".join(filter(None, [row.get("type"), row.get("subtype")])),
            "currency": currency,
        }

    def _normalized_transaction(self, row: dict[str, Any], account_map: dict[str, str], owner: str) -> dict[str, Any]:
        provider_id = str(row.get("transaction_id") or "").strip()
        account_id = account_map.get(str(row.get("account_id") or ""))
        currency = row.get("iso_currency_code") or row.get("unofficial_currency_code")
        raw_amount = row.get("amount")
        if not provider_id or not account_id or currency is None or raw_amount is None or not row.get("date"):
            raise FinanceError("malformed Plaid transaction")
        amount = Decimal(str(raw_amount))
        if not amount.is_finite():
            raise FinanceError("malformed Plaid amount")
        status = "pending" if bool(row.get("pending")) else "posted"
        category = row.get("personal_finance_category") or {}
        return {
            "owner": owner, "account_id": account_id, "provider": "plaid", "provider_transaction_id": provider_id,
            "amount": _money(abs(amount)), "direction": "outflow" if amount > 0 else "inflow",
            "currency": _currency(currency), "transaction_date": _transaction_date(row["date"]),
            "merchant": row.get("merchant_name") or row.get("name"), "description": row.get("original_description") or row.get("name") or "Plaid transaction",
            "status": status, "pending_transaction_id": row.get("pending_transaction_id"),
            "provider_category": category.get("primary") or category.get("detailed"),
            "category_metadata": {key: category[key] for key in ("primary", "detailed") if category.get(key)},
            "provider_metadata": {"provider": "plaid", "transaction_id": provider_id, "account_id": row.get("account_id")},
        }

    def sync(self, owner: str, item_id: str, *, max_pages: int = 50, max_updates: int = 5000, max_restarts: int = 2) -> dict[str, Any]:
        item = self._item(owner, item_id)
        connection = self.db.query(FinanceConnection).filter_by(id=item.connection_id).one_or_none() if item.connection_id else None
        original_cursor = item.sync_cursor
        item.last_attempted_sync_at = utcnow_naive()
        item.sync_status = "syncing"
        if connection:
            set_connection_state(connection, "SYNCING", provider_health="CHECKING", capability_available=False)
        self.db.commit()
        restarts = 0
        try:
            while True:
                try:
                    account_body = self.transport.accounts_get(item.access_token)
                    item_body = self.transport.item_get(item.access_token)
                    accounts = list(account_body.get("accounts") or [])
                    account_map = {str(row.get("account_id")): str(row.get("account_id")) for row in accounts}
                    pages: list[dict[str, Any]] = []
                    cursor = original_cursor
                    for _ in range(max_pages):
                        page = self.transport.transactions_sync(item.access_token, cursor)
                        pages.append(page)
                        updates = sum(len(page.get(key) or []) for key in ("added", "modified", "removed"))
                        if sum(sum(len(p.get(key) or []) for key in ("added", "modified", "removed")) for p in pages) > max_updates:
                            raise FinanceError("Plaid sync update bound exceeded")
                        if not page.get("has_more"):
                            break
                        cursor = page.get("next_cursor")
                        if not cursor:
                            raise FinanceError("Plaid sync page omitted next_cursor")
                    else:
                        raise FinanceError("Plaid sync page bound exceeded")
                    final_cursor = pages[-1].get("next_cursor") or original_cursor
                    break
                except PlaidError as exc:
                    if exc.classification == "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION" and restarts < max_restarts:
                        restarts += 1
                        continue
                    raise
            now = utcnow_naive()
            for raw in accounts:
                canonical = self._safe_account(raw)
                existing = self.db.query(FinanceAccount).filter(FinanceAccount.owner == owner, FinanceAccount.provider == "plaid", FinanceAccount.provider_account_id == canonical["provider_account_id"]).one_or_none()
                if existing is None:
                    existing = FinanceAccount(id=uuid4().hex, owner=owner, provider="plaid", provider_account_id=canonical["provider_account_id"])
                    self.db.add(existing)
                existing.display_name = canonical["display_name"]; existing.account_type = canonical["account_type"]; existing.currency = canonical["currency"]; existing.last_synced_at = now
                self.db.flush(); account_map[str(raw["account_id"])] = existing.id
            for page in pages:
                for raw in page.get("added") or []:
                    self._upsert(self._normalized_transaction(raw, account_map, owner))
                for raw in page.get("modified") or []:
                    self._upsert(self._normalized_transaction(raw, account_map, owner))
                for raw in page.get("removed") or []:
                    provider_id = str(raw.get("transaction_id") or "")
                    existing = self.db.query(FinanceTransaction).filter(FinanceTransaction.owner == owner, FinanceTransaction.provider == "plaid", FinanceTransaction.provider_transaction_id == provider_id).one_or_none()
                    if existing:
                        existing.provider_removed = True; existing.provider_removed_at = now
                        for projection in self.db.query(SharedExpense).filter(SharedExpense.source_transaction_id == existing.id, SharedExpense.revoked_at.is_(None)).all():
                            projection.needs_reconciliation = True
            item.sync_cursor = final_cursor; item.sync_status = "healthy"; item.last_successful_sync_at = now
            item.provider_last_successful_update_at = self._provider_update(item_body)
            item.last_error_classification = None
            connection = self.db.query(FinanceConnection).filter_by(id=item.connection_id).one_or_none() if item.connection_id else None
            if connection:
                set_connection_state(connection, "HEALTHY", provider_health="HEALTHY", capability_available=True, synced_at=now)
            self.db.commit()
            return {"item_id": item.item_id, "pages": len(pages), "added": sum(len(p.get("added") or []) for p in pages), "modified": sum(len(p.get("modified") or []) for p in pages), "removed": sum(len(p.get("removed") or []) for p in pages), "restarts": restarts, "cursor_present": bool(final_cursor)}
        except Exception as exc:
            self.db.rollback()
            item = self._item(owner, item_id)
            classification = getattr(exc, "classification", type(exc).__name__)[:128]
            item.sync_status = "error"; item.last_error_classification = classification
            connection = self.db.query(FinanceConnection).filter_by(id=item.connection_id).one_or_none() if item.connection_id else None
            if connection:
                reconnect = classification in {"ITEM_LOGIN_REQUIRED", "ITEM_LOCKED", "INVALID_CREDENTIALS", "ACCESS_NOT_GRANTED"}
                set_connection_state(connection, "RECONNECT_REQUIRED" if reconnect else "DEGRADED", provider_health="RECONNECT_REQUIRED" if reconnect else "DEGRADED", capability_available=False, error=classification)
            self.db.commit()
            raise

    def _upsert(self, values: dict[str, Any]) -> None:
        row = self.db.query(FinanceTransaction).filter(FinanceTransaction.owner == values["owner"], FinanceTransaction.account_id == values["account_id"], FinanceTransaction.provider == "plaid", FinanceTransaction.provider_transaction_id == values["provider_transaction_id"]).one_or_none()
        if row is None:
            row = FinanceTransaction(id=uuid4().hex, **values); self.db.add(row)
        else:
            for key, value in values.items():
                if key != "id" and key != "owner": setattr(row, key, value)
            row.provider_removed = False; row.provider_removed_at = None
        self.db.flush()
        if row.status == "posted" and row.pending_transaction_id:
            prior = self.db.query(FinanceTransaction).filter(FinanceTransaction.owner == row.owner, FinanceTransaction.provider == "plaid", FinanceTransaction.provider_transaction_id == row.pending_transaction_id).one_or_none()
            if prior and prior.id != row.id:
                prior.provider_removed = True; prior.provider_removed_at = utcnow_naive(); prior.superseded_by_transaction_id = row.provider_transaction_id
                for projection in self.db.query(SharedExpense).filter(SharedExpense.source_transaction_id == prior.id, SharedExpense.revoked_at.is_(None)).all():
                    projection.source_transaction_id = row.id; projection.amount = row.amount; projection.currency = row.currency; projection.transaction_date = row.transaction_date; projection.merchant = row.merchant

    @staticmethod
    def _provider_update(body: dict[str, Any]) -> datetime | None:
        # Consent expiration is an authorization deadline, not evidence that
        # Plaid's transaction data was updated. Never expose it as freshness.
        value = body.get("last_updated_at")
        if not value: return None
        try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError: return None
