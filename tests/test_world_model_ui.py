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
    assert "/api/work/missions" in module and "Missions" in module
    assert "/api/hades/monitors" in module and "Watches" in module and "consequence_tier" in module
    assert "/verification" in module or "result_summary" in module
    assert "blast_radius" in (ROOT / "src/run_planner.py").read_text()
    assert '"/execution-nodes"' in (ROOT / "routes/work_routes.py").read_text()
    assert '"/grants"' in (ROOT / "routes/work_routes.py").read_text()
    assert "/api/work/execution-nodes" in module
    assert "Execution Nodes" in module and "Delegated Grants" in module
    assert "broker authority unchanged" in module
    assert "Actions / Contracts" in module and "state_invalidations" in module
    assert "parameter_constraints" in module and "[redacted reference]" in module
    assert "/api/work/claims?include_inactive=true" in module
    assert "Evidence" in module and "contradictions" in module
    assert '"/claims"' in (ROOT / "routes/work_routes.py").read_text()
    assert "/claims/{claim_id}/lineage" in (ROOT / "routes/work_routes.py").read_text()
    assert "Evidence Explorer" in module and "data-claim-id" in module
    assert '"/world/relationships/{relationship_id}"' in (ROOT / "routes/work_routes.py").read_text()
    assert "evidence_summary" in (ROOT / "src/model_competence.py").read_text()
    assert "Linked verified Runs" in module and "Blast radius" in module and "run_state" in module
    assert '"/sandboxes"' in (ROOT / "routes/work_routes.py").read_text()
    assert '"/competence/matrix"' in (ROOT / "routes/work_routes.py").read_text()
    assert "Routing" in module and "authority unchanged" in module
    assert "supporting" in module and "contradicting" in module
    assert '"/changes/{change_id}/transition"' in (ROOT / "routes/work_routes.py").read_text()
