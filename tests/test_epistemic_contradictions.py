from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.work_engine import WorkEngine


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try: yield session
    finally: session.close(); engine.dispose()


def test_contradicting_claims_remain_linked_and_unresolved(db):
    svc = WorkEngine(db)
    first = svc.record_claim("alice", {"claim_class": "Observation", "subject_ref": "host:x", "predicate": "hostname", "value": "server", "source": "old-probe"})
    second = svc.record_claim("alice", {"claim_class": "UserAssertion", "subject_ref": "host:x", "predicate": "hostname", "value": "cerberus", "source": "owner"})
    updated = svc.record_contradiction("alice", first["id"], second["id"])
    assert second["id"] in updated["contradicting_references"]
    assert svc.list_claims("alice", subject_ref="host:x", include_inactive=False)


def test_stale_provenance_is_not_current_knowledge(db):
    svc = WorkEngine(db)
    run = svc.create_run("alice", {})
    claim = svc.record_claim("alice", {"claim_class": "Observation", "subject_ref": "service:x", "predicate": "status", "value": "active", "source": "probe"})
    svc.invalidate_state("alice", run["id"], [{"subject_ref": "service:x", "predicate": "status"}])
    context = svc.epistemic_context("alice", subject_ref="service:x")
    assert not context["current"] and context["stale"][0]["id"] == claim["id"]
