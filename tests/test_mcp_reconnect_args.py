"""Verify that MCP reconnect via the agent tool passes full server metadata."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace


@pytest.mark.parametrize("raw", ["{", '"--flag"', "{}", "1", "true", "null", '[1]'])
def test_mcp_args_reject_invalid_json_or_non_string_array(raw):
    from routes.mcp.mcp_routes import _parse_mcp_args
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        _parse_mcp_args(raw)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize("raw", [None, "", "   ", "[]"])
def test_mcp_args_only_empty_input_normalizes_to_empty_array(raw):
    from routes.mcp.mcp_routes import _parse_mcp_args

    assert _parse_mcp_args(raw) == []


def test_mcp_args_preserve_valid_string_array():
    from routes.mcp.mcp_routes import _parse_mcp_args

    assert _parse_mcp_args('["--flag", "value"]') == ["--flag", "value"]


def test_reconnect_passes_full_server_config():
    """do_manage_mcp reconnect must pass name/transport/command/args/env/url."""
    from src.agent_tools.admin_tools import do_manage_mcp

    fake_mcp = MagicMock()
    fake_mcp.disconnect_server = AsyncMock()
    fake_mcp.connect_server = AsyncMock(return_value=True)
    fake_mcp.get_server_status = MagicMock(return_value={"tool_count": 3})

    fake_srv = SimpleNamespace(
        id="srv-123",
        name="test-server",
        transport="stdio",
        command="/usr/bin/test",
        args=json.dumps(["--flag"]),
        env=json.dumps({"KEY": "val"}),
        url=None,
    )

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = fake_srv

    with patch("src.agent_tools.admin_tools.get_mcp_manager", return_value=fake_mcp), \
         patch("core.database.SessionLocal", return_value=fake_db):
        result = asyncio.run(do_manage_mcp(
            json.dumps({"action": "reconnect", "server_id": "srv-123"})
        ))

    assert result["exit_code"] == 0
    fake_mcp.connect_server.assert_called_once_with(
        server_id="srv-123",
        name="test-server",
        transport="stdio",
        command="/usr/bin/test",
        args=["--flag"],
        env={"KEY": "val"},
        url=None,
    )
