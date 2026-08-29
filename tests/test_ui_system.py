from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_inventory_uses_shared_window_and_form_primitives():
    source = (ROOT / "static/js/inventory.js").read_text()
    for marker in (
        "inventory-pane hades-workspace-window",
        "inventory-header hades-window-titlebar",
        "inventory-tabs hades-module-tabs",
        "inventory-form hades-intake-panel",
        "hades-intake-field",
        "inventory-advanced",
        "hades-btn-primary",
        "hades-record-card",
        "hades-dialog",
        "hades-empty-state",
        "name | quantity | unit",
        "source_url",
        "requested_name",
        "recipes/import/prepare",
        "recipes/import/commit",
        "shopping-requirements",
        "needs review before anything can be saved",
        "missing_fields",
        "Couldn't import recipe",
        "Review Draft",
        "Retry import",
        "renderRecipeImportDraft",
        "recipe-review-ingredient-row",
        "Save reviewed recipe",
        "positive numeric quantity",
        "recipeReviewDraft",
        "Nothing has been saved yet",
        "recipes/import/commit",
        "recipeIngredientRow",
        "add-recipe-ingredient",
        "ingredient_name",
        "ingredient_quantity",
        "ingredient_unit",
        "RECIPE_UNITS = ['each', 'count', 'cup', 'tbsp', 'tsp', 'g', 'kg', 'ml', 'l', 'oz', 'lb']",
        'id="recipe-search"',
        "visibleRecipes",
        "<h4>Ingredients</h4>",
        "View source",
    ):
        assert marker in source
    assert "Review this unpersisted recipe draft" not in source
    assert "data-recipe-import-draft" in source
    assert "(?:\\\\.[0-9]+)?$/.test(quantity)" not in source


def test_work_uses_shared_prompt_and_keeps_canonical_records_secondary():
    source = (ROOT / "static/js/work.js").read_text()
    assert "import { styledPrompt } from './ui.js';" in source
    assert "window.prompt(" not in source
    assert "readableRecord" in source
    assert "work-technical-record" in source
    assert "Technical record" in source


def test_sidebar_tool_entries_have_one_intentional_icon():
    html = (ROOT / "static/index.html").read_text()
    sidebar = html.split('<nav class="sidebar"', 1)[1].split('</nav>', 1)[0]
    entries = re.findall(r'<div class="list-item" id="(tool-[^"]+)">(.*?)</div>', sidebar, re.S)
    assert entries
    for entry_id, body in entries:
        assert len(re.findall(r'<svg\b', body)) == 1, entry_id


def test_research_workspace_does_not_duplicate_security_destination():
    source = (ROOT / "static/js/workspaceRegistry.js").read_text()
    research = source.split("id: 'research'", 1)[1].split("},", 1)[0]
    assert "'securityResearch'" not in research
    assert "['securityResearch'" not in source


def test_semantic_nav_hydration_replaces_legacy_glyph_instead_of_appending():
    source = (ROOT / "static/app.js").read_text()
    assert "legacyIcon.replaceWith(nextIcon)" in source
    assert "item.insertAdjacentHTML('afterbegin', iconSvg(name));" in source
