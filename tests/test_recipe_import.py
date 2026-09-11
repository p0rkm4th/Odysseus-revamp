from pathlib import Path

import pytest

from src.recipe_import import (
    extract_pdf_text,
    parse_model_recipe_proposal,
    parse_recipe_text,
    recipe_text_from_web_result,
)


def test_model_recipe_proposal_requires_explicit_concrete_ingredients():
    candidate = parse_model_recipe_proposal(
        "Spaghetti\n\nYou will need:\nSpaghetti pasta\nOlive oil\nGarlic (4 cloves)\n\nMissing Ingredients:\nSpaghetti pasta",
        name="spaghetti",
    )
    assert [item["name"] for item in candidate["ingredients"]] == [
        "Spaghetti pasta", "Olive oil", "Garlic",
    ]


def test_model_recipe_proposal_rejects_unstructured_prose():
    with pytest.raises(ValueError):
        parse_model_recipe_proposal("I can help you make dinner.", name="dinner")


def test_pasted_recipe_import_extracts_bounded_ingredients_and_instructions():
    result = parse_recipe_text("""Spaghetti night
Serves 2

Ingredients:
- 400 g spaghetti
- 2 cups tomato sauce
- 3 cloves garlic

Directions:
Boil the pasta and combine with sauce.
""")

    assert result["name"] == "Spaghetti night"
    assert result["servings"] == "2"
    assert [(row["name"], row["quantity"], row["unit"]) for row in result["ingredients"]] == [
        ("spaghetti", "400.000000", "g"),
        ("tomato sauce", "473.176473", "ml"),
        ("garlic", "3.000000", "count"),
    ]
    assert "Boil the pasta" in result["instructions"]


def test_pasted_recipe_import_requires_an_ingredients_section():
    with pytest.raises(ValueError, match="Ingredients"):
        parse_recipe_text("A paragraph about dinner with no structured list")


def test_pasted_recipe_without_heading_accepts_only_explicit_quantity_lines():
    result = parse_recipe_text("Quick pasta\n- 400 g spaghetti\n- 1 can sauce\nBoil for 10 minutes")
    assert [row["name"] for row in result["ingredients"]] == ["spaghetti", "sauce"]


def test_recipe_import_normalizes_unicode_fractions():
    result = parse_recipe_text("Pancakes\n\nIngredients:\n½ cup milk\n1½ cups flour")
    assert [(row["quantity"], row["unit"]) for row in result["ingredients"]] == [
        ("118.294118", "ml"), ("354.882355", "ml"),
    ]


def test_recipe_import_is_bounded():
    with pytest.raises(ValueError, match="24000"):
        parse_recipe_text("x" * 24_001)


def test_web_recipe_projection_recovers_structured_ingredient_list_after_text_flattening():
    text = recipe_text_from_web_result({
        "title": "Web pasta",
        "content": "Web pasta Ingredients 400 g spaghetti Directions boil.",
        "lists": [["400 g spaghetti", "1 can tomato sauce"], ["Home", "About"]],
    })
    result = parse_recipe_text(text)
    assert [row["name"] for row in result["ingredients"]] == ["spaghetti", "tomato sauce"]


def test_pdf_import_uses_existing_pdf_text_extractor(tmp_path: Path):
    pytest.importorskip("pypdf")
    # A malformed/empty file must fail closed rather than producing a recipe.
    path = tmp_path / "recipe.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(Exception):
        extract_pdf_text(str(path))
