from pathlib import Path


def test_security_workspace_exposes_authorization_scope_evidence_and_report_grammar():
    source = (Path(__file__).resolve().parents[1] / "static/js/security.js").read_text()
    for label in ("Security Assessments", "Authorization", "Scope", "Targets", "Evidence", "Finding candidates", "Findings", "Report"):
        assert label in source
    assert "hades-module-header" in source
    assert "hades-summary-metrics" in source
    assert "hades-empty-state" in source
    assert "/reports" in source
    assert "Canonical report revision" in source


def test_security_report_remains_a_canonical_projection():
    source = (Path(__file__).resolve().parents[1] / "static/js/security.js").read_text()
    assert "generated from canonical scope, runs, evidence, and findings" in source
    assert "JSON.stringify(report.projection || report" in source
    assert "Authorized, bounded assessment records" in source


def test_shared_summary_metrics_have_layout_and_spacing():
    source = (Path(__file__).resolve().parents[1] / "static/style.css").read_text()
    assert ".hades-summary-metrics" in source
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in source
    assert ".hades-summary-metric" in source
    assert "gap:var(--hades-space-3)" in source
