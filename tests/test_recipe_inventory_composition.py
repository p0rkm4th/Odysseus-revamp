from datetime import date, timedelta
import json
import pytest
from decimal import Decimal

from core import database as cdb
from core import inventory_models  # noqa: F401 - register inventory tables
from src.inventory_service import InventoryNotFound, get_inventory_service
from tests.helpers.sqlite_db import make_temp_sqlite
from src.aci import (
    canonical_recipe_mutation_answer,
    canonical_recipe_read_answer,
    canonical_tool_result_projection,
    project_action_selection,
)
from src.intent_contracts import (
    RecipeDraft, recipe_import_draft, recipe_import_review, recipe_import_review_draft,
    recipe_import_review_draft_from_payload,
)
from src.intent_contracts import compile_intent, resolve_intent
from types import SimpleNamespace


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
    assert listed["status"] == "SUCCESS"
    assert listed["result_type"] == "recipe_list"
    assert listed["operation"] == "list"
    assert listed["canonical_store"] == "inventory_service"
    assert [row["name"] for row in listed["recipes"]] == ["Weeknight Chili"]

    searched = service.manage_recipes({"action": "search", "query": "chili"}, owner="alice")
    assert searched["status"] == "SUCCESS"
    assert searched["result_type"] == "recipe_search"
    assert searched["operation"] == "search"
    assert searched["canonical_store"] == "inventory_service"
    assert searched["recipes"][0]["id"] == recipe["id"]

    coverage = service.manage_recipes(
        {"action": "can_make", "recipe_id": recipe["id"]}, owner="alice"
    )
    assert coverage["can_make"] is True
    assert coverage["recipe_id"] == recipe["id"]
    assert coverage["shortages"] == []
    assert coverage["deductions"]
    assert coverage["result_type"] == "recipe_pantry_coverage"
    assert coverage["operation"] == "can_make"
    assert coverage["availability_status"] == "AVAILABLE"
    assert coverage["canonical_store"] == "inventory_service"

    missing = service.manage_recipes(
        {"action": "can_make", "recipe_id": recipe["id"], "servings": "4"},
        owner="alice",
    )
    assert missing["can_make"] is False
    assert missing["status"] == "SUCCESS"
    assert missing["availability_status"] == "MISSING_INGREDIENTS"
    assert {row["name"] for row in missing["shortages"]} == {"beans", "rice"}


def test_recipe_scale_is_read_only_deterministic_arithmetic_over_canonical_recipe():
    service, recipe = _recipe_fixture()

    scaled = service.manage_recipes(
        {"action": "scale", "recipe_id": recipe["id"], "servings": "6"},
        owner="alice",
    )

    assert scaled["status"] == "SUCCESS"
    assert scaled["result_type"] == "recipe_scaled_quantities"
    assert scaled["operation"] == "scale"
    assert scaled["canonical_store"] == "inventory_service"
    assert scaled["recipe_id"] == recipe["id"]
    assert scaled["servings"] == Decimal("6")
    assert [(row["name"], row["quantity"], row["unit"]) for row in scaled["scaled_ingredients"]] == [
        ("Beans", Decimal("1419.529419"), "ml"),
        ("Rice", Decimal("709.764708"), "ml"),
    ]
    assert service.get_recipe("alice", recipe["id"])["servings"] == Decimal("2")


def test_recipe_shopping_requirements_reuses_canonical_stock_shortages_without_writing():
    service, recipe = _recipe_fixture()

    result = service.manage_recipes(
        {"action": "shopping_requirements", "recipe_id": recipe["id"], "servings": "4"},
        owner="alice",
    )

    assert result["status"] == "SUCCESS"
    assert result["result_type"] == "recipe_shopping_requirements"
    assert result["operation"] == "shopping_requirements"
    assert result["canonical_store"] == "inventory_service"
    assert result["recipe_name"] == "Weeknight Chili"
    assert result["can_make"] is False
    assert {(row["name"], row["quantity"], row["unit"]) for row in result["missing_ingredients"]} == {
        ("beans", Decimal("473.176473"), "ml"), ("rice", Decimal("236.588236"), "ml"),
    }
    assert service.get_recipe("alice", recipe["id"])["name"] == "Weeknight Chili"


