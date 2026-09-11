from src import developer_mode
from tests.helpers.sqlite_db import make_temp_sqlite
from core import database as cdb
from core import local_intelligence_models  # noqa: F401


def test_latest_active_yolo_lease_is_owner_scoped_and_supports_ui_refresh(tmp_path, monkeypatch):
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    workspace = str(tmp_path)
    monkeypatch.setattr(developer_mode, "WORKSPACE", workspace)
    with session_factory() as db:
        first = developer_mode.grant(db, "alice", workspace=workspace, duration_seconds=180)
        second = developer_mode.grant(
            db, "alice", workspace=workspace, duration_seconds=180,
            network_policy="sandboxed_network",
        )
        assert developer_mode.latest_active(db, "bob") is None
        latest = developer_mode.latest_active(db, "alice")
        assert latest.id == second["id"]
        assert latest.network_policy == "sandboxed_network"
        assert developer_mode.active(db, "bob", first["id"]) is None


def test_latest_active_lease_disappears_after_revoke(tmp_path, monkeypatch):
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(developer_mode, "WORKSPACE", str(tmp_path))
    with session_factory() as db:
        lease = developer_mode.grant(db, "alice", workspace=str(tmp_path), duration_seconds=180)
        assert developer_mode.revoke(db, "alice", lease["id"]) is True
        assert developer_mode.latest_active(db, "alice") is None


def test_workspace_yolo_does_not_inherit_service_secrets(tmp_path, monkeypatch):
    session_factory, _engine, _tmp = make_temp_sqlite(cdb.Base.metadata)
    workspace = str(tmp_path)
    monkeypatch.setattr(developer_mode, "WORKSPACE", workspace)
    monkeypatch.setenv("HADES_SYNTHETIC_YOLO_SECRET", "must-not-cross-boundary")
    with session_factory() as db:
        lease = developer_mode.grant(db, "alice", workspace=workspace, duration_seconds=180)
        result = developer_mode.execute(
            db,
            "alice",
            lease["id"],
            'printf "secret=%s\\npwd=%s\\nhome=%s\\n" "$HADES_SYNTHETIC_YOLO_SECRET" "$PWD" "$HOME"',
        )
    assert result["returncode"] == 0
    assert "must-not-cross-boundary" not in result["stdout"]
    assert "secret=\n" in result["stdout"]
    assert f"pwd={workspace}" in result["stdout"]
    assert f"home={workspace}" in result["stdout"]
