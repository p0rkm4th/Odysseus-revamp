from src.cmdb_inventory_adapter import identity_match, inventory_proposal, strong_identity


def test_ip_alone_never_matches_identity():
    left = {"ip": "192.168.1.20", "hostname": "old-name"}
    right = {"ip": "192.168.1.20", "hostname": "new-name"}
    assert strong_identity(left) == {}
    assert not identity_match(left, right)


def test_shared_strong_identifier_matches_but_ip_does_not_participate():
    assert identity_match({"serial": "S-1", "ip": "10.0.0.2"}, {"serial": "S-1", "ip": "10.0.0.9"})
    assert not identity_match({"mac": "AA:BB", "ip": "10.0.0.2"}, {"mac": "CC:DD", "ip": "10.0.0.2"})


def test_network_observation_becomes_pending_owner_bound_proposal():
    proposal = inventory_proposal(
        owner="alice",
        cmdb_asset_id="cmdb-1",
        observation={"hostname": "switch-1", "serial": "SN1", "ip": "192.168.1.4"},
    )
    assert proposal["status"] == "pending"
    assert proposal["requires_confirmation"] is True
    assert proposal["source_type"] == "network_discovery"
    assert proposal["identity"] == {"serial": "SN1"}
    assert proposal["payload"]["item"]["cmdb_asset_id"] == "cmdb-1"
    assert proposal["idempotency_key"].startswith("cmdb:cmdb-1:")
