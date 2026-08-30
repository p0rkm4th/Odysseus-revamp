from decimal import Decimal

from core import database as cdb
from src.intent_contracts import _recipe_ingredients, compile_intent
from src.inventory_service import get_inventory_service
from tests.helpers.sqlite_db import make_temp_sqlite


def test_named_recipe_detail_followup_resolves_to_canonical_get():
    frame = compile_intent("Reload. What is in Acceptance Mixed Amounts?", continuation=True)
    assert frame.domain_concept == "RECIPE"
    assert frame.operation_class == "READ"
    assert frame.entity_reference == "Acceptance Mixed Amounts"


def test_recipe_detail_resolves_unique_owner_scoped_name_but_not_duplicates():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    recipe = service.create_recipe(
        "alice", name="Named Dinner", servings=2,
        ingredients=[{"name": "rice", "quantity": 1, "unit": "cup"}],
        instructions="Cook.",
    )
    assert service.get_recipe("alice", "Named Dinner")["id"] == recipe["id"]
    service.create_recipe(
        "alice", name="Duplicate Dinner", servings=1,
        ingredients=[{"name": "salt", "amount_kind": "TO_TASTE"}], instructions="Season.",
    )
    service.create_recipe(
        "alice", name="Duplicate Dinner", servings=1,
        ingredients=[{"name": "pepper", "amount_kind": "TO_TASTE"}], instructions="Season.",
    )
    try:
        service.get_recipe("alice", "Duplicate Dinner")
    except Exception as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("ambiguous recipe name must not resolve")


def test_owner_recipe_language_preserves_truthful_amount_kinds_and_compounds():
    expected = {
        "some salt and pepper": [("salt", "UNSPECIFIED"), ("pepper", "UNSPECIFIED")],
        "salt and pepper to taste": [("salt", "TO_TASTE"), ("pepper", "TO_TASTE")],
        "oil as needed": [("oil", "AS_NEEDED")],
        "a pinch of cayenne": [("cayenne", "NOMINAL")],
        "a splash of milk": [("milk", "NOMINAL")],
        "a handful of parsley": [("parsley", "NOMINAL")],
        "butter for greasing": [("butter", "AS_NEEDED")],
        "flour for dusting": [("flour", "AS_NEEDED")],
    }
    for source, rows in expected.items():
        parsed = _recipe_ingredients(source, split_compact=False)
        assert [(row["name"], row["amount_kind"]) for row in parsed] == rows
        assert all(row["quantity"] is None and row["unit"] is None for row in parsed)
        assert all(row["source_text"] == source for row in parsed)

    assert _recipe_ingredients("about 2 cups flour", split_compact=False)[0] == {
        "name": "flour", "quantity": 2.0, "unit": "cups",
        "amount_kind": "APPROXIMATE", "source_text": "about 2 cups flour",
    }
    assert _recipe_ingredients("1-2 tbsp olive oil", split_compact=False)[0]["quantity_min"] == 1.0


def test_qualitative_recipe_readback_projection_and_scaling_are_non_fabricating():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    salt = service.create_item(
        "alice", name="Salt", domain="kitchen", item_kind="ingredient", default_unit="each",
    )
    service.add_stock("alice", salt["id"], quantity=1, unit="each", idempotency_key="salt-stock")
    recipe = service.create_recipe(
        "alice", name="Truthful Seasoning", servings=2,
        ingredients=[
            {"name": "salt", "amount_kind": "TO_TASTE", "source_text": "salt to taste"},
            {"name": "oil", "amount_kind": "AS_NEEDED", "source_text": "oil as needed"},
            {"name": "olive oil", "quantity_min": 1, "quantity_max": 2, "unit": "tbsp",
             "amount_kind": "RANGE", "source_text": "1-2 tbsp olive oil"},
        ], instructions="Season and cook.",
    )
    rows = service.get_recipe("alice", recipe["id"])["ingredients"]
    assert [(row["name"], row["amount_kind"], row["quantity"], row["source_text"])
            for row in rows] == [
        ("salt", "TO_TASTE", None, "salt to taste"),
        ("oil", "AS_NEEDED", None, "oil as needed"),
        ("olive oil", "RANGE", None, "1-2 tbsp olive oil"),
    ]
    scaled = service.manage_recipes(
        {"action": "scale", "recipe_id": recipe["id"], "servings": 4}, owner="alice",
    )
    assert scaled["scaled_ingredients"][0]["quantity"] is None
    assert scaled["scaled_ingredients"][0]["amount_kind"] == "TO_TASTE"
    assert scaled["scaled_ingredients"][2]["quantity_min"] == Decimal("29.573530")
    coverage = service.manage_recipes(
        {"action": "can_make", "recipe_id": recipe["id"]}, owner="alice",
    )
    assert coverage["can_make"] is False
    assert {row["name"] for row in coverage["shortages"]} == {"oil", "olive oil"}
    salt_shortage = next(row for row in coverage["shortages"] if row["name"] == "oil")
    assert salt_shortage["missing"] is None
    assert coverage["deductions"] == []


def test_qualitative_recipe_cook_does_not_decrement_fabricated_stock():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    salt = service.create_item(
        "alice", name="Salt", domain="kitchen", item_kind="ingredient", default_unit="each",
    )
    service.add_stock("alice", salt["id"], quantity=1, unit="each", idempotency_key="salt-stock")
    recipe = service.create_recipe(
        "alice", name="Salt To Taste", servings=1,
        ingredients=[{"name": "salt", "amount_kind": "TO_TASTE", "source_text": "salt to taste"}],
        instructions="Season.",
    )
    before = service.list_lots("alice", salt["id"])[0]["quantity"]
    result = service.cook("alice", recipe["id"], idempotency_key="cook-qualitative")
    after = service.list_lots("alice", salt["id"])[0]["quantity"]
    assert result["movement_ids"] == []
    assert after == before
