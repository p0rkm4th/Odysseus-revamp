from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_world_model_is_visible_and_uses_canonical_projection():
    index = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    module = (ROOT / "static/js/worldModel.js").read_text()
    assert 'id="tool-world-model-btn"' in index
    assert "el('tool-world-model-btn')" in app
    assert "/api/work/world/relationships" in module
    assert "blast-radius" in module
    assert "MODEL PROPOSED" in module
