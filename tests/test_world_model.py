import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.world_model import WorldModelService
from src.work_engine import WorkError


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try: yield session
    finally: session.close(); engine.dispose()


def test_world_relationships_are_owner_scoped_and_evidence_backed(db):
    svc = WorldModelService(db)
    row = svc.create_relationship("alice", {"source_ref": "service:postgres", "relation": "RUNS_ON", "target_ref": "host:cerberus", "status": "observed", "confidence_class": "high", "observation_kind": "observed", "source": "homelab-probe"})
    assert row["relation"] == "RUNS_ON"
    assert len(svc.list_relationships("alice", entity_ref="host:cerberus")) == 1
    assert svc.list_relationships("bob") == []


def test_world_neighbors_and_blast_radius_do_not_promote_inferences(db):
    svc = WorldModelService(db)
    svc.create_relationship("alice", {"source_ref": "service:postgres", "relation": "RUNS_ON", "target_ref": "host:cerberus", "status": "observed", "confidence_class": "high", "source": "probe"})
    svc.create_relationship("alice", {"source_ref": "app:jellyfin", "relation": "DEPENDS_ON", "target_ref": "service:postgres", "status": "proposed", "confidence_class": "medium", "source": "model-proposal"})
    graph = svc.neighbors("alice", "host:cerberus", depth=2)
    assert "app:jellyfin" in graph["entities"]
    radius = svc.blast_radius("alice", "host:cerberus")
    assert any(item["entity"] == "service:postgres" for item in radius["confirmed"])
    assert any(item["entity"] == "app:jellyfin" for item in radius["likely"])


def test_confirmed_relationship_requires_provenance(db):
    with pytest.raises(WorkError, match="provenance"):
        WorldModelService(db).create_relationship("alice", {"source_ref": "a", "relation": "USES", "target_ref": "b", "status": "user_confirmed"})


def test_relationship_reconciliation_is_owner_scoped_and_evented(db):
    svc = WorldModelService(db)
    row = svc.create_relationship("alice", {"source_ref": "service:x", "relation": "RUNS_ON", "target_ref": "host:y", "status": "proposed", "source": "model", "evidence_references": ["run://1"]})
    updated = svc.update_relationship("alice", row["id"], {"status": "user_confirmed", "source": "owner", "confidence_class": "confirmed", "observation_kind": "user_confirmed", "evidence_references": ["owner://confirmation"]})
    assert updated["status"] == "user_confirmed"
    assert updated["evidence_references"] == ["owner://confirmation"]
    with pytest.raises(WorkError, match="relationship not found"):
        svc.update_relationship("bob", row["id"], {"status": "stale"})
    assert db.query(__import__("core.work_models", fromlist=["WorkEvent"]).WorkEvent).filter_by(owner="alice", event_type="world.relationship.updated").count() == 1


def test_blast_radius_excludes_stale_edges_and_reports_unknown_gap(db):
    svc = WorldModelService(db)
    current = datetime.now(timezone.utc).replace(tzinfo=None)
    svc.create_relationship("alice", {"source_ref": "service:old", "relation": "RUNS_ON", "target_ref": "host:cerberus", "status": "observed", "confidence_class": "high", "source": "old-probe", "valid_until": (current - timedelta(days=1)).isoformat()})
    radius = svc.blast_radius("alice", "host:cerberus")
    assert not any(item["entity"] == "service:old" for item in radius["confirmed"] + radius["likely"])
    assert any(item["entity"] == "service:old" and item["status"] == "observed" for item in radius["unknown"])


def test_neighbors_do_not_traverse_future_relationship(db):
    svc = WorldModelService(db)
    current = datetime.now(timezone.utc).replace(tzinfo=None)
    svc.create_relationship("alice", {"source_ref": "service:future", "relation": "RUNS_ON", "target_ref": "host:cerberus", "status": "observed", "confidence_class": "high", "source": "scheduled", "valid_from": (current + timedelta(days=1)).isoformat()})
    graph = svc.neighbors("alice", "host:cerberus")
    assert "service:future" not in graph["entities"]


def test_cmdb_sync_projects_edges_idempotently_and_preserves_ended_state(db):
    svc = WorldModelService(db)
    edges = [
        {"parent_asset_id": "host-1", "child_asset_id": "service-1", "relation": "runs_on", "started_at": "2025-01-01T00:00:00"},
        {"parent_asset_id": "host-1", "child_asset_id": "old-service", "relation": "contains", "ended_at": "2025-02-01T00:00:00"},
        {"parent_asset_id": "", "child_asset_id": "missing", "relation": "runs_on"},
    ]
    first = svc.sync_cmdb_edges("alice", edges)
    second = svc.sync_cmdb_edges("alice", edges)
    assert first["relationship_count"] == 2
    assert second["relationship_count"] == 2
    assert len(svc.list_relationships("alice")) == 2
    assert {row["status"] for row in svc.list_relationships("alice")} == {"observed", "stale"}
    assert svc.list_relationships("bob") == []
