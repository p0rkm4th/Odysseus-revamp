from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_communications_projection_reuses_owner_scoped_canonical_sources():
    route = (ROOT / "routes/intelligence_routes.py").read_text()
    intelligence = (ROOT / "static/js/intelligence.js").read_text()
    app = (ROOT / "static/app.js").read_text()
    index = (ROOT / "static/index.html").read_text()
    assert '@router.get("/api/communications/overview")' in route
    assert "EmailAccount" in route and "CalendarEvent" in route and "CalendarCal" in route
    assert "from_address == value" in route
    assert '"canonical_store": "CardDAV/local contacts routes"' in route
    assert "export async function openCommunications" in intelligence
    assert "'/api/communications/overview'" in intelligence
    assert "does not copy contact records" in intelligence
    assert "openCommunications" in app
    assert 'id="tool-communications-btn"' in index
