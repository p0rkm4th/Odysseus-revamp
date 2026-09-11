from datetime import date, timedelta

import pytest

from core import database as cdb
from core import inventory_models  # noqa: F401 - register inventory tables
from src.inventory_service import InventoryError, get_inventory_service
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
    inventory_source = (Path(__file__).resolve().parents[1] / "static/js/inventory.js").read_text()
    assert "'/api/inventory/overview?expiry_days=30'" in source
    for label in ("Items", "Recipes", "Low stock", "Expiring", "Reviewable intake", "Recent activity"):
        assert label in source
    assert "Ingredient check" in inventory_source
    assert "recipe-ingredient" in inventory_source
    assert "canonical_store" in source
    assert "hades-module-header" in source
    assert "hades-empty-state" in source
    assert "/api/inventory/sharing" in inventory_source
    assert "Household sharing" in inventory_source
    assert 'data-resource="${resource}"' in inventory_source


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


def test_recipe_shaped_grocery_request_cannot_be_saved_as_literal_item():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)

    try:
        service.manage_inventory({
            "action": "add_item",
            "name": "everything needed to make chicken cordon bleu",
            "list_name": "grocery",
            "shopping_list": True,
        }, owner="alice")
    except Exception as exc:
        assert "recipe" in str(exc)
        assert "no grocery change" in str(exc)
    else:
        raise AssertionError("recipe-shaped request must not become a literal item")

    assert service.list_items("alice", list_name="grocery") == []


def test_all_grocery_write_boundaries_reject_recipe_placeholders():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    with pytest.raises(InventoryError, match="recipe rather than one grocery item"):
        service.create_item(
            "alice", name="everything needed to make spaghetti", domain="kitchen",
            item_kind="ingredient", shopping_list=True,
        )

    item = service.create_item(
        "alice", name="those ingredients", domain="kitchen",
        item_kind="ingredient", shopping_list=False,
    )
    with pytest.raises(InventoryError, match="individual grocery items"):
        service.update_item("alice", item["id"], shopping_list=True)


def test_recipe_queue_missing_by_name_compares_stock_and_queues_only_shortages():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    rice = service.create_item(
        "alice", name="Rice", domain="kitchen", item_kind="ingredient",
        default_unit="kg",
    )
    service.add_stock("alice", rice["id"], quantity="1", unit="kg", idempotency_key="rice-stock")
    service.create_recipe(
        "alice", name="Rice Bowl", servings="1",
        ingredients=[
            {"name": "Rice", "quantity": "0.5", "unit": "kg"},
            {"name": "Eggs", "quantity": "2", "unit": "each"},
        ],
    )
    result = service.manage_recipes(
        {"action": "queue_missing_by_name", "query": "rice bowl"}, owner="alice",
    )
    assert [row["name"] for row in result["missing"]["shortages"]] == ["eggs"]
    assert [row["name"] for row in service.list_items("alice", list_name="grocery")] == ["eggs"]

    with pytest.raises(InventoryError, match="individual grocery items"):
        service.create_item(
            "alice", name="the ingredients I am missing", domain="kitchen",
            item_kind="ingredient", shopping_list=True,
        )


def test_recipe_missing_by_name_compares_stock_without_queueing():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    service.create_recipe(
        "alice", name="Spaghetti", servings="1",
        ingredients=[{"name": "pasta", "quantity": "400", "unit": "g"}],
    )
    result = service.manage_recipes(
        {"action": "missing_by_name", "query": "spaghetti"}, owner="alice",
    )
    assert [row["name"] for row in result["missing"]["shortages"]] == ["pasta"]
    assert service.list_items("alice", list_name="grocery") == []


