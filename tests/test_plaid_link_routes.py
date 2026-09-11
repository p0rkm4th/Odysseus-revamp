import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.finance_models import FinanceConnection, PlaidLinkSession
from routes import finance_routes
from src.finance_service import FinanceService


class LinkPlaid:
    def __init__(self):
        self.exchange_calls = []
        self.sync_calls = []
        self.fail_sync = False

    def link_token_create(self, client_user_id, *, access_token=None):
        self.client_user_id = client_user_id
        self.update_access_token = access_token
        return {"link_token": "link-sandbox-token", "expiration": "2026-09-10T01:30:00Z"}

    def item_public_token_exchange(self, public_token):
        self.exchange_calls.append(public_token)
        return {"access_token": "access-secret", "item_id": "item-live-1"}

    def accounts_get(self, access_token):
        assert access_token == "access-secret"
        return {"accounts": [{"account_id": "account-1", "name": "Checking", "type": "depository", "subtype": "checking", "balances": {"iso_currency_code": "USD"}}]}

    def item_get(self, access_token):
        return {"item": {"institution_id": "ins-1"}}

    def transactions_sync(self, access_token, cursor):
        if self.fail_sync:
            from src.plaid_transport import PlaidError
            raise PlaidError("PROVIDER_UNAVAILABLE")
        self.sync_calls.append(cursor)
        return {"added": [], "modified": [], "removed": [], "has_more": False, "next_cursor": "cursor-1"}


def _client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    plaid = LinkPlaid()
    monkeypatch.setattr(finance_routes, "require_user", lambda request: request.headers.get("x-owner", ""))
    app = FastAPI()
    app.state.auth_manager = type("Auth", (), {"is_admin": lambda self, user: user == "alice"})()
    app.include_router(finance_routes.setup_finance_routes(session_factory=Session, plaid_transport_factory=lambda: plaid))
    return TestClient(app), db, plaid, engine


def test_link_flow_binds_owner_stores_encrypted_access_token_and_syncs(monkeypatch):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        created = client.post("/api/finance/plaid/link-token", headers={"x-owner": "alice"})
        assert created.status_code == 200
        body = created.json()
        assert body["link_token"] == "link-sandbox-token"
        assert body["authorization_state"]
        assert body["connection_id"]
        assert "access_token" not in json.dumps(body)
        assert len(plaid.client_user_id) == 32

        exchanged = client.post(
            "/api/finance/plaid/link-exchange",
            headers={"x-owner": "alice"},
            json={"link_token": body["link_token"], "authorization_state": body["authorization_state"], "public_token": "public-sandbox-token"},
        )
        assert exchanged.status_code == 200
        result = exchanged.json()
        assert result["item"]["item_id"] == "item-live-1"
        assert result["sync"]["cursor_present"] is True
        assert "access-secret" not in json.dumps(result)
        raw = db.execute(text("SELECT access_token FROM finance_plaid_items")).scalar_one()
        assert raw.startswith("enc:")
        assert plaid.exchange_calls == ["public-sandbox-token"]
        assert len(plaid.sync_calls) == 1
    finally:
        db.close()
        engine.dispose()


def test_link_exchange_rejects_cross_owner_and_does_not_exchange(monkeypatch):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        created = client.post("/api/finance/plaid/link-token", headers={"x-owner": "alice"}).json()
        response = client.post(
            "/api/finance/plaid/link-exchange",
            headers={"x-owner": "bob"},
            json={"link_token": created["link_token"], "authorization_state": created["authorization_state"], "public_token": "public-sandbox-token"},
        )
        assert response.status_code == 400
        assert plaid.exchange_calls == []
    finally:
        db.close()
        engine.dispose()


def test_link_exchange_is_one_time(monkeypatch):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        created = client.post("/api/finance/plaid/link-token", headers={"x-owner": "alice"}).json()
        payload = {"link_token": created["link_token"], "authorization_state": created["authorization_state"], "public_token": "public-sandbox-token"}
        assert client.post("/api/finance/plaid/link-exchange", headers={"x-owner": "alice"}, json=payload).status_code == 200
        second = client.post("/api/finance/plaid/link-exchange", headers={"x-owner": "alice"}, json=payload)
        assert second.status_code == 400
        assert plaid.exchange_calls == ["public-sandbox-token"]
    finally:
        db.close()
        engine.dispose()