def test_recipe_detail_read_result_identifies_canonical_owner_and_operation():
    service, recipe = _recipe_fixture()

    result = service.manage_recipes(
        {"action": "get", "recipe_id": recipe["id"]}, owner="alice"
    )

    assert result["status"] == "SUCCESS"
    assert result["result_type"] == "recipe_detail"
    assert result["operation"] == "get"
    assert result["canonical_store"] == "inventory_service"
    assert result["recipe"]["id"] == recipe["id"]


def test_recipe_list_projection_preserves_bounded_refs_for_follow_up_resolution():
    projection = canonical_tool_result_projection("read_recipes", {
        "output": json.dumps({
            "status": "SUCCESS",
            "operation": "list",
            "canonical_store": "inventory_service",
            "recipes": [{"id": "recipe-1", "name": "Weeknight Chili", "servings": "2", "ingredients": []}],
        }),
    })

    assert projection["recipes"] == [{
        "id": "recipe-1",
        "name": "Weeknight Chili",
        "servings": "2",
    }]
    assert "ingredients" not in projection["recipes"][0]


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

    assert result["status"] == "SUCCESS"
    assert result["result_type"] == "recipe_expiring_candidates"
    assert result["operation"] == "expiring_candidates"
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


def test_expiring_recipe_result_contract_accepts_candidates_collection():
    from src.intent_contracts import validate_bound_result

    valid, reason = validate_bound_result(
        "read_recipes", "expiring_candidates",
        {"status": "SUCCESS", "candidates": [{"recipe_name": "Chicken Rice"}]},
    )

    assert valid is True
    assert reason == "SUCCESS"


def test_pantry_recipe_candidates_compose_current_stock_without_mutation():
    service, recipe = _recipe_fixture()
    result = service.manage_recipes({"action": "pantry_candidates"}, owner="alice")
    assert result["status"] == "SUCCESS"
    assert result["result_type"] == "recipe_pantry_candidates"
    assert result["operation"] == "pantry_candidates"
    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate["recipe_id"] == recipe["id"]
    assert candidate["can_make"] is True
    assert candidate["shortages"] == []
    assert service.get_recipe("alice", recipe["id"])["name"] == recipe["name"]


def test_recipe_shopping_requirements_renderer_is_human_readable_and_grounded():
    answer = canonical_recipe_read_answer([{
        "tool": "read_recipes", "exit_code": 0,
        "command": json.dumps({"action": "shopping_requirements"}),
        "output": json.dumps({
            "status": "SUCCESS", "result_type": "recipe_shopping_requirements",
            "recipe_name": "Chicken Rice", "can_make": False,
            "missing_ingredients": [{"name": "rice", "quantity": "2", "unit": "cup", "optional": False}],
        }),
    }])
    assert answer == "For Chicken Rice, you still need:\n- 2 cup rice"
    assert not answer.lstrip().startswith("{")


def test_pantry_candidates_renderer_groups_makeable_and_missing_recipes():
    answer = canonical_recipe_read_answer([{
        "tool": "read_recipes", "exit_code": 0,
        "command": json.dumps({"action": "pantry_candidates"}),
        "output": json.dumps({
            "status": "SUCCESS", "result_type": "recipe_pantry_candidates",
            "candidates": [
                {"recipe_name": "Eggs", "can_make": True, "shortages": []},
                {"recipe_name": "Pasta", "can_make": False, "shortages": [{"name": "tomato sauce"}]},
            ],
        }),
    }])
    assert answer == (
        "I checked 2 recorded recipes against your current stock.\n"
        "You can make:\n- Eggs\n\n"
        "Needs ingredients:\n- Pasta (missing: tomato sauce)"
    )


def test_cooking_history_renderer_fails_closed_without_events():
    answer = canonical_recipe_read_answer([{
        "tool": "read_recipes", "exit_code": 0,
        "command": json.dumps({"action": "cooking_history"}),
        "output": json.dumps({"status": "SUCCESS_EMPTY", "events": []}),
    }])
    assert answer == "I don't have any recorded cooking history, so I can't identify a recipe cooked last night."


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


def test_recipe_import_prepare_applies_explicit_name_override_without_persisting():
    draft = recipe_import_draft(
        '{"@type":"Recipe","name":"Page Title",'
        '"recipeIngredient":["1 cup rice"],'
        '"recipeInstructions":"Cook the rice."}',
        source_url="https://example.test/recipe",
        requested_name="Owner Chosen Dinner",
    )
    assert isinstance(draft, RecipeDraft)
    assert draft.name == "Owner Chosen Dinner"
    assert draft.source_url == "https://example.test/recipe"


