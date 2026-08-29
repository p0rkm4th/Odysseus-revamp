from datetime import date, timedelta

from core import database as cdb
from core import inventory_models  # noqa: F401 - register inventory tables
from core.inventory_models import InventoryLocation
from src.inventory_service import InsufficientStock, get_inventory_service
from tests.helpers.sqlite_db import make_temp_sqlite


def test_household_overview_projects_canonical_stock_risk_and_history():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)

    rice = service.create_item(
        "alice", name="Rice", domain="kitchen", item_kind="ingredient",
        default_unit="kg", reorder_point="2",
    )
    service.add_stock(
        "alice", rice["id"], quantity="1", unit="kg", idempotency_key="add-rice",
        expiry_date=date.today() + timedelta(days=3),
    )
    service.create_item(
        "alice", name="Batteries", domain="household", item_kind="consumable",
        default_unit="each",
    )
    service.create_item(
        "bob", name="Private item", domain="household", item_kind="consumable",
    )

    result = service.household_overview("alice")

    assert result["canonical_store"] == "inventory_service"
    assert result["item_count"] == 2
    assert [row["item"]["name"] for row in result["low_stock"]] == ["Rice"]
    assert result["expiring_lots"][0]["item"]["name"] == "Rice"
    assert result["recent_activity"][0]["item"]["name"] == "Rice"
    assert result["authority_unchanged"] is True
    assert all(row["name"] != "Private item" for row in result["items"])

    history = service.inventory_history("alice")
    assert len(history) == 1
    assert history[0]["movement"]["source_kind"] == "stock_add"
    assert history[0]["provenance"]["source_id"] == "add-rice"


def test_household_projection_has_no_parallel_store_and_empty_state_is_grounded():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)

    result = service.household_overview("empty-owner")

    assert result["canonical_store"] == "inventory_service"
    assert result["scope"] == "kitchen_and_household"
    assert result["items"] == []
    assert result["low_stock"] == []
    assert result["expiring_lots"] == []
    assert result["recent_activity"] == []
    assert result["authority_unchanged"] is True


def test_household_workspace_uses_canonical_overview_and_common_states():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "static/js/intelligence.js").read_text()
    assert "'/api/inventory/overview?expiry_days=30'" in source
    for label in ("Items", "Recipes", "Low stock", "Expiring", "Reviewable intake", "Recent activity"):
        assert label in source
    assert "canonical_store" in source
    assert "hades-module-header" in source
    assert "hades-empty-state" in source


def test_household_mutations_read_back_from_the_same_canonical_inventory_owner():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    milk = service.create_item(
        "alice", name="Milk", domain="kitchen", item_kind="ingredient",
        default_unit="l",
    )

    first = service.add_stock(
        "alice", milk["id"], quantity="2", unit="l", idempotency_key="milk-add",
    )
    replay = service.add_stock(
        "alice", milk["id"], quantity="2", unit="l", idempotency_key="milk-add",
    )
    assert first["replayed"] is False
    assert replay["replayed"] is True
    assert service.household_overview("alice")["items"][0]["stock_quantity"] == "2000.000000"

    service.consume_stock(
        "alice", milk["id"], quantity="1", unit="l", idempotency_key="milk-use-1",
    )
    assert service.household_overview("alice")["items"][0]["stock_quantity"] == "1000.000000"

    service.consume_stock(
        "alice", milk["id"], quantity="1", unit="l", idempotency_key="milk-use-2",
    )
    assert service.household_overview("alice")["items"][0]["stock_quantity"] == "0"

    try:
        service.consume_stock(
            "alice", milk["id"], quantity="1", unit="l", idempotency_key="milk-use-3",
        )
    except InsufficientStock:
        pass
    else:
        raise AssertionError("over-consumption must fail closed")
    assert service.household_overview("alice")["items"][0]["stock_quantity"] == "0"


def test_household_overview_projects_owner_scoped_location_names_and_totals():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    with session_factory() as db:
        db.add(InventoryLocation(
            id="pantry-alice", owner="alice", name="Pantry",
            normalized_name="pantry", normalized_path="pantry",
        ))
        db.add(InventoryLocation(
            id="pantry-bob", owner="bob", name="Pantry",
            normalized_name="pantry", normalized_path="pantry",
        ))
        db.commit()
    rice = service.create_item(
        "alice", name="Rice", domain="kitchen", item_kind="ingredient",
        default_unit="kg", location_id="pantry-alice",
    )
    service.add_stock(
        "alice", rice["id"], quantity="2", unit="kg",
        idempotency_key="alice-rice", location_id="pantry-alice",
    )

    result = service.household_overview("alice")

    assert result["items"][0]["location_name"] == "Pantry"
    assert result["locations"] == [{
        "id": "pantry-alice", "name": "Pantry", "item_count": 1,
        "stock_quantity": "2000.000000",
    }]
    assert all(row["id"] != "pantry-bob" for row in result["locations"])
