from decimal import Decimal

from core import database as cdb
from core import inventory_models  # noqa: F401 - register inventory tables
from src.inventory_service import InventoryNotFound, get_inventory_service
from tests.helpers.sqlite_db import make_temp_sqlite


def _recipe_fixture():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    beans = service.create_item(
        "alice", name="Beans", domain="kitchen", item_kind="ingredient",
        default_unit="cup",
    )
    rice = service.create_item(
        "alice", name="Rice", domain="kitchen", item_kind="ingredient",
        default_unit="cup",
    )
    service.add_stock(
        "alice", beans["id"], quantity="2", unit="cup", idempotency_key="beans-stock",
    )
    service.add_stock(
        "alice", rice["id"], quantity="1", unit="cup", idempotency_key="rice-stock",
    )
    recipe = service.create_recipe(
        "alice", name="Weeknight Chili", servings="2", ingredients=[
            {"item_id": beans["id"], "quantity": "2", "unit": "cup"},
            {"item_id": rice["id"], "quantity": "1", "unit": "cup"},
        ],
    )
    return service, recipe


def test_recipe_reads_and_pantry_coverage_use_one_persisted_inventory_owner():
    service, recipe = _recipe_fixture()

    listed = service.manage_recipes({"action": "list"}, owner="alice")
    assert [row["name"] for row in listed["recipes"]] == ["Weeknight Chili"]

    searched = service.manage_recipes({"action": "search", "query": "chili"}, owner="alice")
    assert searched["recipes"][0]["id"] == recipe["id"]

    coverage = service.manage_recipes(
        {"action": "can_make", "recipe_id": recipe["id"]}, owner="alice"
    )
    assert coverage["can_make"] is True
    assert coverage["recipe_id"] == recipe["id"]
    assert coverage["shortages"] == []
    assert coverage["deductions"]

    missing = service.manage_recipes(
        {"action": "can_make", "recipe_id": recipe["id"], "servings": "4"},
        owner="alice",
    )
    assert missing["can_make"] is False
    assert {row["name"] for row in missing["shortages"]} == {"beans", "rice"}


def test_recipe_scale_is_read_only_deterministic_arithmetic_over_canonical_recipe():
    service, recipe = _recipe_fixture()

    scaled = service.manage_recipes(
        {"action": "scale", "recipe_id": recipe["id"], "servings": "6"},
        owner="alice",
    )

    assert scaled["recipe_id"] == recipe["id"]
    assert scaled["servings"] == Decimal("6")
    assert [(row["name"], row["quantity"], row["unit"]) for row in scaled["scaled_ingredients"]] == [
        ("Beans", Decimal("1419.529419"), "ml"),
        ("Rice", Decimal("709.764708"), "ml"),
    ]
    assert service.get_recipe("alice", recipe["id"])["servings"] == Decimal("2")


def test_recipe_owner_scope_does_not_leak_across_inventory_service_reads():
    service, recipe = _recipe_fixture()

    assert service.manage_recipes({"action": "list"}, owner="bob")["recipes"] == []
    try:
        service.manage_recipes({"action": "get", "recipe_id": recipe["id"]}, owner="bob")
    except InventoryNotFound as exc:
        assert str(exc) == "recipe not found"
    else:
        raise AssertionError("recipe crossed owner boundary")
