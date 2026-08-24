import pytest
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
