from datetime import date, timedelta

from core import database as cdb
from core import inventory_models  # noqa: F401 - register inventory tables
from src.inventory_service import get_inventory_service
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


def test_pantry_grocery_crud_is_owner_scoped_and_does_not_fake_stock_changes():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    item = service.create_item("alice", name="Milk", domain="kitchen", item_kind="ingredient", shopping_list=True)
    assert item["shopping_list"] is True
    changed = service.update_item("alice", item["id"], shopping_list=False, category="Dairy")
    assert changed["shopping_list"] is False
    assert changed["category"] == "Dairy"
    assert service.get_item("alice", item["id"])["shopping_list"] is False
    try:
        service.update_item("bob", item["id"], shopping_list=True)
    except Exception as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("cross-owner inventory update must fail")


def test_model_facing_grocery_add_defaults_to_canonical_kitchen_item():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    result = service.manage_inventory({"action": "add_item", "name": "Rice"}, owner="alice")
    assert result["item"]["domain"] == "kitchen"
    assert result["item"]["item_kind"] == "ingredient"
    assert result["item"]["shopping_list"] is True
    assert [item["name"] for item in service.list_items("alice", list_name="grocery")] == ["Rice"]


def test_grocery_pantry_and_fridge_are_canonical_list_views():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    service.create_item("alice", name="Milk", domain="kitchen", item_kind="ingredient", storage_area="fridge", shopping_list=True)
    service.create_item("alice", name="Rice", domain="kitchen", item_kind="ingredient", storage_area="pantry")
    assert [row["name"] for row in service.list_items("alice", list_name="grocery")] == ["Milk"]
    assert [row["name"] for row in service.list_items("alice", list_name="fridge")] == ["Milk"]
    assert [row["name"] for row in service.list_items("alice", list_name="pantry")] == ["Rice"]
    assert service.list_items("bob", list_name="grocery") == []


def test_inventory_ui_has_pantry_and_grocery_crud_surfaces():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "static/js/inventory.js").read_text()
    for marker in ("Grocery list", "new-grocery", "shopping_list", "PATCH", "archive"):
        assert marker in source
