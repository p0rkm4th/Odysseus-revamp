from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from src.finance_service import FinanceService, FinanceError
from src.plaid_sync import PlaidSyncService
from src.plaid_transport import PlaidError
from core.finance_models import PlaidItem, PlaidLinkSession
from core.finance_models import FinanceConnection


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class FakePlaid:
    def __init__(self, pages, *, mutate_once=False, fail_on=None):
        self.pages = list(pages)
        self.mutate_once = mutate_once
        self.mutated = False
        self.fail_on = fail_on
        self.calls = []
        self.successful_calls = 0

    def accounts_get(self, token):
        assert token == "secret-token"
        return {"accounts": [{"account_id": "pa-1", "name": "Checking", "type": "depository", "subtype": "checking", "balances": {"iso_currency_code": "USD"}}]}

    def item_get(self, token):
        return {"item": {"institution_id": "ins_1"}}

    def transactions_sync(self, token, cursor):
        self.calls.append(cursor)
        if self.mutate_once and not self.mutated and len(self.calls) == 2:
            self.mutated = True
            self.successful_calls = 0
            raise PlaidError("TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION")
        index = self.successful_calls
        if self.fail_on == index:
            raise PlaidError("PROVIDER_UNAVAILABLE")
        result = self.pages[index]
        self.successful_calls += 1
        return result


def _item(db, owner="alice"):
    return FinanceService(db).create_plaid_item(owner, "item-1", "secret-token", "Bank")


def _added(txid="tx-1", *, pending=False, pending_id=None, amount="12.50"):
    return {"transaction_id": txid, "account_id": "pa-1", "amount": amount, "iso_currency_code": "USD", "date": "2026-09-01", "name": "Cafe", "pending": pending, "pending_transaction_id": pending_id, "personal_finance_category": {"primary": "FOOD_AND_DRINK"}}


def test_sync_paginates_atomically_and_replays_without_duplicates(db):
    _item(db)
    fake = FakePlaid([
        {"added": [_added()], "modified": [], "removed": [], "has_more": True, "next_cursor": "c1"},
        {"added": [_added("tx-2", amount="4")], "modified": [], "removed": [], "has_more": False, "next_cursor": "c2"},
    ])
    result = PlaidSyncService(db, fake).sync("alice", "item-1")
    assert result["pages"] == 2
    svc = FinanceService(db)
    assert len(svc.list_transactions("alice")) == 2
    assert svc.list_plaid_items("alice")[0]["sync_cursor_present"] is True
    # A completed cursor with no new pages is a safe idempotent replay.
    fake.pages = [{"added": [], "modified": [], "removed": [], "has_more": False, "next_cursor": "c2"}]
    fake.successful_calls = 0
    PlaidSyncService(db, fake).sync("alice", "item-1")
    assert len(svc.list_transactions("alice")) == 2


def test_failed_later_page_preserves_previous_cursor_and_canonical_rows(db):
    _item(db)
    first = FakePlaid([{ "added": [_added()], "modified": [], "removed": [], "has_more": False, "next_cursor": "safe"}])
    PlaidSyncService(db, first).sync("alice", "item-1")
    failing = FakePlaid([
        {"added": [_added("tx-2")], "modified": [], "removed": [], "has_more": True, "next_cursor": "unsafe"},
        {"added": [_added("tx-3")], "modified": [], "removed": [], "has_more": False, "next_cursor": "never"},
    ], fail_on=1)
    with pytest.raises(PlaidError):
        PlaidSyncService(db, failing).sync("alice", "item-1")
    assert FinanceService(db).list_plaid_items("alice")[0]["sync_status"] == "error"
    assert FinanceService(db).list_plaid_items("alice")[0]["sync_cursor_present"] is True
    assert {row["provider_transaction_id"] for row in FinanceService(db).list_transactions("alice")} == {"tx-1"}


def test_pending_posted_removed_and_mutation_restart(db):
    _item(db)
    fake = FakePlaid([
        {"added": [_added("pending-1", pending=True, amount="20")], "modified": [], "removed": [], "has_more": False, "next_cursor": "p1"},
    ])
    PlaidSyncService(db, fake).sync("alice", "item-1")
    fake = FakePlaid([
        {"added": [_added("posted-1", pending=False, pending_id="pending-1", amount="20")], "modified": [], "removed": [], "has_more": True, "next_cursor": "p2"},
        {"added": [], "modified": [], "removed": [], "has_more": False, "next_cursor": "p3"},
    ], mutate_once=True)
    result = PlaidSyncService(db, fake).sync("alice", "item-1")
    assert result["restarts"] == 1
    rows = FinanceService(db).list_transactions("alice")
    assert [row["provider_transaction_id"] for row in rows] == ["posted-1"]


