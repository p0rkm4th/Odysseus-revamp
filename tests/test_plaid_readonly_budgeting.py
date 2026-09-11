from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from src.finance_service import FinanceService, FinanceError
from src.plaid_sync import PlaidSyncService
from src.plaid_transport import PlaidError
from core.finance_models import PlaidItem, PlaidLinkSession
from core.finance_models import FinanceAccount, FinanceConnection


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


def test_provider_freshness_never_uses_consent_expiration():
    assert PlaidSyncService._provider_update({
        "item": {"consent_expiration_time": "2030-01-01T00:00:00Z"},
    }) is None
    value = PlaidSyncService._provider_update({
        "item": {"consent_expiration_time": "2030-01-01T00:00:00Z"},
        "last_updated_at": "2026-09-10T18:30:00Z",
    })
    assert value.isoformat() == "2026-09-10T18:30:00"


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
    assert spending["posted_outflow_by_merchant"]["Cafe"] == {"USD": "10.0000", "EUR": "5.0000"}
    flow = svc.cash_flow("alice", date(2026, 9, 1), date(2026, 9, 30))
    assert flow["by_currency"]["USD"]["posted_inflow"] == "50.0000"
    assert flow["by_currency"]["USD"]["net_raw_flow"] == "40.0000"
    assert flow["by_currency"]["EUR"]["posted_outflow"] == "5.0000"
    assert svc.list_transactions("bob") == []
    with pytest.raises(FinanceError):
        svc.read_finance("alice", "shared_expenses", {})


def test_dining_out_category_group_does_not_return_all_spending(db):
    svc = FinanceService(db)
    account = svc.import_account("alice", {"provider": "fixture", "provider_account_id": "a", "currency": "USD"})
    for txid, category, amount in (
        ("restaurant", "Restaurants", "25"),
        ("fast-food", "Fast Food", "10"),
        ("rent", "Mortgage & Rent", "1500"),
    ):
        svc.import_transaction("alice", {
            "account_id": account["id"], "provider": "fixture", "provider_transaction_id": txid,
            "amount": amount, "direction": "outflow", "currency": "USD",
            "transaction_date": "2026-09-01", "merchant": txid,
            "provider_category": category, "status": "posted",
        })
    result = svc.spending("alice", date(2026, 9, 1), date(2026, 9, 30), category="dining_out")
    assert result["posted_outflow_by_currency"] == {"USD": "35.0000"}
    assert set(result["posted_outflow_by_category"]) == {"Restaurants", "Fast Food"}


def test_local_csv_fallback_is_canonical_idempotent_and_not_live_plaid(db):
    svc = FinanceService(db)
    csv_text = "date,amount,merchant,currency\n2026-09-01,12.50,Cafe,USD\n2026-09-01,12.50,Cafe,USD\n2026-09-02,-40.00,Payroll,USD\n"
    first = svc.import_csv("alice", csv_text, source_label="bank-export")
    second = svc.import_csv("alice", csv_text, source_label="bank-export")
    assert first["source"] == second["source"] == "local_csv"
    assert first["live_provider"] is False
    assert second["imported_count"] == 3
    assert len(svc.list_transactions("alice")) == 3
    coverage = svc.coverage("alice", date(2026, 9, 1), date(2026, 9, 2))
    assert coverage["coverage_state"] == "AVAILABLE"
    assert coverage["as_of"] is not None
    assert {source["source"] for source in coverage["data_sources"]} == {"local_csv"}


def test_local_csv_amount_column_uses_bank_signs_and_reimport_repairs_direction(db):
    svc = FinanceService(db)
    csv_text = (
        "Date,Description,Category,Amount,Status\n"
        "2026-09-09,Publix,Groceries,-25.72,Posted\n"
        "2026-09-09,Payroll,Income,2500.00,Posted\n"
        "2026-09-09,Publix Pending,Category Pending,-37.33,Pending\n"
    )
    svc.import_csv("alice", csv_text, source_label="owner-bank.csv")
    svc.import_csv("alice", csv_text, source_label="owner-bank.csv")

    rows = svc.query_transactions(
        "alice", start=date(2026, 9, 1), end=date(2026, 9, 30), merchant="Publix", limit=10,
    )["transactions"]
    assert len(rows) == 2
    assert {row["direction"] for row in rows} == {"outflow"}
    assert {row["status"] for row in rows} == {"posted", "pending"}
    spending = svc.spending("alice", date(2026, 9, 1), date(2026, 9, 30), merchant="Publix")
    assert spending["posted_outflow_by_currency"] == {"USD": "25.7200"}
    assert spending["pending_outflow_by_currency"] == {"USD": "37.3300"}
    assert spending["pending_outflow_count"] == 1
    assert spending["merchant"] == "Publix"


def test_ranked_transactions_returns_largest_posted_outflows_deterministically(db):
    svc = FinanceService(db)
    csv_text = (
        "Date,Description,Amount,Status\n"
        "09/01/2026,Small shop,-12.50,Posted\n"
        "09/02/2026,Larger shop,-125.00,Posted\n"
        "09/03/2026,Pending shop,-999.00,Pending\n"
        "09/04/2026,Payroll,2000.00,Posted\n"
    )
    svc.import_csv("alice", csv_text, source_label="ranked.csv")
    result = svc.read_finance("alice", "transactions", {
        "start": "2026-01-01", "end": "2026-12-31", "sort": "amount_desc",
        "direction": "outflow", "status": "posted", "limit": 10,
    })
    assert [row["merchant"] for row in result["transactions"]] == ["Larger shop", "Small shop"]
    assert all(row["status"] == "posted" and row["direction"] == "outflow" for row in result["transactions"])


