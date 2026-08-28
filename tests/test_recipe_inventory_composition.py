from datetime import date, timedelta
import json
from decimal import Decimal

from core import database as cdb
from core import inventory_models  # noqa: F401 - register inventory tables
from src.inventory_service import InventoryNotFound, get_inventory_service
from tests.helpers.sqlite_db import make_temp_sqlite
from src.aci import canonical_recipe_read_answer
from src.intent_contracts import RecipeDraft, recipe_import_draft
from src.intent_contracts import compile_intent, resolve_intent


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


def test_expiring_inventory_composes_with_recipe_coverage_without_mutation():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    chicken = service.create_item(
        "alice", name="Chicken", domain="kitchen", item_kind="ingredient",
        default_unit="g",
    )
    rice = service.create_item(
        "alice", name="Rice", domain="kitchen", item_kind="ingredient",
        default_unit="g",
    )
    service.add_stock(
        "alice", chicken["id"], quantity="500", unit="g",
        idempotency_key="chicken-expiring",
        expiry_date=date.today() + timedelta(days=2),
    )
    recipe = service.create_recipe(
        "alice", name="Chicken Rice", servings="2", ingredients=[
            {"item_id": chicken["id"], "quantity": "400", "unit": "g"},
            {"item_id": rice["id"], "quantity": "200", "unit": "g"},
        ],
    )

    result = service.manage_recipes(
        {"action": "expiring_candidates", "expiry_days": 7}, owner="alice",
    )

    assert result["canonical_store"] == "inventory_service"
    assert result["expiry_days"] == 7
    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate["recipe_id"] == recipe["id"]
    assert candidate["can_make"] is False
    assert candidate["expiring_ingredients"][0]["name"] == "Chicken"
    assert {row["name"] for row in candidate["shortages"]} == {"rice"}
    assert service.get_recipe("alice", recipe["id"])["name"] == "Chicken Rice"


def test_expiring_recipe_result_has_a_human_renderer_distinct_from_raw_result():
    event = {
        "tool": "read_recipes",
        "exit_code": 0,
        "command": json.dumps({"action": "expiring_candidates"}),
        "output": json.dumps({
            "status": "SUCCESS",
            "candidates": [{
                "recipe_name": "Chicken Rice",
                "can_make": False,
                "shortages": [{"name": "Rice"}],
            }],
        }),
    }

    answer = canonical_recipe_read_answer([event])

    assert answer == (
        "Recipes using ingredients that are expiring soon:\n"
        "- Chicken Rice (missing ingredients)\n"
        "  Missing: Rice"
    )
    assert answer.startswith("Recipes using")
    assert not answer.startswith("{")


def test_recipe_import_prepare_accepts_schema_org_jsonld_without_persisting():
    draft = recipe_import_draft(
        '{"@type":"Recipe","name":"JSON Dinner","recipeYield":"4 servings",'
        '"recipeIngredient":["2 cups rice", "1 tsp salt"],'
        '"recipeInstructions":[{"@type":"HowToStep","text":"Cook the rice."}]}',
        source_url="https://example.test/recipe",
    )
    assert isinstance(draft, RecipeDraft)
    assert draft.name == "JSON Dinner"
    assert draft.source_url == "https://example.test/recipe"
    assert draft.provenance == "import_evidence"
    assert len(draft.ingredients) == 2


def test_recipe_import_prepare_extracts_jsonld_embedded_in_untrusted_html():
    html = '<html><script type="application/ld+json">{"@type":"Recipe","name":"HTML Dinner",'
    html += '"recipeIngredient":["1 cup rice"],"recipeInstructions":"Steam the rice."}</script></html>'
    draft = recipe_import_draft(html, source_url="https://example.test/html")
    assert isinstance(draft, RecipeDraft)
    assert draft.name == "HTML Dinner"
    assert draft.source_url == "https://example.test/html"


def test_recipe_import_commit_requires_validated_draft_and_verifies_readback():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    result = service.manage_recipes({"action": "commit_import", "draft": {
        "name": "Imported Dinner", "servings": 2,
        "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}],
        "instructions": "Cook it.", "source_url": "https://example.test/recipe",
    }}, owner="alice")
    assert result["success"] is True
    assert result["verification"]["status"] == "VERIFIED"
    assert service.manage_recipes({"action": "list"}, owner="alice")["recipes"][0]["name"] == "Imported Dinner"


def test_recipe_url_import_prepare_is_a_read_proposal_not_a_write():
    frame = compile_intent("import this recipe from https://example.test/recipe")
    assert frame.domain_concept == "RECIPE"
    resolved = resolve_intent(frame)
    assert resolved.action_id == "prepare_import"
    assert resolved.binding_name == "read_recipes"


def test_recipe_import_prepare_renderer_never_claims_persistence():
    event = {
        "tool": "read_recipes", "exit_code": 0,
        "command": json.dumps({"action": "prepare_import"}),
        "output": json.dumps({"status": "READY_FOR_REVIEW", "draft": {
            "name": "Review Dinner", "ingredients": [{"name": "rice"}],
        }}),
    }
    answer = canonical_recipe_read_answer([event])
    assert answer == "Prepared 'Review Dinner' as an unpersisted draft with 1 ingredient(s). Review it before committing."
    assert "saved" not in answer.lower()


def test_household_add_item_can_atomically_seed_requested_initial_stock():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)

    item = service.manage_inventory({
        "action": "add_item", "name": "Acceptance Tomatoes", "domain": "kitchen",
        "item_kind": "ingredient", "default_unit": "each",
        "initial_quantity": 3, "initial_unit": "each",
    }, owner="alice")["item"]

    overview = service.household_overview("alice")
    row = next(row for row in overview["items"] if row["id"] == item["id"])
    assert row["stock_quantity"] == "3.000000"
