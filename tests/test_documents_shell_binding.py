from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_documents_sidebar_uses_canonical_library_button_and_visible_label():
    html = (ROOT / "static/index.html").read_text(encoding="utf-8")
    assert 'id="tool-library-btn"' in html
    assert '<span class="grow">Documents</span>' in html
    assert 'title="Documents, research, and archived library records"' in html


def test_app_binds_the_rendered_documents_button_and_legacy_alias():
    source = (ROOT / "static/app.js").read_text(encoding="utf-8")
    assert "el('tool-library-btn') || el('tool-doclib-btn')" in source
    assert "documentModule.openLibrary()" in source


def test_command_palette_can_open_documents():
    source = (ROOT / "static/js/search-chat.js").read_text(encoding="utf-8")
    assert "['Open Documents', 'tool-library-btn']" in source