def test_recipe_shortages_can_be_reviewed_and_queued_without_changing_stock():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    rice = service.create_item("alice", name="Rice", domain="kitchen", item_kind="ingredient", default_unit="g")
    service.add_stock("alice", rice["id"], quantity=500, unit="g", idempotency_key="recipe-stock")
    recipe = service.create_recipe(
        "alice", name="Spaghetti", servings=2,
        ingredients=[
            {"item_id": rice["id"], "quantity": 250, "unit": "g"},
            {"name": "tomato sauce", "quantity": 1, "unit": "each"},
        ],
    )
    missing = service.missing_ingredients("alice", recipe["id"])
    assert missing["can_make"] is False
    assert [row["name"] for row in missing["shortages"]] == ["tomato sauce"]
    queued = service.queue_missing_ingredients("alice", recipe["id"])
    assert queued["stock_changed"] is False
    assert queued["count"] == 1
    assert [row["name"] for row in service.list_items("alice", list_name="grocery")] == ["tomato sauce"]
    replay = service.queue_missing_ingredients("alice", recipe["id"])
    assert replay["count"] == 1 and replay["queued"][0]["replayed"] is True
    assert str(service.list_lots("alice", rice["id"])[0]["quantity"]) == "500.000000"


def test_imported_recipe_reaches_canonical_stock_comparison_and_grocery_queue():
    from src.recipe_import import parse_recipe_text

    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    pasta = service.create_item(
        "alice", name="spaghetti", domain="kitchen", item_kind="ingredient",
        default_unit="g",
    )
    service.add_stock("alice", pasta["id"], quantity=200, unit="g", idempotency_key="import-stock")
    candidate = parse_recipe_text(
        "Weeknight spaghetti\n\nIngredients:\n400 g spaghetti\n1 can tomato sauce\n\nDirections:\nBoil."
    )
    recipe = service.create_recipe("alice", **candidate)
    missing = service.missing_ingredients("alice", recipe["id"])
    assert [row["name"] for row in missing["shortages"]] == ["spaghetti", "tomato sauce"]
    queued = service.queue_missing_ingredients("alice", recipe["id"])
    assert {row["name"] for row in service.list_items("alice", list_name="grocery")} == {"spaghetti", "tomato sauce"}
    assert queued["stock_changed"] is False
    assert str(service.list_lots("alice", pasta["id"])[0]["quantity"]) == "200.000000"


def test_multi_item_grocery_mutation_creates_individual_canonical_items():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    result = service.manage_inventory({
        "action": "add_item",
        "items": ["rice", "milk", "eggs"],
        "shopping_list": True,
        "domain": "kitchen",
        "item_kind": "ingredient",
    }, owner="alice")
    assert result["count"] == 3
    assert [item["name"] for item in result["items"]] == ["rice", "milk", "eggs"]
    rows = service.list_items("alice", list_name="grocery")
    assert {row["name"] for row in rows} == {"eggs", "milk", "rice"}


def test_multi_item_grocery_mutation_discards_model_recipe_phrase():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    result = service.manage_inventory({
        "action": "add_item",
        "items": ["spaghetti", "tomato sauce", "the ingredients I am missing"],
        "shopping_list": True,
        "domain": "kitchen",
        "item_kind": "ingredient",
    }, owner="alice")

    assert result["count"] == 2
    assert {row["name"] for row in service.list_items("alice", list_name="grocery")} == {
        "spaghetti", "tomato sauce",
    }


def test_named_kitchen_archive_removes_items_from_active_inventory_without_model_fallback():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    for name in ("basil-test", "dogfood test", "ketchup"):
        service.create_item("alice", name=name, domain="kitchen", item_kind="ingredient")
    result = service.manage_inventory({
        "action": "archive_item",
        "items": ["basil-test", "dogfood test", "ketchup"],
    }, owner="alice")
    assert result["count"] == 3
    assert service.list_items("alice", domain="kitchen") == []
    assert len(service.list_items("alice", domain="kitchen", include_archived=True)) == 3


