from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_plaid_link_is_an_owner_surface_without_access_token_in_browser_code():
    html = (ROOT / "static/index.html").read_text(encoding="utf-8")
    js = (ROOT / "static/js/integrationCenter.js").read_text(encoding="utf-8")
    assert "https://cdn.plaid.com/link/v2/stable/link-initialize.js" in html
    assert "/api/finance/plaid/link-token" in js
    assert "/api/finance/plaid/link-exchange" in js
    assert "access_token" not in js
    assert "connectionRows" in js
    assert "Authorization has not produced a provider item yet" in js
    assert "visibleUnbackedConnections" in js
    assert "previous Plaid setup attempt" in js
    assert "state === 'RECONNECT_REQUIRED'" in js
    assert "Reconnect is a provider-authorization operation" in js


def test_dead_settings_workspace_entry_is_not_rendered_and_inventory_has_crud_surface():
    registry = (ROOT / "static/js/workspaceRegistry.js").read_text(encoding="utf-8")
    inventory = (ROOT / "static/js/inventory.js").read_text(encoding="utf-8")
    assert "['settings', 'Settings'" not in registry
    assert "Pantry & grocery" in inventory
    for marker in ("Grocery list", "data-action=\"edit-item\"", "archive-item"):
        assert marker in inventory
    assert "Grocery · To buy" in inventory
    assert "Pantry · On hand" in inventory
    assert "not counted as pantry stock" in inventory


def test_security_navigation_uses_one_semantic_icon():
    html = (ROOT / "static/index.html").read_text(encoding="utf-8")
    security_row = html.split('id="tool-security-btn"', 1)[1].split('</div>', 1)[0]
    assert security_row.count('<svg') == 1
    assert 'class="hades-nav-icon"' in security_row
