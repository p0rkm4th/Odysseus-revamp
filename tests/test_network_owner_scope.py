"""Owner isolation and legacy fail-closed coverage for the standalone CMDB."""

import json
import sqlite3

from src import asset_inventory
from src.network_projection import map_projection


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
