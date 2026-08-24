import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_realistic_osint_fixture_covers_empty_large_and_adversarial_content():
    fixture = json.loads((ROOT / "tests/fixtures/osint-realistic-content.json").read_text())
    assert {case["source_count"] for case in fixture["cases"]} >= {0, 17, 50}
    assert "LONG_WORD" in fixture["known_information"]
    assert "https://" in fixture["known_information"]
    assert "<script>" in fixture["report_excerpt"]


def test_shared_layout_contract_contains_intrinsic_sizing_and_responsive_rules():
    css = (ROOT / "static/style.css").read_text()
    assert ".hades-window-body" in css and "min-width:0" in css and "min-height:0" in css
    assert "overflow-wrap:anywhere" in css
    assert "min(100%,260px)" in css
    assert "--action-primary-background" in css
    assert "scrollbar-width:thin" in css


def test_osint_uses_structured_case_cards_and_dedicated_seed_section():
    js = (ROOT / "static/js/osint.js").read_text()
    assert "function knownInformation" in js
    assert "Known Information / Seed" in js
    assert "Open Case" in js
    assert "item.query || item.summary" not in js.split("function caseCard", 1)[1].split("async function caseDossier", 1)[0]
    assert "No sources yet" in js


def test_window_controls_have_tooltips_and_accessible_labels():
    js = (ROOT / "static/js/workspaceWindowManager.js").read_text()
    for label in ("Minimize", "Maximize or restore", "Snap left", "Snap right", "Close"):
        assert f'title="{label}"' in js
        assert f'aria-label="{label}"' in js
