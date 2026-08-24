import asyncio
from pathlib import Path

import routes.intelligence_routes as intelligence_routes


ROOT = Path(__file__).resolve().parents[1]


def test_smart_home_projection_uses_generic_read_boundary_and_no_mutations(monkeypatch):
    calls = []

    monkeypatch.setattr(
        intelligence_routes,
        "load_integrations",
        lambda: [{"id": "ha-1", "preset": "homeassistant", "enabled": True, "api_key": "SECRET"}],
    )

    async def fake_call(integration_id, method, path):
        calls.append((integration_id, method, path))
        if path == "/api/":
            return {"exit_code": 0, "output": "HTTP 200\n{}"}
        return {
            "exit_code": 0,
            "output": 'HTTP 200\n[{"entity_id":"light.office","state":"on"},{"entity_id":"sensor.temp","state":"21"}]',
        }

    monkeypatch.setattr(intelligence_routes, "execute_api_call", fake_call)
    result = asyncio.run(intelligence_routes._home_assistant_overview())

    assert result["status"] == "healthy"
    assert result["entities"] == 2
    assert result["domains"] == {"light": 1, "sensor": 1}
    assert result["authority_unchanged"] is True
    assert result["mutation_available"] is False
    assert calls == [("ha-1", "GET", "/api/"), ("ha-1", "GET", "/api/states")]
    assert "SECRET" not in str(result)


def test_smart_home_projection_has_safe_unconfigured_and_failure_states(monkeypatch):
    monkeypatch.setattr(intelligence_routes, "load_integrations", lambda: [])
    unconfigured = asyncio.run(intelligence_routes._home_assistant_overview())
    assert unconfigured["status"] == "unconfigured"
    assert unconfigured["configured"] is False

    monkeypatch.setattr(
        intelligence_routes,
        "load_integrations",
        lambda: [{"id": "ha-1", "preset": "homeassistant", "enabled": True}],
    )

    async def failed_call(*_args):
        return {"exit_code": 1, "error": "secret-bearing remote error"}

    monkeypatch.setattr(intelligence_routes, "execute_api_call", failed_call)
    failed = asyncio.run(intelligence_routes._home_assistant_overview())
    assert failed["status"] == "degraded"
    assert failed["error_class"] == "health_check_failed"
    assert "secret-bearing" not in str(failed)


def test_smart_home_is_visible_and_uses_the_read_only_projection():
    index = (ROOT / "static/index.html").read_text()
    app = (ROOT / "static/app.js").read_text()
    intelligence = (ROOT / "static/js/intelligence.js").read_text()
    routes = (ROOT / "routes/intelligence_routes.py").read_text()
    assert 'id="tool-smart-home-btn"' in index
    assert "openSmartHome" in app
    assert "export async function openSmartHome" in intelligence
    assert "'/api/home-assistant/overview'" in intelligence
    assert "read-only projection" in intelligence
    assert "@router.get(\"/api/home-assistant/overview\")" in routes
    assert '"mutation_available": False' in routes
