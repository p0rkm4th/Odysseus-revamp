from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_declares_bounded_share_target():
    manifest = (ROOT / "static/manifest.json").read_text()
    assert '"share_target"' in manifest
    assert '"action": "/"' in manifest
    assert '"method": "GET"' in manifest
    assert '"title": "title"' in manifest
    assert '"text": "text"' in manifest
    assert '"url": "url"' in manifest


def test_share_target_only_stages_bounded_content_and_never_auto_sends():
    app = (ROOT / "static/app.js").read_text()
    assert "Shared content staged for review" in app
    assert "slice(0, 8000)" in app
    assert "input.dispatchEvent(new Event('input'" in app
    assert "window.history.replaceState" in app
