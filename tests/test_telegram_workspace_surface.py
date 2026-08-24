from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_telegram_workspace_reuses_owner_scoped_lifecycle_routes():
    intelligence = (ROOT / "static/js/intelligence.js").read_text()
    app = (ROOT / "static/app.js").read_text()
    index = (ROOT / "static/index.html").read_text()
    routes = (ROOT / "routes/telegram_routes.py").read_text()
    assert 'id="tool-telegram-btn"' in index
    assert "openTelegram" in app
    assert "export async function openTelegram" in intelligence
    assert "'/api/telegram/status'" in intelligence
    assert "'/api/telegram/pairing-codes'" in intelligence
    assert "'/api/telegram/connection'" in intelligence
    assert "Owner scope" in intelligence
    assert "def _owner(request" in routes
    assert 'router.get("/status")' in routes
    assert 'router.post("/pairing-codes"' in routes