def test_inventory_recipe_prepare_import_preserves_name_override_and_does_not_write():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    result = service.manage_recipes({
        "action": "prepare_import",
        "source_url": "https://example.test/recipe",
        "requested_name": "Owner Chosen Dinner",
        "source_text": (
            '{"@type":"Recipe","name":"Page Title",'
            '"recipeIngredient":["1 cup rice"],'
            '"recipeInstructions":"Cook the rice."}'
        ),
    }, owner="alice")
    assert result["status"] == "READY_FOR_REVIEW"
    assert result["draft"]["name"] == "Owner Chosen Dinner"
    assert result["draft"]["source_url"] == "https://example.test/recipe"
    assert service.manage_recipes({"action": "list"}, owner="alice")["recipes"] == []


def test_recipe_import_prepare_accepts_validated_draft_json_without_persisting():
    draft = recipe_import_draft(json.dumps({
        "name": "Photo Dinner", "servings": 2,
        "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}],
        "instructions": "Cook the rice.",
    }))
    assert isinstance(draft, RecipeDraft)
    assert draft.name == "Photo Dinner"


def test_recipe_import_prepare_accepts_fenced_validated_draft_json():
    draft = recipe_import_draft("```json\n" + json.dumps({
        "name": "Fenced Dinner", "servings": 1,
        "ingredients": [{"name": "salt", "quantity": 1, "unit": "tsp"}],
        "instructions": "Season.",
    }) + "\n```")
    assert isinstance(draft, RecipeDraft)
    assert draft.name == "Fenced Dinner"


def test_recipe_import_prepare_extracts_jsonld_embedded_in_untrusted_html():
    html = '<html><script type="application/ld+json">{"@type":"Recipe","name":"HTML Dinner",'
    html += '"recipeIngredient":["1 cup rice"],"recipeInstructions":"Steam the rice."}</script></html>'
    draft = recipe_import_draft(html, source_url="https://example.test/html")
    assert isinstance(draft, RecipeDraft)
    assert draft.name == "HTML Dinner"
    assert draft.source_url == "https://example.test/html"


def test_recipe_import_prepare_accepts_bounded_fetch_jsonld_projection():
    evidence = (
        '<!-- RECIPE_JSONLD:'
        '{"@type":"Recipe","name":"Source Dinner",'
        '"recipeIngredient":["2 cups rice"],'
        '"recipeInstructions":"Cook the rice."}'
        ' -->\n# Source Dinner\nSource: https://example.test/recipe\n'
    )
    draft = recipe_import_draft(evidence, source_url="https://example.test/recipe")
    assert isinstance(draft, RecipeDraft)
    assert draft.name == "Source Dinner"
    assert draft.source_url == "https://example.test/recipe"
    assert draft.provenance == "import_evidence"


def test_recipe_import_parses_unicode_and_mixed_quantities_without_guessing():
    assert recipe_import_draft(
        'Recipe: Fraction Dinner. Ingredients: ¾ cup flour, 1½ cups milk. '
        'Instructions: Mix and cook.'
    ).ingredients == (
        {"name": "flour", "quantity": 0.75, "unit": "cup"},
        {"name": "milk", "quantity": 1.5, "unit": "cups"},
    )


def test_recipe_import_keeps_commas_inside_schema_org_ingredient_items():
    draft = recipe_import_draft(
        '<!-- RECIPE_JSONLD:{"@type":"Recipe","name":"Comma Dinner",'
        '"recipeIngredient":["1 onion, finely diced", "2 cups chicken broth"],'
        '"recipeInstructions":"Cook it."} -->',
        source_url="https://example.test/comma-dinner",
    )
    assert draft is not None
    assert [item["name"] for item in draft.ingredients] == [
        "onion, finely diced", "chicken broth",
    ]


def test_recipe_import_strips_trailing_site_price_and_footnote_artifacts():
    draft = recipe_import_draft(
        '{"@type":"Recipe","name":"Clean Dinner",'
        '"recipeIngredient":["1 onion, diced (about 1 cup)* ($0.76)",'
        '"2 cloves garlic, minced ($0.12)"],'
        '"recipeInstructions":"Cook the onion and garlic."}'
    )
    assert isinstance(draft, RecipeDraft)
    assert [item["name"] for item in draft.ingredients] == [
        "onion, diced (about 1 cup)", "garlic, minced",
    ]


