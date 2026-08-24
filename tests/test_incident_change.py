import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.incident_change import IncidentChangeService
from src.work_engine import WorkEngine, WorkError


@pytest.fixture()
def db():
    engine=create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); session=sessionmaker(bind=engine)()
    try: yield session
    finally: session.close(); engine.dispose()


def test_incident_hypothesis_history_and_owner_scope(db):
    svc=IncidentChangeService(db)
    incident=svc.create_incident("alice", {"title":"Test endpoint unavailable", "severity":"high", "affected_entities":["service:test"]})
    hypothesis=svc.add_hypothesis("alice", incident["id"], {"statement":"The test service is stopped", "confidence_class":"medium"})
    assert svc.list_hypotheses("alice", incident["id"])[0]["id"] == hypothesis["id"]
    assert svc.list_incidents("bob") == []
    assert svc.update_incident("alice", incident["id"], {"status":"resolved", "root_cause":"controlled test"})["closed_at"]


def test_change_reuses_run_preview_and_rejects_cross_owner_run(db):
    work=WorkEngine(db); run=work.create_run("alice", {"domain":"homelab", "plan":[{"capability_id":"homelab.manage", "action_id":"service_status"}]})
    svc=IncidentChangeService(db)
    change=svc.create_change("alice", {"objective":"Inspect test service", "run_id":run["id"], "risk":"low"})
    assert change["preview"]["run_id"] == run["id"]
    assert change["preview"]["validation"]["valid"] is True
    with pytest.raises(WorkError, match="run not found"):
        svc.create_change("bob", {"objective":"No access", "run_id":run["id"]})


def test_dossiers_join_canonical_hypotheses_changes_and_refs(db):
    svc=IncidentChangeService(db)
    incident=svc.create_incident("alice", {"title":"Synthetic outage", "evidence_references":["result://test-1"]})
    hypothesis=svc.add_hypothesis("alice", incident["id"], {"statement":"Dependency unavailable", "status":"rejected"})
    change=svc.create_change("alice", {"objective":"Verify dependency recovery", "incident_id":incident["id"], "preview":{"actions":["service_status"]}, "verification":{"required":True}})
    dossier=svc.get_incident("alice", incident["id"])
    assert dossier["hypotheses"][0]["id"] == hypothesis["id"]
    assert dossier["changes"][0]["id"] == change["id"]
    assert dossier["canonical_refs"]["evidence"] == ["result://test-1"]
    change_dossier=svc.get_change("alice", change["id"])
    assert change_dossier["canonical_refs"]["incident"] == f"incident://{incident['id']}"
    with pytest.raises(WorkError, match="incident not found"):
        svc.get_incident("bob", incident["id"])


def test_change_and_incident_project_verified_run_state_owner_scoped(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab", "plan": [{"capability_id": "homelab.manage", "action_id": "service_status"}]})
    svc = IncidentChangeService(db)
    incident = svc.create_incident("alice", {"title": "Synthetic service issue"})
    change = svc.create_change("alice", {"objective": "Inspect via durable Run", "incident_id": incident["id"], "run_id": run["id"]})
    dossier = svc.get_change("alice", change["id"])
    assert dossier["run_state"]["lifecycle_state"] == "created"
    incident_dossier = svc.get_incident("alice", incident["id"])
    assert incident_dossier["runs"][0]["id"] == run["id"]
    with pytest.raises(WorkError, match="change not found"):
        svc.get_change("bob", change["id"])
