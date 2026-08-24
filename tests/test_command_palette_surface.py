from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_existing_search_surface_exposes_canonical_navigation_commands():
    source = (ROOT / "static/js/search-chat.js").read_text()
    for label, target in (
        ("Open Hades overview", "tool-hades-btn"),
        ("Open Work / Life", "tool-work-btn"),
        ("Open Network", "tool-network-btn"),
        ("Open Developer", "tool-developer-btn"),
    ):
        assert label in source
        assert target in source
    assert "navigateCommand" in source


def test_command_palette_invokes_existing_module_buttons_not_private_execution():
    source = (ROOT / "static/js/search-chat.js").read_text()
    assert "button.click()" in source
    assert "ActionSpec" in source
