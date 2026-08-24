from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_service_worker_precaches_current_product_workspaces_and_bumps_cache():
    sw = (ROOT / "static/sw.js").read_text()
    assert "odysseus-v381-product-workspaces" in sw
    for path in (
        "/static/js/ui-components.js",
        "/static/js/workspaceWindowManager.js",
        "/static/js/intelligence.js",
        "/static/js/osint.js",
        "/static/js/security.js?v=20260823security1",
        "/static/js/worldModel.js",
        "/static/js/controlCenter.js",
        "/static/js/persistentAgent.js",
    ):
        assert path in sw


def test_manifest_remains_installable_without_external_cdn_dependencies():
    manifest = (ROOT / "static/manifest.json").read_text()
    assert '"display": "standalone"' in manifest
    assert '"start_url": "/"' in manifest
    assert "https://" not in manifest
