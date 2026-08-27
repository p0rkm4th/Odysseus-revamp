from pathlib import Path


def test_it_assets_workspace_keeps_inventory_and_cmdb_sources_distinct():
    source = (Path(__file__).resolve().parents[1] / "static/js/intelligence.js").read_text()
    assert "IT Assets" in source
    assert "/api/inventory/items?domain=it" in source
    assert "fetch('/api/network/map'" in source
    assert "Two canonical sources" in source
    assert "User-entered assets remain in InventoryService" in source
    assert "unidentified observations remain non-canonical" in source
    for label in ("Inventory assets", "CMDB assets", "Pending candidates", "Unidentified", "Observed nodes"):
        assert label in source
    assert "hades-module-header" in source
    assert "hades-empty-state" in source
    assert "hades-error-state" in source


def test_it_asset_dossier_preserves_observation_provenance_and_identity_boundary():
    source = (Path(__file__).resolve().parents[1] / "static/js/intelligence.js").read_text()
    assert "Observations / provenance" in source
    assert "IP addresses remain observations" in source
    assert "openCmdbAsset" in source
