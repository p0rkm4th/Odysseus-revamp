"""Shared theme/icon contract tests for the early UI acceptance gate."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_theme_module_defines_required_token_validation_and_live_accent_binding():
    theme = (ROOT / "static/js/theme.js").read_text()
    css = (ROOT / "static/style.css").read_text()
    for token in ("--accent", "--icon-primary", "--icon-selected", "--status-success", "--epistemic-observed"):
        assert token in theme and token in css
    assert "validateThemeColors" in theme
    assert "'--accent': accent" in theme


def test_semantic_icon_registry_covers_previous_plain_text_destinations():
    components = (ROOT / "static/js/ui-components.js").read_text()
    app = (ROOT / "static/app.js").read_text()
    for name in ("household", "itAssets", "network", "developer", "hades", "worldModel", "controlCenter"):
        assert name in components or name in app
    assert "iconSvg" in components
    assert "stroke=\"currentColor\"" in components
    assert "hydrateSemanticNavIcons" in app


def test_sidebar_plain_text_exceptions_are_hydrated_by_canonical_map():
    app = (ROOT / "static/app.js").read_text()
    for element_id in ("tool-household-btn", "tool-it-assets-btn", "tool-network-btn", "tool-developer-btn", "tool-hades-btn"):
        assert element_id in app
    assert "item.insertAdjacentHTML('afterbegin', iconSvg(name))" in app


def test_sidebar_destinations_are_grouped_without_replacing_existing_route_ids():
    app = (ROOT / "static/app.js").read_text()
    for label in ("PERSONAL", "COMMUNICATIONS", "TECHNOLOGY", "INVESTIGATION", "WORK", "KNOWLEDGE", "AGENT", "SYSTEM"):
        assert label in app
    assert "odysseus-sidebar-groups-v1" in app
    assert "section.dataset.grouped = '1'" in app
    assert "body.hidden = !next" in app


def test_runtime_build_projection_and_developer_diagnostics_are_non_secret():
    server = (ROOT / "app.py").read_text()
    intelligence = (ROOT / "static/js/intelligence.js").read_text()
    for field in ("source_commit", "image_id", "frontend_build_id", "ui_state_schema_version"):
        assert field in server and field in intelligence
    assert "ODYSSEUS_SOURCE_COMMIT" in server
    assert "ODYSSEUS_IMAGE_ID" in server
    assert "ODYSSEUS_FRONTEND_BUILD_ID" in server