def test_ranked_transactions_can_filter_category_without_exposing_full_ledger(db):
    svc = FinanceService(db)
    account = svc.import_account("alice", {"provider": "fixture", "provider_account_id": "a", "currency": "USD"})
    for txid, category, amount in (
        ("insurance", "Insurance", "130"),
        ("groceries", "Groceries", "300"),
    ):
        svc.import_transaction("alice", {
            "account_id": account["id"], "provider": "fixture", "provider_transaction_id": txid,
            "amount": amount, "direction": "outflow", "currency": "USD",
            "transaction_date": "2026-09-01", "merchant": txid,
            "provider_category": category, "status": "posted",
        })
    result = svc.read_finance("alice", "transactions", {
        "start": "2026-01-01", "end": "2026-12-31", "category": "Insurance",
        "sort": "amount_desc", "direction": "outflow", "status": "posted", "limit": 10,
    })
    assert [row["merchant"] for row in result["transactions"]] == ["insurance"]


def test_paycheck_read_returns_only_posted_paycheck_inflows(db):
    svc = FinanceService(db)
    account = svc.import_account("alice", {"provider": "fixture", "provider_account_id": "a", "currency": "USD"})
    for txid, category, amount, direction, status in (
        ("paycheck", "Paycheck", "2500", "inflow", "posted"),
        ("rent", "Mortgage & Rent", "1500", "outflow", "posted"),
        ("pending-pay", "Paycheck", "2500", "inflow", "pending"),
    ):
        svc.import_transaction("alice", {
            "account_id": account["id"], "provider": "fixture", "provider_transaction_id": txid,
            "amount": amount, "direction": direction, "currency": "USD",
            "transaction_date": "2026-09-01", "merchant": txid,
            "provider_category": category, "status": status,
        })
    result = svc.read_finance("alice", "transactions", {
        "start": "2026-01-01", "end": "2026-12-31", "category": "Paycheck",
        "direction": "inflow", "status": "posted", "limit": 20,
    })
    assert [row["merchant"] for row in result["transactions"]] == ["paycheck"]


def test_local_csv_accepts_common_bank_export_headers_and_debit_credit(db):
    svc = FinanceService(db)
    bank_export = (
        "Transaction Date,Description,Debit,Credit,Currency\n"
        "09/01/2026,7 Brew,$12.50,,USD\n"
        '09/02/2026,Payroll,,"2,000.00",USD\n'
    )
    imported = svc.import_csv("alice", bank_export, source_label="checking.csv")
    assert imported["imported_count"] == 2
    rows = sorted(svc.list_transactions("alice"), key=lambda row: row["merchant"])
    assert rows[0]["merchant"] == "7 Brew"
    assert rows[0]["amount"] == "12.5000"
    assert rows[0]["direction"] == "outflow"
    assert rows[1]["merchant"] == "Payroll"
    assert rows[1]["amount"] == "2000.0000"
    assert rows[1]["direction"] == "inflow"


def test_local_csv_accepts_bom_and_parenthesized_amount(db):
    svc = FinanceService(db)
    imported = svc.import_csv(
        "alice",
        "\ufeffPosted Date,Payee,Amount\n09/03/2026,Grocer,(45.20)\n",
        source_label="export.csv",
    )
    assert imported["imported_count"] == 1
    row = svc.list_transactions("alice")[0]
    assert row["amount"] == "45.2000"
    assert row["direction"] == "outflow"


def test_local_csv_fallback_is_atomic_when_a_later_row_is_invalid(db):
    svc = FinanceService(db)
    invalid = "date,amount,merchant\n2026-09-01,12.50,Cafe\nnot-a-date,4.00,Grocer\n"
    with pytest.raises(FinanceError, match="row 2"):
        svc.import_csv("alice", invalid, source_label="broken-export")
    assert svc.list_accounts("alice") == []
    assert svc.list_transactions("alice") == []


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
    assert projection["lifecycle_state"] == "RECONNECT_REQUIRED"
    assert projection["capability_available"] is False


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


def test_coverage_surfaces_unexchanged_plaid_connection_alongside_csv_data(db):
    db.add(FinanceConnection(
        id="conn-awaiting-link", owner="alice", provider="plaid",
        lifecycle_state="AUTHORIZATION_REQUIRED", provider_health="DEGRADED",
        capability_available=False,
    ))
    account = FinanceAccount(
        id="csv-account", owner="alice", provider="csv", provider_account_id="csv-1",
        display_name="Imported account", currency="USD", last_synced_at=datetime.now(timezone.utc),
    )
    db.add(account)
    db.commit()

    coverage = FinanceService(db).coverage("alice", date(2026, 9, 1), date(2026, 9, 30))
    assert coverage["data_sources"] == [{"source": "local_csv", "live": False}]
    assert "one or more Plaid connections are unhealthy or require attention" not in coverage["coverage_limitations"]
    assert coverage["ingestion_complete"] is True
    assert coverage["connection"]["connections"][0]["lifecycle_state"] == "AUTHORIZATION_REQUIRED"


def test_coverage_reports_pending_plaid_authorization_without_csv_as_auth_gate(db):
    db.add(FinanceConnection(
        id="conn-awaiting-link", owner="alice", provider="plaid",
        lifecycle_state="AUTHORIZATION_REQUIRED", provider_health="DEGRADED",
        capability_available=False,
    ))
    db.commit()

    coverage = FinanceService(db).coverage("alice", date(2026, 9, 1), date(2026, 9, 30))
    assert "Plaid authorization is required" in coverage["coverage_limitations"]
    assert "one or more Plaid connections are unhealthy or require attention" not in coverage["coverage_limitations"]
