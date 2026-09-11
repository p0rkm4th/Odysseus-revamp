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
    assert "validity" in module
    assert "evidence_references" in module
    assert "Bounded neighbors" in module
    assert "All relations" in module and "All statuses" in module
    assert "CONTAINS" in module
    assert "Unknown dependency gaps" in module
    assert "Activity:" in module
    assert '"/world/relationships/sync-cmdb"' in (ROOT / "routes/work_routes.py").read_text()
    assert "world-sync-cmdb" in module
    assert "Sync CMDB" in module


def test_control_center_is_visible_and_inspects_durable_run_state():
    index = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    module = (ROOT / "static/js/controlCenter.js").read_text()
    assert 'id="tool-control-center-btn"' in index
    assert "el('tool-control-center-btn')" in app
    assert "/api/work/runs/" in module
    assert "/preview" in module and "/validate" in module and "/traces" in module
    assert "Run Inspector" in module
    assert "preview.prechecks" in module
    assert "<h3>Prechecks</h3>" in module
    assert "preview.targets" in module
    assert "preview.reversibility" in module
    assert "preview.capability_health" in module
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
    assert "/actions/${encodeURIComponent(button.dataset.actionId)}/retry" in module
    assert "Retry safely" in module
    assert "control-retry-action" in module
    assert "execution_ambiguous" in module
    assert "compensation_result" in module
    assert "ambiguous_reason" in module
    app = (ROOT / "static/app.js").read_text()
    index = (ROOT / "static/index.html").read_text()
    integrations = (ROOT / "static/js/integrationCenter.js").read_text()
    assert 'id="tool-integrations-center-btn"' in index
    assert "openIntegrationCenter" in app
    assert "/api/setup-center/integrations" in integrations
    assert "secrets hidden" in integrations


def test_integration_center_normalizes_legacy_character_split_capabilities():
    integrations = (ROOT / "static/js/integrationCenter.js").read_text()
    assert "capabilityLabels" in integrations
    assert "rawLabels.every(label => label.length === 1)" in integrations
    assert "rawLabels.join('').split" in integrations


def test_recipe_missing_action_carries_canonical_recipe_id_from_library_card():
    inventory = (ROOT / "static/js/inventory.js").read_text()
    assert 'data-action="queue-missing"' in inventory
    assert 'data-recipe-id="${escapeHtml(recipe.id)}"' in inventory


def test_recipe_library_has_owner_facing_hierarchy_and_roomier_window():
    inventory = (ROOT / "static/js/inventory.js").read_text()
    manager = (ROOT / "static/js/workspaceWindowManager.js").read_text()
    styles = (ROOT / "static/style.css").read_text()
    assert "What can we cook?" in inventory
    assert "recipe-card-grid" in inventory
    assert "Ingredient check" in inventory
    assert "NEXT STEP" in inventory
    assert "Ingredients to buy" in inventory
    assert 'aria-label="${missing ? \'Missing\' : \'On hand\'}"' in inventory
    assert "recipe-detail-shortage" in inventory
    assert "kind === 'view' ? ''" in inventory
    assert "recipe-serving-count" in inventory
    assert "data-action=\"recipe-plan\"" in inventory
    assert "data-serving-count" in inventory
    assert "initialRect" in manager
    assert ".recipe-card-body" in styles
    assert ".recipe-preview { display:grid; grid-template-columns:1fr;" in styles
    assert ".recipe-detail-check .recipe-ingredient-list" in styles
    assert ".recipe-serving-control" in styles
    assert ".recipe-stat-ready" in styles


def test_household_sharing_uses_explicit_status_and_action_regions():
    inventory = (ROOT / "static/js/inventory.js").read_text()
    styles = (ROOT / "static/style.css").read_text()
    assert "inventory-sharing-state" in inventory
    assert "inventory-sharing-actions" in inventory
    assert "Make members read-only" in inventory
    assert ".inventory-sharing-row" in styles