def test_recipe_inventory_accepts_clove_as_a_deterministic_count_unit():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    result = service.manage_recipes({
        "action": "add", "name": "Garlic Dinner", "servings": 2,
        "ingredients": [{"name": "garlic", "quantity": 2, "unit": "cloves"}],
        "instructions": "Cook it.",
    }, owner="alice")
    assert result["recipe"]["ingredients"][0]["unit"] == "count"
    assert result["recipe"]["ingredients"][0]["quantity"] == 2


def test_incomplete_recipe_import_returns_bounded_review_diagnostics():
    review = recipe_import_review(
        '<!-- RECIPE_JSONLD:{"@type":"Recipe","name":"Seasoned Dinner",'
        '"recipeIngredient":["1 cup rice", "salt and pepper"],'
        '"recipeInstructions":"Cook it."} -->',
        source_url="https://example.test/seasoned",
    )
    assert review["status"] == "NEEDS_REVIEW"
    assert review["name"] == "Seasoned Dinner"
    assert review["source_url"] == "https://example.test/seasoned"
    assert review["missing_fields"] == ["salt and pepper"]


def test_incomplete_recipe_prepare_preserves_requested_name_in_review_only():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    result = service.manage_recipes({
        "action": "prepare_import",
        "source_url": "https://example.test/seasoned",
        "requested_name": "Owner Dinner",
        "source_text": (
            '<!-- RECIPE_JSONLD:{"@type":"Recipe","name":"Page Dinner",'
            '"recipeIngredient":["salt and pepper"],'
            '"recipeInstructions":"Cook it."} -->'
        ),
    }, owner="alice")
    assert result["status"] == "NEEDS_REVIEW"
    assert result["review"]["requested_name"] == "Owner Dinner"
    assert result["draft"] is None
    assert service.manage_recipes({"action": "list"}, owner="alice")["recipes"] == []


def test_sectioned_qualitative_recipe_returns_editable_review_draft_without_persistence():
    source = (
        'Acceptance Taste Test\n\nIngredients\n'
        '- 1 cup rice\n- salt to taste\n- oil as needed\n\n'
        'Instructions\nCook the rice and season it.\n'
    )
    draft = recipe_import_review_draft(source)
    assert draft is not None
    assert draft["name"] == "Acceptance Taste Test"
    assert draft["ingredients"][0]["quantity"] == 1.0
    assert draft["ingredients"][1]["quantity"] == ""
    assert draft["ingredients"][1]["review_note"] == "to taste"
    assert draft["ingredients"][2]["quantity"] == ""
    assert draft["review_required"] is True

    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    prepared = service.manage_recipes(
        {"action": "prepare_import", "source_text": source}, owner="alice"
    )
    assert prepared["status"] == "NEEDS_REVIEW"
    assert prepared["draft"]["ingredients"][1]["quantity"] == ""
    assert service.manage_recipes({"action": "list"}, owner="alice")["recipes"] == []


def test_review_draft_ignores_serving_metadata_inside_copied_ingredients_section():
    source = (
        'Acceptance Web Paste Dinner\n★★★★★ 4.8 from 214 reviews\n\n'
        'Ingredients\nServes 4\n- 2 chicken breasts, boneless and skinless\n'
        '- 1½ cups rice\n- salt to taste\n- oil as needed\n\n'
        'Instructions\nSeason the chicken and cook the rice.\n'
    )
    draft = recipe_import_review_draft(source)
    assert draft is not None
    assert draft["servings"] == 4
    assert [item["name"] for item in draft["ingredients"]] == [
        "chicken breasts, boneless and skinless", "rice", "salt", "oil",
    ]


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


def test_recipe_import_commit_replay_is_idempotent_for_owner_source_and_name():
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    service = get_inventory_service(session_factory)
    draft = {
        "name": "Imported Dinner", "servings": 2,
        "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}],
        "instructions": "Cook it.", "source_url": "https://example.test/recipe",
    }

    first = service.manage_recipes({"action": "commit_import", "draft": draft}, owner="alice")
    replay = service.manage_recipes({"action": "commit_import", "draft": draft}, owner="alice")

    assert first["success"] is True
    assert replay["success"] is True
    assert replay["deduplicated"] is True
    assert replay["recipe"]["id"] == first["recipe"]["id"]
    assert len(service.manage_recipes({"action": "list"}, owner="alice")["recipes"]) == 1


def test_recipe_url_import_prepare_is_a_read_proposal_not_a_write():
    frame = compile_intent("import this recipe from https://example.test/recipe")
    assert frame.domain_concept == "RECIPE"
    resolved = resolve_intent(frame)
    assert resolved.action_id == "prepare_import"
    assert resolved.binding_name == "read_recipes"


