from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_homelab_is_visible_and_uses_existing_authority_projections():
    index = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    intelligence = (ROOT / "static/js/intelligence.js").read_text()
    assert 'id="tool-homelab-btn"' in index
    assert "openHomelab" in app
    assert "export async function openHomelab" in intelligence
    assert "'/api/hades/self'" in intelligence
    assert "'/api/network/map'" in intelligence
    assert "homelab.manage" in intelligence
    assert "existing privileged broker" in intelligence
    assert "ActionSpec" in intelligence
    assert "hades-module-header" in intelligence
    assert "hades-error-state" in intelligence


def test_homelab_surface_keeps_discovery_bounded_and_identity_safe():
    intelligence = (ROOT / "static/js/intelligence.js").read_text()
    assert "Bounded private-network discovery" in intelligence
    assert "IP addresses remain observations" in intelligence
    assert "no IP-only merge" in intelligence
