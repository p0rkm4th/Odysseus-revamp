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


def test_control_center_is_visible_and_inspects_durable_run_state():
    index = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    module = (ROOT / "static/js/controlCenter.js").read_text()
    assert 'id="tool-control-center-btn"' in index
    assert "el('tool-control-center-btn')" in app
    assert "/api/work/runs/" in module
    assert "/preview" in module and "/validate" in module and "/traces" in module
    assert "Run Inspector" in module
    assert "/api/work/competence" in module
    assert "Competence" in module
    assert "'incidents'" in module and "'changes'" in module
    assert "controlEntityDossier" in module
    assert "Hypotheses" in module and "Preview" in module