def test_url_recipe_create_resolves_effectful_import_backed_action():
    frame = compile_intent(
        'Add this recipe to my recipe book, for the name, use '
        '"Chicken Cordon Bleu with Cheese Sauce": '
        'https://sundaysuppermovement.com/best-chicken-cordon-bleu-recipe/#recipe'
    )
    resolved = resolve_intent(frame)
    assert resolved.action_id == "commit_import"
    assert resolved.binding_name == "manage_recipes"


def test_url_recipe_create_projects_user_fields_into_canonical_choice_payload():
    """The model chooses a card; ACI carries explicit URL/name arguments."""
    query = (
        'Add this recipe to my recipe book, for the name, use '
        '"Chicken Cordon Bleu with Cheese Sauce": '
        'https://sundaysuppermovement.com/best-chicken-cordon-bleu-recipe/#recipe'
    )
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    projection = project_action_selection(
        intent={
            "intent_frame": frame.__dict__,
            "resolved_contract": {
                "binding": resolved.binding_name,
                "action_id": resolved.action_id,
                "reason": resolved.reason,
            },
        },
        relevant_tools=["manage_recipes"],
        disabled_tools=set(), owner="alice", active_run=None, query=query,
    )
    payload = projection.choice_map["A"]["payload"]
    assert projection.mode.value == "DIRECT_ACTION"
    assert payload == {
        "action": "commit_import",
        "requested_name": "Chicken Cordon Bleu with Cheese Sauce",
        "source_url": "https://sundaysuppermovement.com/best-chicken-cordon-bleu-recipe/#recipe",
    }


def test_generic_pantry_question_projects_direct_canonical_read():
    query = "can i make anything w what we got"
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    projection = project_action_selection(
        intent={"intent_frame": frame.as_dict(), "resolved_contract": resolved.as_dict()},
        relevant_tools=["read_recipes"], disabled_tools=set(), owner="alice",
        active_run=None, query=query,
    )
    assert projection.mode.value == "DIRECT_ACTION"
    assert projection.fast_path == {"action": "pantry_candidates"}


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


@pytest.mark.asyncio
async def test_chat_recipe_url_create_fetches_untrusted_source_before_canonical_mutation(monkeypatch):
    import src.tool_execution as tool_execution

    captured = {}
    calls = []

    async def fetch_source(url, *, owner):
        assert url == "https://recipes.example.test/chicken"
        assert owner == "alice"
        return (
            '{"@type":"Recipe","name":"URL Dinner","recipeYield":"2 servings",'
            '"recipeIngredient":["1 cup rice"],"recipeInstructions":"Cook the rice."}',
            None,
        )

    class FakeService:
        def manage_recipes(self, payload, *, owner):
            calls.append((dict(payload), owner))
            captured["payload"] = payload
            captured["owner"] = owner
            if payload.get("action") == "prepare_import":
                return {"status": "READY_FOR_REVIEW", "draft": {
                    "action": "add", "name": "URL Dinner", "servings": 2,
                    "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}],
                    "instructions": "Cook the rice.",
                    "source_url": "https://recipes.example.test/chicken",
                }}
            return {"recipe": {"id": "recipe-url-1"}}

        def get_recipe(self, owner, recipe_id):
            assert owner == "alice"
            assert recipe_id == "recipe-url-1"
            return {"id": recipe_id, "name": "URL Dinner"}

    monkeypatch.setattr("src.recipe_import_sources.fetch_recipe_source", fetch_source)
    monkeypatch.setattr("src.inventory_service.get_inventory_service", lambda: FakeService())

    tool, result = await tool_execution._execute_manage_recipes_binding(
        SimpleNamespace(
            content=json.dumps({
                "action": "add",
                "source_url": "https://recipes.example.test/chicken",
            })
        ),
        owner="alice",
    )

    assert tool == "manage_recipes"
    assert result["verified"] is True
    assert captured["owner"] == "alice"
    assert calls[0][0]["action"] == "prepare_import"
    assert calls[0][0]["source_url"] == "https://recipes.example.test/chicken"
    assert calls[0][0]["requested_name"] is None
    assert calls[1][0]["action"] == "commit_import"
    assert captured["payload"]["action"] == "commit_import"
    assert captured["payload"]["draft"]["name"] == "URL Dinner"
    assert captured["payload"]["draft"]["source_url"] == "https://recipes.example.test/chicken"
    assert captured["payload"]["draft"]["ingredients"][0]["name"] == "rice"