def test_model_facing_stock_actions_resolve_canonical_name_and_replay_safely():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    service.manage_inventory({"action": "add_item", "name": "Rice"}, owner="alice")
    purchased = service.manage_inventory({
        "action": "add_stock", "name": "rice", "quantity": 2,
        "unit": "kg", "storage_area": "pantry", "idempotency_key": "buy-rice",
    }, owner="alice")
    replay = service.manage_inventory({
        "action": "add_stock", "name": "rice", "quantity": 2,
        "unit": "kg", "storage_area": "pantry", "idempotency_key": "buy-rice",
    }, owner="alice")
    assert purchased["replayed"] is False
    assert replay["replayed"] is True
    consumed = service.manage_inventory({
        "action": "consume_stock", "name": "rice", "quantity": 500,
        "unit": "g", "idempotency_key": "use-rice",
    }, owner="alice")
    assert consumed["replayed"] is False
    item = service.search_items("alice", "rice")[0]
    assert item["storage_area"] == "pantry"
    assert item["shopping_list"] is False
    pantry = service.list_items("alice", list_name="pantry")
    assert pantry[0]["stock_quantity"] == "1500.000000"


def test_remove_from_grocery_unqueues_item_without_deleting_owned_stock():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    item = service.create_item(
        "alice", name="Rice", domain="kitchen", item_kind="ingredient",
        shopping_list=True, storage_area="pantry", default_unit="kg",
    )
    service.add_stock("alice", item["id"], quantity="1", unit="kg", idempotency_key="rice-stock")

    removed = service.manage_inventory({
        "action": "remove_from_grocery", "name": "rice",
    }, owner="alice")
    assert removed["removed"] is True
    assert service.list_items("alice", list_name="grocery") == []
    assert service.list_items("alice", list_name="pantry")[0]["name"] == "Rice"

    replay = service.manage_inventory({
        "action": "remove_from_grocery", "name": "rice",
    }, owner="alice")
    assert replay["removed"] is False
    assert str(service.list_lots("alice", item["id"])[0]["quantity"]) == "1000.000000"


def test_grocery_pantry_and_fridge_are_canonical_list_views():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    service.create_item("alice", name="Milk", domain="kitchen", item_kind="ingredient", storage_area="fridge", shopping_list=True)
    service.create_item("alice", name="Rice", domain="kitchen", item_kind="ingredient", storage_area="pantry")
    assert [row["name"] for row in service.list_items("alice", list_name="grocery")] == ["Milk"]
    assert [row["name"] for row in service.list_items("alice", list_name="fridge")] == ["Milk"]
    assert [row["name"] for row in service.list_items("alice", list_name="pantry")] == ["Rice"]
    assert service.list_items("bob", list_name="grocery") == []


def test_inventory_lifecycle_depletion_queues_grocery_and_purchase_restores_stock():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    rice = service.create_item(
        "alice", name="Rice", domain="kitchen", item_kind="ingredient",
        default_unit="kg", storage_area="pantry",
    )
    service.add_stock("alice", rice["id"], quantity="1", unit="kg", idempotency_key="rice-add")
    consumed = service.consume_stock("alice", rice["id"], quantity="1", unit="kg", idempotency_key="rice-use")
    assert consumed["depleted"] is True
    assert [item["name"] for item in service.list_items("alice", list_name="grocery")] == ["Rice"]
    purchased = service.manage_inventory({
        "action": "add_stock", "item_id": rice["id"], "quantity": "2", "unit": "kg",
        "storage_area": "pantry", "idempotency_key": "rice-purchase",
    }, owner="alice")
    assert purchased["replayed"] is False
    assert service.get_item("alice", rice["id"])["shopping_list"] is False
    # Quantities are canonicalized to the item's base unit (grams), so the
    # same value is stable across chat, UI refresh, and restart.
    assert service.household_overview("alice")["items"][0]["stock_quantity"] == "2000.000000"
    assert service.list_items("alice", list_name="pantry")[0]["stock_quantity"] == "2000.000000"


def test_inventory_ui_has_pantry_and_grocery_crud_surfaces():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "static/js/inventory.js").read_text()
    for marker in ("Grocery list", "new-grocery", "shopping_list", "PATCH", "archive"):
        assert marker in source
