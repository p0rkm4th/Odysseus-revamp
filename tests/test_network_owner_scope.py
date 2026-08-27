"""Owner isolation and legacy fail-closed coverage for the standalone CMDB."""

import json
import sqlite3
import argparse
from datetime import datetime, timezone, timedelta
import pytest

from src import asset_inventory
from src.network_projection import map_projection, observation_freshness


def test_network_observation_freshness_qualifies_current_state():
    reference = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    fresh = observation_freshness(
        (reference - timedelta(minutes=5)).isoformat(), now=reference,
    )
    stale = observation_freshness(
        (reference - timedelta(minutes=16)).isoformat(), now=reference,
    )
    unknown = observation_freshness("not-a-timestamp", now=reference)
    assert fresh["state"] == "FRESH"
    assert stale["state"] == "STALE"
    assert unknown["state"] == "UNKNOWN"


def _asset_args(**overrides):
    values = {
        "id": None, "name": "asset", "type": "server", "status": "active",
        "manufacturer": None, "model": None, "serial": None, "system_uuid": None,
        "hostname": None, "mac": None, "location": None, "notes": None, "source": "test",
        "confidence": 1.0, "attributes": None, "asset": None, "query": None, "limit": 100, "relationship_id": None, "kind": "observation",
        "text": None, "json": None, "owner": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_asset_cli_owner_filter_does_not_cross_partitions(tmp_path, monkeypatch, capsys):
    path = tmp_path / "assets.db"
    monkeypatch.setattr(asset_inventory, "DB_PATH", path)
    asset_inventory.cmd_add(_asset_args(id="alice-asset", name="Alice server", owner="alice"))
    asset_inventory.cmd_add(_asset_args(id="bob-asset", name="Bob server", owner="bob"))
    capsys.readouterr()

    asset_inventory.cmd_list(_asset_args(owner="alice", limit=50))
    rows = json.loads(capsys.readouterr().out)
    assert [row["id"] for row in rows] == ["alice-asset"]
    assert rows[0]["owner"] == "alice"


def test_asset_relationship_unlink_is_owner_scoped(tmp_path, monkeypatch, capsys):
    path = tmp_path / "assets.db"
    monkeypatch.setattr(asset_inventory, "DB_PATH", path)
    asset_inventory.cmd_add(_asset_args(id="alice-host", name="Alice host", owner="alice"))
    asset_inventory.cmd_add(_asset_args(id="alice-runtime", name="Alice runtime", owner="alice"))
    capsys.readouterr()
    asset_inventory.cmd_link(_asset_args(parent="alice-host", child="alice-runtime", owner="alice", relation="runs_on", source="test", notes=None))
    relationship_id = json.loads(capsys.readouterr().out)["relationship_id"]
    with pytest.raises(SystemExit, match="relationship not found"):
        asset_inventory.cmd_unlink(_asset_args(relationship_id=relationship_id, owner="bob"))
    with asset_inventory.db() as db:
        assert db.execute("SELECT ended_at FROM relationships WHERE id=?", (relationship_id,)).fetchone()[0] is None


def test_network_projection_is_owner_scoped_and_same_mac_never_merges(tmp_path, monkeypatch):
    path = tmp_path / "assets.db"
    monkeypatch.setattr(asset_inventory, "DB_PATH", path)
    monkeypatch.setenv("ODY_ASSET_DB", str(path))

    asset_inventory.record_net({"hosts": [{"ip": "192.168.10.10", "mac": "AA:BB:CC:DD:EE:01"}]}, owner="alice")
    asset_inventory.record_net({"hosts": [{"ip": "192.168.10.20", "mac": "AA:BB:CC:DD:EE:01"}]}, owner="bob")
    asset_inventory.record_net({"hosts": [{"ip": "192.168.10.30"}]}, owner="bob")

    alice = map_projection(owner="alice")
    bob = map_projection(owner="bob")
    assert alice["status"] == "SUCCESS"
    assert alice["network_state"]["projected_observation_count"] == 1
    assert alice["network_state"]["current_state"] == "FRESH"
    alice_ips = {
        json.loads(observation["data_json"]).get("ip")
        for node in alice["nodes"]
        for observation in node["observations"]
    }
    assert alice_ips == {"192.168.10.10"}
    assert bob["status"] == "SUCCESS"
    bob_ips = {
        node["attributes"].get("ip")
        for node in bob["nodes"]
        if node["resolution_state"] == "unidentified"
    }
    assert bob_ips == {"192.168.10.20", "192.168.10.30"}
    assert all(node["resolution_state"] == "unidentified" for node in bob["nodes"])


def test_network_projection_hides_legacy_ownerless_rows(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.executescript(
            "CREATE TABLE assets(id TEXT PRIMARY KEY, name TEXT, type TEXT, status TEXT, attributes_json TEXT);"
            "CREATE TABLE observations(id INTEGER PRIMARY KEY, asset_id TEXT, observed_at TEXT, source TEXT, kind TEXT, confidence REAL, data_json TEXT);"
        )
        db.execute("INSERT INTO assets VALUES ('legacy-1','old','network_device','observed','{}')")
        db.commit()
    monkeypatch.setenv("ODY_ASSET_DB", str(path))
    result = map_projection(owner="alice")
    assert result["status"] == "UNAVAILABLE"
    assert result["error_code"] == "OWNER_SCOPE_NOT_CONFIGURED"
    assert result["nodes"] == []


def test_explicit_legacy_owner_binding_preserves_rows_for_selected_owner(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    monkeypatch.setattr(asset_inventory, "DB_PATH", path)
    monkeypatch.setenv("ODY_ASSET_DB", str(path))
    asset_inventory.db().close()
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO assets(id,name,type,status,attributes_json,created_at,updated_at) VALUES ('legacy-1','old','network_device','observed','{}','now','now')")
        db.execute("INSERT INTO observations(asset_id,observed_at,source,kind,confidence,data_json) VALUES ('legacy-1','now','test','network_host',0.5,'{\"ip\":\"192.168.10.40\"}')")
        db.commit()
    result = asset_inventory.bind_legacy_owner("alice")
    assert result["assets_bound"] == 1
    assert result["observations_bound"] == 1
    projection = map_projection(owner="alice")
    assert projection["status"] == "SUCCESS"
    assert projection["nodes"][0]["owner"] == "alice"


def test_network_projection_requires_authenticated_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("ODY_ASSET_DB", str(tmp_path / "missing.db"))
    result = map_projection()
    assert result["status"] == "UNAVAILABLE"
    assert result["error_code"] == "OWNER_REQUIRED"


def test_observed_strong_identifier_is_pending_until_owner_confirmation(tmp_path, monkeypatch):
    path = tmp_path / "assets.db"
    monkeypatch.setattr(asset_inventory, "DB_PATH", path)
    monkeypatch.setenv("ODY_ASSET_DB", str(path))
    asset_inventory.record_net({"hosts": [{"ip": "192.168.10.10", "mac": "AA:BB:CC:DD:EE:01"}]}, owner="alice")
    projection = map_projection(owner="alice")
    node = projection["nodes"][0]
    assert node["canonical"] is False
    assert node["resolution_state"] == "pending_candidate"
    assert node["requires_confirmation"] is True


def test_owner_reconciliation_promotes_candidate_without_making_ip_identity(tmp_path, monkeypatch):
    path = tmp_path / "assets.db"
    monkeypatch.setattr(asset_inventory, "DB_PATH", path)
    monkeypatch.setenv("ODY_ASSET_DB", str(path))
    asset_inventory.record_net(
        {"hosts": [{"ip": "192.168.10.10", "mac": "AA:BB:CC:DD:EE:01"}]},
        owner="alice",
    )
    candidate = map_projection(owner="alice")["nodes"][0]
    result = asset_inventory.reconcile_candidate(
        "alice", candidate["id"], "confirm", name="Morpheus"
    )
    assert result["decision"] == "confirmed"
    with asset_inventory.db() as connection:
        row = connection.execute(
            "SELECT name,status FROM assets WHERE id=? AND owner=?",
            (candidate["id"], "alice"),
        ).fetchone()
        assert tuple(row) == ("Morpheus", "active")
        assert connection.execute(
            "SELECT count(*) FROM identifiers WHERE asset_id=? AND kind='ip'",
            (candidate["id"],),
        ).fetchone()[0] == 0


def test_owner_can_create_named_asset_from_unidentified_observation(tmp_path, monkeypatch):
    path = tmp_path / "assets.db"
    monkeypatch.setattr(asset_inventory, "DB_PATH", path)
    monkeypatch.setenv("ODY_ASSET_DB", str(path))
    asset_inventory.record_net(
        {"hosts": [{"ip": "192.168.10.11"}]}, owner="alice"
    )
    result = asset_inventory.reconcile_candidate(
        "alice", "unidentified:192.168.10.11", "create", name="New box"
    )
    assert result["decision"] == "confirmed"
    projection = map_projection(owner="alice")
    node = next(item for item in projection["nodes"] if item["id"] == result["asset_id"])
    assert node["canonical"] is True
    assert node["name"] == "New box"
    assert node["identifiers"] == []


def test_owner_rejects_candidate_without_cross_owner_access(tmp_path, monkeypatch):
    path = tmp_path / "assets.db"
    monkeypatch.setattr(asset_inventory, "DB_PATH", path)
    monkeypatch.setenv("ODY_ASSET_DB", str(path))
    asset_inventory.record_net(
        {"hosts": [{"ip": "192.168.10.12", "mac": "AA:BB:CC:DD:EE:12"}]},
        owner="alice",
    )
    candidate = map_projection(owner="alice")["nodes"][0]["id"]
    import pytest
    with pytest.raises(ValueError, match="not found"):
        asset_inventory.reconcile_candidate("bob", candidate, "reject")
    result = asset_inventory.reconcile_candidate("alice", candidate, "reject")
    assert result["decision"] == "rejected"


def test_network_cmdb_uses_bounded_sqlite_writer_lock(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "assets.db"
    monkeypatch.setattr(asset_inventory, "DB_PATH", path)
    connection = asset_inventory.db()
    try:
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    finally:
        connection.close()

    asset_inventory.record_net(
        {"hosts": [{"ip": "192.168.10.41", "mac": "aa:bb:cc:dd:ee:41"}]},
        owner="alice",
    )
    with sqlite3.connect(path) as check:
        assert check.execute(
            "SELECT count(*) FROM observations WHERE owner='alice'"
        ).fetchone()[0] == 1