@pytest.mark.asyncio
async def test_chat_recipe_url_create_applies_explicit_owner_name_after_import(monkeypatch):
    import src.tool_execution as tool_execution

    captured = {}

    async def fetch_source(url, *, owner):
        return (
            '{"@type":"Recipe","name":"Page Title","recipeYield":"2 servings",'
            '"recipeIngredient":["1 cup rice"],"recipeInstructions":"Cook the rice."}',
            None,
        )

    class FakeService:
        def manage_recipes(self, payload, *, owner):
            captured["payload"] = payload
            if payload.get("action") == "prepare_import":
                return {"status": "READY_FOR_REVIEW", "draft": {
                    "action": "add", "name": "Chicken Cordon Bleu with Cheese Sauce", "servings": 2,
                    "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}],
                    "instructions": "Cook the rice.",
                    "source_url": "https://recipes.example.test/chicken",
                }}
            return {"recipe": {"id": "recipe-named-1"}}

        def get_recipe(self, owner, recipe_id):
            return {"id": recipe_id, "name": captured["payload"]["draft"]["name"]}

    monkeypatch.setattr("src.recipe_import_sources.fetch_recipe_source", fetch_source)
    monkeypatch.setattr("src.inventory_service.get_inventory_service", lambda: FakeService())
    tool, result = await tool_execution._execute_manage_recipes_binding(
        SimpleNamespace(content=json.dumps({
            "action": "add",
            "source_url": "https://recipes.example.test/chicken",
            "requested_name": "Chicken Cordon Bleu with Cheese Sauce",
        })),
        owner="alice",
    )
    assert tool == "manage_recipes"
    assert result["verified"] is True
    assert captured["payload"]["draft"]["name"] == "Chicken Cordon Bleu with Cheese Sauce"
    assert captured["payload"]["draft"]["source_url"] == "https://recipes.example.test/chicken"


@pytest.mark.asyncio
async def test_chat_recipe_url_prepare_review_never_reaches_commit(monkeypatch):
    import src.tool_execution as tool_execution

    calls = []

    async def fetch_source(url, *, owner):
        return "unstructured page evidence", None

    class FakeService:
        def manage_recipes(self, payload, *, owner):
            calls.append(payload)
            return {
                "status": "NEEDS_REVIEW", "draft": None,
                "review": {"missing_fields": ["verified recipe structure"]},
            }

    monkeypatch.setattr("src.recipe_import_sources.fetch_recipe_source", fetch_source)
    monkeypatch.setattr("src.inventory_service.get_inventory_service", lambda: FakeService())
    tool, result = await tool_execution._execute_manage_recipes_binding(
        SimpleNamespace(content=json.dumps({
            "action": "commit_import",
            "source_url": "https://recipes.example.test/incomplete",
        })),
        owner="alice",
    )

    assert tool == "manage_recipes"
    assert result["success"] is False
    assert "needs review" in result["error"]
    assert [call["action"] for call in calls] == ["prepare_import"]


@pytest.mark.asyncio
async def test_chat_incomplete_paste_returns_editable_review_draft_without_commit(monkeypatch):
    import src.tool_execution as tool_execution

    calls = []
    source = (
        "Acceptance Web Paste Dinner\n\nIngredients\n"
        "- 1 cup rice\n- salt to taste\n- oil as needed\n\n"
        "Instructions\nCook the rice and season it.\n"
    )

    class FakeService:
        def manage_recipes(self, payload, *, owner):
            calls.append((payload, owner))
            return {
                "status": "NEEDS_REVIEW",
                "draft": {
                    "action": "commit_import", "name": "Acceptance Web Paste Dinner",
                    "servings": 1,
                    "ingredients": [
                        {"name": "rice", "quantity": 1, "unit": "cup"},
                        {"name": "salt", "quantity": "", "unit": "each", "review_note": "to taste"},
                    ],
                    "instructions": "Cook the rice and season it.",
                    "review_required": True,
                    "review": {"missing_fields": ["salt (to taste)"]},
                },
            }

    monkeypatch.setattr("src.inventory_service.get_inventory_service", lambda: FakeService())
    tool, result = await tool_execution._execute_manage_recipes_binding(
        SimpleNamespace(content=json.dumps({
            "action": "commit_import", "review_required": True,
            "source_text": source,
        })),
        owner="alice",
    )

    assert tool == "manage_recipes"
    assert result["success"] is True
    assert result["data"]["status"] == "NEEDS_REVIEW"
    assert result["data"]["draft"]["review_required"] is True
    assert result["data"]["ui_event"] == "recipe_import_review"
    assert result["ui_event"] == "recipe_import_review"
    assert result["draft"]["name"] == "Acceptance Web Paste Dinner"
    assert calls == [({
        "action": "prepare_import", "source_text": source,
        "source_url": None, "requested_name": None,
    }, "alice")]


