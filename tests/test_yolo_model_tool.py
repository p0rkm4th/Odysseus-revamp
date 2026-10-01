import json

import pytest

from src.agent_tools.developer_tools import YoloShellTool


class _Db:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_model_yolo_shell_fails_closed_without_owner_lease(monkeypatch):
    from core import database
    from src import developer_mode

    monkeypatch.setattr(database, "SessionLocal", lambda: _Db())
    monkeypatch.setattr(developer_mode, "latest_active", lambda db, owner: None)
    result = await YoloShellTool().execute(
        json.dumps({"command": "printf SHOULD_NOT_RUN"}),
        {"owner": "alice"},
    )
    assert result["requires_owner_grant"] is True
    assert result["exit_code"] == 1


@pytest.mark.asyncio
async def test_model_yolo_shell_uses_latest_owner_lease_server_side(monkeypatch):
    from core import database
    from src import developer_mode

    calls = {}
    lease = type("Lease", (), {"id": "lease-alice"})()
    monkeypatch.setattr(database, "SessionLocal", lambda: _Db())
    monkeypatch.setattr(
        developer_mode, "latest_active", lambda db, owner: calls.setdefault("lookup", (db, owner)) and lease,
    )

    def execute(db, owner, lease_id, command):
        calls["execute"] = (db, owner, lease_id, command)
        return {"returncode": 0, "stdout": "MODEL_YOLO_OK", "stderr": "", "network_policy": "sandboxed_network"}

    monkeypatch.setattr(developer_mode, "execute", execute)
    result = await YoloShellTool().execute(
        json.dumps({"command": "printf MODEL_YOLO_OK"}),
        {"owner": "alice"},
    )
    assert result["returncode"] == 0
    assert result["stdout"] == "MODEL_YOLO_OK"
    assert calls["execute"][1:] == ("alice", "lease-alice", "printf MODEL_YOLO_OK")
    assert result["model_invoked"] is True
    assert result["lease_selected_server_side"] is True

