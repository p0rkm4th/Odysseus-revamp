from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shared_layout_assertion_helper_is_available_to_browser_harnesses():
    helper = (ROOT / "static/js/layoutAssertions.js").read_text()
    for name in ("assertNoOverlap", "assertContained", "assertVisible"):
        assert f"export function {name}" in helper


def test_osint_has_populated_empty_and_dossier_layout_hooks():
    source = (ROOT / "static/js/osint.js").read_text()
    for marker in ("osint-case-card", "osint-known-information", "osint-recent-section", "data-osint-session", "No sources yet"):
        assert marker in source
