from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_osint_is_primary_navigation_and_has_investigation_workspace():
    index = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    osint = (ROOT / "static/js/osint.js").read_text()
    assert 'id="tool-osint-btn"' in index
    assert "openOsint" in app
    for section in ("Overview", "New Investigation", "Cases", "Targets", "Research", "Sources", "Facts", "Inferences", "Relationships", "Timeline", "Evidence", "Reports"):
        assert section in osint
    assert "api('/api/research/start'" in osint
    assert "category:'osint'" in osint
    assert "caseDossier" in osint
    assert "/api/research/detail/" in osint
    assert "Sources" in osint and "Findings / Evidence" in osint
    assert "Facts / Inferences" in osint
    assert "sourceCount" in osint
    assert "not promoted into claims" in osint
    assert "External research remains tainted content" in osint
    assert "/api/research/${encodeURIComponent(sessionId)}/claims" in osint
    assert "canonical_claim_count" in osint
    assert "No reviewed canonical claims are attached" in osint


def test_osint_claim_projection_reuses_owner_scoped_work_ledger():
    routes = (ROOT / "routes/research/research_routes.py").read_text()
    assert "osint:case:" in routes
    assert "WorkEngine(db).list_claims" in routes
    assert "WorkEngine(db).record_claim" in routes
    assert "claim_lineage" in routes
    assert "record_research_claim_contradiction" in routes
    assert "review_research_claim" in routes
    assert "USER_CORRECTION" in routes or "decision" in routes
    assert "/questions" in routes
    assert "primary.subject_ref != subject or other.subject_ref != subject" in routes
    assert "_assert_owns_research(session_id, user)" in routes
    assert "deliberately not promoted" in routes


def test_osint_intake_keeps_public_source_and_review_boundaries_visible():
    osint = (ROOT / "static/js/osint.js").read_text()
    assert "public-source" in osint
    assert "MODEL PROPOSED" in osint
    assert "requires review" in osint
    assert "attachments" in osint
    assert "Correction status" in osint
    assert "data-osint-review" in osint
    assert "Prior evidence will be retained" in osint
    assert "osint-question-form" in osint


def test_shared_ui_grammar_exposes_reusable_states_headers_and_provenance():
    components = (ROOT / "static/js/ui-components.js").read_text()
    stylesheet = (ROOT / "static/style.css").read_text()
    for name in ("moduleHeader", "statusBadge", "emptyState", "loadingState", "errorState", "provenanceBadge", "intakeField"):
        assert f"function {name}" in components
    for class_name in ("hades-module-header", "hades-intake-panel", "hades-record-card", "hades-empty-state", "hades-provenance"):
        assert f".{class_name}" in stylesheet