def test_reconnect_uses_update_mode_and_same_connection(monkeypatch):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        created = client.post("/api/finance/plaid/link-token", headers={"x-owner": "alice"}).json()
        payload = {"link_token": created["link_token"], "authorization_state": created["authorization_state"], "public_token": "public-sandbox-token"}
        assert client.post("/api/finance/plaid/link-exchange", headers={"x-owner": "alice"}, json=payload).status_code == 200
        connection = db.query(FinanceConnection).filter_by(owner="alice", provider="plaid").one()
        connection.lifecycle_state = "RECONNECT_REQUIRED"
        db.commit()
        repair = client.post(f"/api/finance/plaid/link-token?connection_id={connection.id}", headers={"x-owner": "alice"}).json()
        assert plaid.update_access_token == "access-secret"
        repaired = client.post("/api/finance/plaid/link-exchange", headers={"x-owner": "alice"}, json={"link_token": repair["link_token"], "authorization_state": repair["authorization_state"]})
        assert repaired.status_code == 200
        assert repaired.json()["item"]["connection_id"] == connection.id
        assert plaid.exchange_calls == ["public-sandbox-token"]
    finally:
        db.close()
        engine.dispose()


def test_pending_connection_reuses_same_connection_for_initial_authorization(monkeypatch):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        pending = FinanceConnection(
            id="pending-connection", owner="alice", provider="plaid",
            lifecycle_state="AUTHORIZATION_REQUIRED",
        )
        db.add(pending)
        db.commit()
        response = client.post(
            "/api/finance/plaid/link-token?connection_id=pending-connection",
            headers={"x-owner": "alice"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["connection_id"] == "pending-connection"
        assert plaid.update_access_token is None
        assert db.query(FinanceConnection).filter_by(owner="alice", provider="plaid").count() == 1
        assert db.query(PlaidLinkSession).filter_by(connection_id="pending-connection").count() == 1
    finally:
        db.close()
        engine.dispose()


def test_unqualified_link_open_reuses_pending_connection_without_provider_item(monkeypatch):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        pending = FinanceConnection(
            id="pending-connection", owner="alice", provider="plaid",
            lifecycle_state="AUTHORIZATION_REQUIRED",
        )
        db.add(pending)
        db.commit()

        response = client.post("/api/finance/plaid/link-token", headers={"x-owner": "alice"})
        assert response.status_code == 200
        assert response.json()["connection_id"] == "pending-connection"
        assert db.query(FinanceConnection).filter_by(owner="alice", provider="plaid").count() == 1
    finally:
        db.close()
        engine.dispose()


def test_missing_plaid_credentials_do_not_leave_new_connection_row(monkeypatch):
    from src.plaid_transport import PlaidError

    client, db, _plaid, engine = _client(monkeypatch)

    class MissingCredentials:
        def link_token_create(self, *_args, **_kwargs):
            raise PlaidError("PLAID_CREDENTIALS_MISSING", "Plaid credentials are not configured")

    try:
        from fastapi import FastAPI
        app = FastAPI()
        app.state.auth_manager = type("Auth", (), {"is_admin": lambda self, user: user == "alice"})()
        app.include_router(finance_routes.setup_finance_routes(
            session_factory=sessionmaker(bind=engine),
            plaid_transport_factory=MissingCredentials,
        ))
        response = TestClient(app).post(
            "/api/finance/plaid/link-token", headers={"x-owner": "alice"},
        )
        assert response.status_code == 503
        assert db.query(FinanceConnection).filter_by(owner="alice", provider="plaid").count() == 0
    finally:
        db.close()
        engine.dispose()


def test_exchange_consumes_continuation_when_initial_sync_fails(monkeypatch):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        created = client.post("/api/finance/plaid/link-token", headers={"x-owner": "alice"}).json()
        plaid.fail_sync = True
        response = client.post("/api/finance/plaid/link-exchange", headers={"x-owner": "alice"}, json={
            "link_token": created["link_token"], "authorization_state": created["authorization_state"], "public_token": "public-sandbox-token",
        })
        assert response.status_code == 503
        session = db.query(PlaidLinkSession).filter_by(owner="alice").one()
        assert session.consumed_at is not None
        assert session.exchange_status == "COMPLETED"
    finally:
        db.close()
        engine.dispose()


def test_exchange_claim_blocks_replay_before_provider_dispatch(monkeypatch):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        created = client.post("/api/finance/plaid/link-token", headers={"x-owner": "alice"}).json()
        row = db.query(PlaidLinkSession).filter_by(owner="alice").one()
        row.exchange_status = "IN_PROGRESS"
        db.commit()
        response = client.post(
            "/api/finance/plaid/link-exchange",
            headers={"x-owner": "alice"},
            json={
                "link_token": created["link_token"],
                "authorization_state": created["authorization_state"],
                "public_token": "public-sandbox-token",
            },
        )
        assert response.status_code == 400
        assert plaid.exchange_calls == []
    finally:
        db.close()
        engine.dispose()


def test_exchange_reuses_committed_item_after_callback_interruption(monkeypatch):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        created = client.post("/api/finance/plaid/link-token", headers={"x-owner": "alice"}).json()
        # Model a process interruption after the provider credential was
        # committed but before the continuation was consumed.
        connection = db.query(FinanceConnection).filter_by(owner="alice", provider="plaid").one()
        FinanceService(db).create_plaid_item("alice", "item-live-1", "access-secret", connection_id=connection.id)
        row = db.query(PlaidLinkSession).filter_by(owner="alice").one()
        row.exchange_status = "IN_PROGRESS"
        db.commit()
        recovered = client.post(
            "/api/finance/plaid/link-exchange",
            headers={"x-owner": "alice"},
            json={
                "link_token": created["link_token"],
                "authorization_state": created["authorization_state"],
                "public_token": "public-sandbox-token",
            },
        )
        assert recovered.status_code == 200
        assert plaid.exchange_calls == []
        assert recovered.json()["item"]["item_id"] == "item-live-1"
    finally:
        db.close()
        engine.dispose()


def test_authenticated_owner_can_import_local_csv_fallback(monkeypatch):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        response = client.post(
            "/api/finance/csv/import",
            headers={"x-owner": "alice"},
            json={
                "source_label": "checking-export.csv",
                "csv": "date,amount,merchant\n2026-09-01,12.50,Cafe\n2026-09-02,-100.00,Payroll\n",
            },
        )
        assert response.status_code == 201
        result = response.json()["import"]
        assert result["source"] == "local_csv"
        assert result["live_provider"] is False
        assert result["imported_count"] == 2
        assert client.get("/api/finance/transactions", headers={"x-owner": "alice"}).status_code == 200
        assert client.get("/api/finance/transactions", headers={"x-owner": "bob"}).json()["transactions"] == []
        assert "access_token" not in json.dumps(result)
    finally:
        db.close()
        engine.dispose()


def test_admin_can_configure_plaid_without_secret_response(monkeypatch, tmp_path):
    client, db, plaid, engine = _client(monkeypatch)
    try:
        import src.plaid_config as config
        monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "plaid_config.json")
        response = client.put(
            "/api/finance/plaid/config",
            headers={"x-owner": "alice"},
            json={"client_id": "client-id", "secret": "secret-value", "environment": "sandbox", "client_name": "Hades Test"},
        )
        assert response.status_code == 200
        result = response.json()
        assert result == {"configured": True, "environment": "sandbox", "client_name": "Hades Test", "source": "stored"}
        assert "secret-value" not in response.text
        raw = (tmp_path / "plaid_config.json").read_text()
        assert raw.startswith("{") and "secret-value" not in raw and "enc:" in raw
        assert client.get("/api/finance/plaid/config", headers={"x-owner": "alice"}).json()["configured"] is True
        denied = client.put("/api/finance/plaid/config", headers={"x-owner": "bob"}, json={"client_id": "x", "secret": "y"})
        assert denied.status_code == 403
    finally:
        db.close()
        engine.dispose()
