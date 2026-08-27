from pathlib import Path


def test_network_workspace_projects_canonical_map_without_identity_shortcuts():
    source = (Path(__file__).resolve().parents[1] / "static/js/intelligence.js").read_text()
    assert "export async function openNetwork" in source
    assert "fetch('/api/network/map'" in source
    for label in ("Nodes", "Canonical", "Unidentified", "Relationships", "Identity and provenance"):
        assert label in source
    assert "IP addresses remain observations" in source
    assert "active evidence-backed relationship" in source
    assert "pending_candidate" in source
    assert "hades-module-header" in source
    assert "hades-empty-state" in source
    assert "hades-error-state" in source


def test_network_workspace_exposes_explicit_candidate_reconciliation():
    source = (Path(__file__).resolve().parents[1] / "static/js/intelligence.js").read_text()
    assert "data-cmdb-confirm" in source
    assert "data-cmdb-reject" in source
    assert "/api/network/assets/reconcile" in source
    assert "decision === 'reject'" in source
    assert "IP addresses remain observations" in source