def test_incomplete_model_import_payload_becomes_review_draft_without_commit():
    draft = recipe_import_review_draft_from_payload({
        "name": "Acceptance Video Pancakes", "servings": 2,
        "ingredients": [
            {"name": "banana", "quantity": 1, "unit": "each"},
            {"name": "olive oil spray", "quantity": None, "unit": ""},
        ],
        "instructions": "Mix and cook.", "source_url": "https://www.youtube.com/watch?v=example",
    })
    assert draft is not None
    assert draft["review_required"] is True
    assert draft["ingredients"][1]["quantity"] == ""
    assert "olive oil spray" in draft["review"]["missing_fields"][0]
    assert draft["source_url"].startswith("https://")


@pytest.mark.asyncio
async def test_incomplete_model_import_is_routed_to_review_before_canonical_write(monkeypatch):
    import src.tool_execution as tool_execution

    calls = []

    class FakeService:
        def manage_recipes(self, payload, *, owner):
            calls.append(payload)
            raise ValueError("each recipe ingredient needs a numeric quantity")

    monkeypatch.setattr("src.inventory_service.get_inventory_service", lambda: FakeService())
    tool, result = await tool_execution._execute_manage_recipes_binding(
        SimpleNamespace(content=json.dumps({
            "action": "commit_import",
            "draft": {
                "name": "Acceptance Video Pancakes", "servings": 2,
                "ingredients": [
                    {"name": "banana", "quantity": 1, "unit": "each"},
                    {"name": "olive oil spray", "quantity": None, "unit": ""},
                ], "instructions": "Mix and cook.",
            },
        })),
        owner="alice",
    )

    assert tool == "manage_recipes"
    assert result["success"] is True
    assert result["data"]["status"] == "NEEDS_REVIEW"
    assert result["ui_event"] == "recipe_import_review"
    assert result["draft"]["ingredients"][1]["review_note"] == "quantity unspecified"
    assert calls == [{"action": "commit_import", "draft": {
        "name": "Acceptance Video Pancakes", "servings": 2,
        "ingredients": [
            {"name": "banana", "quantity": 1, "unit": "each"},
            {"name": "olive oil spray", "quantity": None, "unit": ""},
        ], "instructions": "Mix and cook.",
    }}]


def test_chat_review_draft_answer_is_truthful_and_not_a_recipe_mutation_claim():
    answer = canonical_recipe_mutation_answer([{
        "tool": "manage_recipes", "exit_code": 0,
        "command": '{"action":"commit_import"}',
        "output": json.dumps({
            "status": "NEEDS_REVIEW", "success": True,
            "action": "prepare_import", "draft": {
                "name": "Acceptance Web Paste Dinner",
                "ingredients": [{"name": "salt", "quantity": "", "review_note": "to taste"}],
                "review": {"missing_fields": ["salt (to taste)"]},
            },
        }),
    }])
    assert answer is not None
    assert "Prepared 'Acceptance Web Paste Dinner' for review" in answer
    assert "Nothing has been saved" in answer
    assert "Recorded recipe" not in answer


@pytest.mark.asyncio
async def test_youtube_recipe_source_uses_existing_transcript_owner(monkeypatch):
    import src.recipe_import_sources as sources

    async def transcript(url, video_id):
        assert video_id == "abc123"
        return {"success": True, "transcript": "Ingredients: 2 cups rice\nInstructions: Cook the rice."}

    monkeypatch.setattr("src.youtube_handler.extract_youtube_id", lambda url: "abc123")
    monkeypatch.setattr("src.youtube_handler.is_youtube_url", lambda url: True)
    monkeypatch.setattr("src.youtube_handler.extract_transcript_async", transcript)
    text, error = await sources.fetch_recipe_source("https://youtu.be/abc123", owner="alice")
    assert error is None
    assert "Cook the rice" in text