def test_deterministic_queries_are_currency_safe_and_owner_scoped(db):
    svc = FinanceService(db)
    account = svc.import_account("alice", {"provider": "fixture", "provider_account_id": "a", "currency": "USD"})
    for txid, amount, direction, currency, status in (("out", "10", "outflow", "USD", "posted"), ("in", "50", "inflow", "USD", "posted"), ("pending", "99", "outflow", "USD", "pending")):
        svc.import_transaction("alice", {"account_id": account["id"], "provider": "fixture", "provider_transaction_id": txid, "amount": amount, "direction": direction, "currency": currency, "transaction_date": "2026-09-01", "merchant": "Cafe", "status": status})
    svc.import_transaction("alice", {"account_id": account["id"], "provider": "fixture", "provider_transaction_id": "eur-out", "amount": "5", "direction": "outflow", "currency": "EUR", "transaction_date": "2026-09-01", "merchant": "Cafe", "status": "posted"})
    spending = svc.spending("alice", date(2026, 9, 1), date(2026, 9, 30))
    assert spending["posted_outflow_by_currency"] == {"USD": "10.0000", "EUR": "5.0000"}
    flow = svc.cash_flow("alice", date(2026, 9, 1), date(2026, 9, 30))
    assert flow["by_currency"]["USD"]["posted_inflow"] == "50.0000"
    assert flow["by_currency"]["USD"]["net_raw_flow"] == "40.0000"
    assert flow["by_currency"]["EUR"]["posted_outflow"] == "5.0000"
    assert svc.list_transactions("bob") == []
    with pytest.raises(FinanceError):
        svc.read_finance("alice", "shared_expenses", {})


def test_mutation_restart_is_bounded(db):
    _item(db)
    fake = FakePlaid([], mutate_once=False)
    fake.transactions_sync = lambda token, cursor: (_ for _ in ()).throw(PlaidError("TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"))
    with pytest.raises(PlaidError):
        PlaidSyncService(db, fake).sync("alice", "item-1", max_restarts=2)


def test_plaid_token_is_encrypted_and_never_in_owner_projection(db):
    item = _item(db)
    raw = db.connection().exec_driver_sql(
        "SELECT access_token FROM finance_plaid_items WHERE id = ?", (item["id"],)
    ).scalar_one()
    assert raw.startswith("enc:")
    projection = FinanceService(db).list_plaid_items("alice")[0]
    assert "access_token" not in projection
    assert "secret-token" not in str(projection)


def test_plaid_link_session_table_is_part_of_finance_schema(db):
    assert db.query(PlaidLinkSession).count() == 0


def test_connection_projection_keeps_each_unhealthy_connection_reconnectable(db):
    first = FinanceConnection(id="conn-healthy", owner="alice", provider="plaid", lifecycle_state="HEALTHY", provider_health="HEALTHY", capability_available=True)
    second = FinanceConnection(id="conn-reconnect", owner="alice", provider="plaid", lifecycle_state="RECONNECT_REQUIRED", provider_health="RECONNECT_REQUIRED", capability_available=False, last_error_classification="ITEM_LOGIN_REQUIRED")
    db.add_all([first, second]); db.commit()
    FinanceService(db).create_plaid_item("alice", "item-healthy", "secret-1", "Bank A", connection_id=first.id)
    FinanceService(db).create_plaid_item("alice", "item-reconnect", "secret-2", "Bank B", connection_id=second.id)
    second.lifecycle_state = "RECONNECT_REQUIRED"
    second.provider_health = "RECONNECT_REQUIRED"
    second.capability_available = False
    second.last_error_classification = "ITEM_LOGIN_REQUIRED"
    db.commit()

    projection = FinanceService(db).connection_projection("alice")
    assert {row["id"] for row in projection["connections"]} == {first.id, second.id}
    reconnect = next(row for row in projection["connections"] if row["id"] == second.id)
    assert reconnect["lifecycle_state"] == "RECONNECT_REQUIRED"
    assert reconnect["last_error_classification"] == "ITEM_LOGIN_REQUIRED"


def test_coverage_does_not_call_uningested_or_unhealthy_finance_ready(db):
    connection = FinanceConnection(id="conn-reconnect", owner="alice", provider="plaid", lifecycle_state="RECONNECT_REQUIRED", provider_health="RECONNECT_REQUIRED", capability_available=False)
    db.add(connection); db.commit()
    FinanceService(db).create_plaid_item("alice", "item-reconnect", "secret-2", "Bank B", connection_id=connection.id)
    connection.lifecycle_state = "RECONNECT_REQUIRED"
    connection.provider_health = "RECONNECT_REQUIRED"
    connection.capability_available = False
    db.commit()

    coverage = FinanceService(db).coverage("alice", date(2026, 9, 1), date(2026, 9, 30))
    assert coverage["coverage_state"] == "UNKNOWN"
    assert coverage["ingestion_complete"] is False
    assert coverage["requested_range_exceeds_coverage"] is True
    assert "transaction ingestion has not completed successfully" in coverage["coverage_limitations"]
    assert "one or more Plaid connections are unhealthy or require attention" in coverage["coverage_limitations"]
