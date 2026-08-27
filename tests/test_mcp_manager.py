import asyncio
from unittest.mock import patch

from src.mcp_manager import (
    _format_mcp_connection_error,
    load_mcp_disabled_map,
    McpManager,
)


def test_playwright_mcp_connection_error_includes_install_hint():
    msg = _format_mcp_connection_error(
        "Browser (Playwright)",
        "npx",
        ["-y", "@playwright/mcp@latest", "--headless"],
        RuntimeError("package not found"),
    )

    assert "package not found" in msg
    assert "Browser MCP could not start" in msg
    assert "npx -y @playwright/mcp@latest --version" in msg
    assert "restart Odysseus" in msg


def test_generic_mcp_connection_error_preserves_original_error():
    msg = _format_mcp_connection_error(
        "Custom MCP",
        "python",
        ["server.py"],
        RuntimeError("boom"),
    )

    assert msg == "boom"


def test_disabled_tool_projection_is_owned_by_mcp_manager(monkeypatch):
    class Server:
        def __init__(self, server_id, disabled_tools):
            self.id = server_id
            self.disabled_tools = disabled_tools

    class Query:
        def all(self):
            return [
                Server("one", '["write"]'),
                Server("bad", "{"),
                Server("empty", "[]"),
            ]

    class Session:
        def query(self, _model):
            return Query()

        def close(self):
            pass

    monkeypatch.setattr("core.database.SessionLocal", lambda: Session())
    assert load_mcp_disabled_map() == {"one": {"write"}}


def test_http_transport_routes_to_start_http_connect():
    mgr = McpManager()

    async def fake_start(server_id, name, url):
        return "ROUTED"

    with patch.object(McpManager, "_start_http_connect", side_effect=fake_start) as m:
        result = asyncio.run(mgr.connect_server("id1", "n", "http", url="https://x/mcp"))
    assert result == "ROUTED"
    m.assert_called_once()


def test_qualified_tools_for_server_is_a_discovery_projection_only():
    mgr = McpManager()
    mgr._connections = {
        "builtin_browser": {"name": "Browser"},
        "other": {"name": "Other"},
    }
    mgr._tools = {
        "builtin_browser": [
            {"name": "browser_navigate"},
            {"name": "browser_click"},
        ],
        "other": [{"name": "read"}],
    }
    assert mgr.qualified_tools_for_server("builtin_browser") == {
        "mcp__builtin_browser__browser_navigate",
        "mcp__builtin_browser__browser_click",
    }
    assert mgr.qualified_tools_for_server("other") == {"mcp__other__read"}
    assert mgr.qualified_tools_for_server("missing") == set()