@pytest.mark.asyncio
async def test_youtube_recipe_source_composes_description_and_transcript_evidence(monkeypatch):
    import src.recipe_import_sources as sources

    async def transcript(url, video_id):
        return {"success": True, "transcript": "Ingredients: 2 cups rice\nInstructions: Cook the rice."}

    async def metadata(url):
        return {"success": True, "title": "Rice Dinner", "description": "A quick rice recipe."}

    monkeypatch.setattr("src.youtube_handler.extract_youtube_id", lambda url: "abc123")
    monkeypatch.setattr("src.youtube_handler.is_youtube_url", lambda url: True)
    monkeypatch.setattr("src.youtube_handler.extract_transcript_async", transcript)
    monkeypatch.setattr("src.youtube_handler.extract_video_metadata_async", metadata)
    text, error = await sources.fetch_recipe_source("https://youtu.be/abc123", owner="alice")
    assert error is None
    assert "Video title: Rice Dinner" in text
    assert "A quick rice recipe" in text
    assert "Cook the rice" in text


@pytest.mark.asyncio
async def test_youtube_recipe_source_accepts_description_when_transcript_unavailable(monkeypatch):
    import src.recipe_import_sources as sources

    async def transcript(url, video_id):
        return {"success": False, "error": "captions unavailable"}

    async def metadata(url):
        return {"success": True, "title": "Recipe video", "description": "Ingredients are listed below."}

    monkeypatch.setattr("src.youtube_handler.extract_youtube_id", lambda url: "abc123")
    monkeypatch.setattr("src.youtube_handler.is_youtube_url", lambda url: True)
    monkeypatch.setattr("src.youtube_handler.extract_transcript_async", transcript)
    monkeypatch.setattr("src.youtube_handler.extract_video_metadata_async", metadata)
    text, error = await sources.fetch_recipe_source("https://youtu.be/abc123", owner="alice")
    assert error is None
    assert "Ingredients are listed below" in text


def test_video_description_without_literal_ingredients_heading_gets_review_draft():
    source = """Video title: Banana Pancakes
Video description:
Nutrition: 500 kcal

One banana (100g)
Two medium eggs
200g reduced fat Greek yogurt (0%)
40g self raising flour
Olive oil spray
One passionfruit

METHOD
1. Mash the banana.
2. Mix in the eggs and yogurt.
3. Cook the pancakes until golden.
"""

    draft = recipe_import_review_draft(
        source,
        source_url="https://www.youtube.com/watch?v=BuTQZNP_6yI",
        requested_name="Acceptance Greek Yogurt Pancakes",
    )

    assert draft is not None
    assert draft["name"] == "Acceptance Greek Yogurt Pancakes"
    assert len(draft["ingredients"]) == 6
    assert any(item.get("review_note") == "quantity unspecified" for item in draft["ingredients"])
    assert draft["review_required"] is True


def test_video_description_with_requested_name_can_be_commit_ready():
    source = (
        "Video title: 2-Ingredient Homemade Pasta | Easy recipe\n\n"
        "Video description:\n"
        "Whipping up homemade pasta.\n\n"
        "Ingredients (for 2 people):\n"
        "* 160 g flour (1 cup + 1/4 cup)\n"
        "* 2 eggs\n\n"
        "Instructions:\n"
        "1. Create a well in the flour and crack in the eggs.\n"
        "2. Knead, rest, roll, cut, and cook the pasta."
    )
    draft = recipe_import_draft(
        source, source_url="https://www.youtube.com/watch?v=5YcsrFC2h5U",
        requested_name="Acceptance Homemade Pasta",
    )
    assert draft is not None
    assert draft.name == "Acceptance Homemade Pasta"
    assert len(draft.ingredients) == 2
    assert draft.source_url.endswith("5YcsrFC2h5U")


def test_video_description_uses_source_title_when_owner_does_not_rename_recipe():
    source = (
        "Video title: 2-Ingredient Homemade Pasta | Easy recipe\n\n"
        "Video description:\n"
        "Whipping up homemade pasta.\n\n"
        "Ingredients (for 2 people):\n"
        "* 160 g flour (1 cup + 1/4 cup)\n"
        "* 2 eggs\n\n"
        "Instructions:\n"
        "1. Create a well in the flour and crack in the eggs.\n"
        "2. Knead, rest, roll, cut, and cook the pasta."
    )

    draft = recipe_import_draft(
        source, source_url="https://www.youtube.com/watch?v=5YcsrFC2h5U"
    )

    assert draft is not None
    assert draft.name == "2-Ingredient Homemade Pasta | Easy recipe"


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
