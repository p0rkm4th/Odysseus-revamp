from pathlib import Path

import pytest

from src.recipe_import import extract_pdf_text, parse_recipe_text


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


def test_recipe_import_is_bounded():
    with pytest.raises(ValueError, match="24000"):
        parse_recipe_text("x" * 24_001)


def test_pdf_import_uses_existing_pdf_text_extractor(tmp_path: Path):
    pytest.importorskip("pypdf")
    # A malformed/empty file must fail closed rather than producing a recipe.
    path = tmp_path / "recipe.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(Exception):
        extract_pdf_text(str(path))
