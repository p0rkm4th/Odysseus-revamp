import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.finance_models import FinanceConnection
from routes import finance_routes


class LinkPlaid:
    def __init__(self):
        self.exchange_calls = []
        self.sync_calls = []

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
