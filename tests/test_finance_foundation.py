import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.finance_models import FinanceAccount, FinanceTransaction
from src.finance_service import FinanceError, FinanceService
from routes import finance_routes


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


def _account(svc, owner, provider_id="acct-1"):
    return svc.import_account(owner, {
        "provider": "fixture",
        "provider_account_id": provider_id,
        "display_name": "Checking",
        "account_type": "checking",
        "currency": "USD",
    })


def _transaction(svc, owner, account_id, provider_id="txn-1", amount="42.1050"):
    return svc.import_transaction(owner, {
        "account_id": account_id,
        "provider": "fixture",
        "provider_transaction_id": provider_id,
        "amount": amount,
        "currency": "USD",
        "transaction_date": "2026-09-09",
        "merchant": "Market",
        "status": "posted",
        "provider_metadata": {"fixture": True},
    })


def test_finance_schema_is_private_by_default_and_decimal_safe(db):
    transaction_columns = {
        column["name"]: column for column in inspect(db.bind).get_columns("finance_transactions")
    }
    assert transaction_columns["owner"]["nullable"] is False
    svc = FinanceService(db)
    account = _account(svc, "alice")
    transaction = _transaction(svc, "alice", account["id"])
    assert transaction["amount"] == "42.1050"
    assert transaction["currency"] == "USD"
    assert FinanceTransaction.owner.property.columns[0].nullable is False
    assert FinanceAccount.owner.property.columns[0].nullable is False


def test_import_is_idempotent_and_reconciles_provider_identity(db):
    svc = FinanceService(db)
    account = _account(svc, "alice")
    first = _transaction(svc, "alice", account["id"])
    second = _transaction(svc, "alice", account["id"], amount="43.2500", provider_id="txn-1")
    assert second["id"] == first["id"]
    assert second["amount"] == "43.2500"
    assert len(svc.list_transactions("alice")) == 1

    bob_account = _account(svc, "bob", provider_id="acct-1")
    bob_tx = _transaction(svc, "bob", bob_account["id"], provider_id="txn-1")
    assert bob_tx["id"] != second["id"]

    with pytest.raises(FinanceError, match="merchant or description"):
        svc.import_transaction("alice", {
            "account_id": account["id"], "provider": "fixture",
            "provider_transaction_id": "bad", "amount": "1",
            "currency": "USD", "transaction_date": "2026-09-09",
            "status": "posted",
        })
    with pytest.raises(FinanceError, match="currency"):
        svc.import_transaction("alice", {
            "account_id": account["id"], "provider": "fixture",
            "provider_transaction_id": "bad-currency", "amount": "1",
            "currency": "US", "transaction_date": "2026-09-09",
            "merchant": "Market", "status": "posted",
        })


def test_membership_sharing_is_explicit_bounded_and_revocable(db):
    svc = FinanceService(db)
    household = svc.create_household("alice", "December home")
    household_id = household["household_id"]
    svc.add_member("alice", household_id, "bob")
    other = svc.create_household("carol", "Carol home")
    assert svc.list_memberships("bob")[0]["household_id"] == household_id

    account = _account(svc, "alice")
    private = _transaction(svc, "alice", account["id"])
    assert svc.list_transactions("bob") == []
    with pytest.raises(FinanceError, match="membership"):
        svc.list_shared_expenses("carol", household_id)
    with pytest.raises(FinanceError, match="source owner"):
        svc.share_transaction("alice", private["id"], other["household_id"])

    shared = svc.share_transaction(
        "alice", private["id"], household_id, label="Household groceries",
    )
    assert svc.list_shared_expenses("bob", household_id) == [shared]
    assert svc.list_shared_expenses("carol", other["household_id"]) == []
    assert "account_id" not in shared
    assert "provider" not in shared
    assert svc.list_transactions("bob") == []
    with pytest.raises(FinanceError, match="private Finance"):
        svc.share_transaction("bob", private["id"], household_id)

    svc.revoke_shared_expense("alice", shared["id"])
    assert svc.list_shared_expenses("bob", household_id) == []
    assert len(svc.list_transactions("alice")) == 1


def test_projection_is_owner_and_household_scoped(db):
    svc = FinanceService(db)
    household = svc.create_household("alice", "Home")
    svc.add_member("alice", household["household_id"], "bob")
    account = _account(svc, "alice")
    tx = _transaction(svc, "alice", account["id"])
    svc.share_transaction("alice", tx["id"], household["household_id"])

    alice = svc.read_projection("alice", household["household_id"])
    bob = svc.read_projection("bob", household["household_id"])
    assert len(alice["private_transactions"]) == 1
    assert "provider_metadata" not in alice["private_transactions"][0]
    assert bob["private_transactions"] == []
    assert len(bob["shared_expenses"]) == 1
    assert bob["shared_expenses"][0]["status"] == "posted"
    assert bob["shared_expenses"][0]["source_provider"] == "fixture"
    assert "provider_metadata" not in bob["private_transactions"]
    assert svc.read_projection("carol")["private_transactions"] == []


def test_authenticated_finance_routes_enforce_owner_and_household_scope(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    api = FastAPI()

    def fake_require_user(request):
        user = request.headers.get("x-user")
        if not user:
            raise HTTPException(401, "Not authenticated")
        return user

    monkeypatch.setattr(finance_routes, "require_user", fake_require_user)
    api.include_router(finance_routes.setup_finance_routes(session_factory=Session))
    client = TestClient(api)
    alice = {"x-user": "alice"}
    bob = {"x-user": "bob"}
    carol = {"x-user": "carol"}

    assert client.get("/api/finance/accounts").status_code == 401
    household = client.post("/api/finance/households", headers=alice, json={"name": "Home"}).json()
    household_id = household["membership"]["household_id"]
    assert client.post(
        f"/api/finance/households/{household_id}/members",
        headers=alice, json={"user_id": "bob"},
    ).status_code == 201
    account = client.post(
        "/api/finance/accounts/import", headers=alice,
        json={"provider": "fixture", "provider_account_id": "acct", "currency": "USD"},
    ).json()["account"]
    transaction = client.post(
        "/api/finance/transactions/import", headers=alice,
        json={
            "account_id": account["id"], "provider": "fixture",
            "provider_transaction_id": "txn", "amount": "12.34",
            "currency": "USD", "transaction_date": "2026-09-09",
            "merchant": "Market", "status": "pending",
        },
    ).json()["transaction"]
    shared = client.post(
        f"/api/finance/transactions/{transaction['id']}/share", headers=alice,
        json={"household_id": household_id},
    ).json()["expense"]
    assert client.get("/api/finance/transactions", headers=bob).json()["transactions"] == []
    assert len(client.get(
        f"/api/finance/households/{household_id}/shared-expenses", headers=bob,
    ).json()["expenses"]) == 1
    assert client.get(
        f"/api/finance/households/{household_id}/shared-expenses", headers=carol,
    ).status_code == 404
    assert client.delete(
        f"/api/finance/shared-expenses/{shared['id']}", headers=alice,
    ).status_code == 204
    assert client.get(
        f"/api/finance/households/{household_id}/shared-expenses", headers=bob,
    ).json()["expenses"] == []
