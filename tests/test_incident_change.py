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


def test_incident_evidence_loop_updates_hypothesis_without_erasing_history(db):
    svc=IncidentChangeService(db); work=WorkEngine(db); diagnostic_run=work.create_run("alice", {"domain":"homelab"})
    incident=svc.create_incident("alice", {"title":"Evidence loop"})
    hypothesis=svc.add_hypothesis("alice", incident["id"], {"statement":"Database dependency is unavailable"})
    evidence=svc.add_evidence("alice", incident["id"], {"reference":"result://db-health-1", "source_kind":"observed", "run_id":diagnostic_run["id"]})
    updated=svc.update_hypothesis("alice", incident["id"], hypothesis["id"], {"status":"rejected", "confidence_class":"high", "supporting_evidence":[], "contradicting_evidence":[evidence["evidence_reference"]]})
    dossier=svc.get_incident("alice", incident["id"])
    assert updated["status"] == "rejected"
    assert dossier["evidence_references"] == ["result://db-health-1"]
    assert dossier["runs"][0]["id"] == diagnostic_run["id"]
    assert [event["kind"] for event in dossier["timeline"]] == ["hypothesis_added", "evidence_added", "hypothesis_updated"]
    with pytest.raises(WorkError, match="incident not found"):
        svc.update_hypothesis("bob", incident["id"], hypothesis["id"], {})


def test_incident_evidence_rejects_cross_owner_run(db):
    work=WorkEngine(db); run=work.create_run("alice", {"domain":"homelab"})
    svc=IncidentChangeService(db); incident=svc.create_incident("bob", {"title":"Isolated incident"})
    with pytest.raises(WorkError, match="evidence Run not found"):
        svc.add_evidence("bob", incident["id"], {"reference":"result://private", "run_id":run["id"]})


def test_incident_evidence_accepts_completed_canonical_action_reference(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab"})
    action = work.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "service_status"})
    completed = work.complete_action("alice", action["id"], {
        "result": {"result_type": "diagnostic", "reference": f"agent-tool://{action['id']}"},
        "result_reference": f"agent-tool://{action['id']}",
    })
    svc = IncidentChangeService(db)
    incident = svc.create_incident("alice", {"title": "Canonical evidence"})
    evidence = svc.add_evidence("alice", incident["id"], {"reference": completed["result"]["reference"], "run_id": run["id"]})
    assert evidence["evidence_reference"] == f"agent-tool://{action['id']}"
    assert evidence["timeline_event"]["run_id"] == run["id"]


def test_incident_evidence_rejects_cross_run_canonical_action_reference(db):
    work = WorkEngine(db)
    first = work.create_run("alice", {"domain": "homelab"})
    second = work.create_run("alice", {"domain": "homelab"})
    action = work.create_action("alice", first["id"], {"capability_id": "homelab.manage", "action_id": "service_status"})
    work.complete_action("alice", action["id"], {"result_reference": f"action-result://{action['id']}"})
    svc = IncidentChangeService(db)
    incident = svc.create_incident("alice", {"title": "Cross-run evidence"})
    with pytest.raises(WorkError, match="does not match canonical reference"):
        svc.add_evidence("alice", incident["id"], {"reference": f"action-result://{action['id']}", "run_id": second["id"]})


def test_incident_evidence_rejects_cross_owner_canonical_action_reference(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain": "homelab"})
    action = work.create_action("alice", run["id"], {"capability_id": "homelab.manage", "action_id": "service_status"})
    work.complete_action("alice", action["id"], {"result_reference": f"action-result://{action['id']}"})
    svc = IncidentChangeService(db)
    incident = svc.create_incident("bob", {"title": "Cross-owner evidence"})
    with pytest.raises(WorkError, match="canonical evidence reference not found"):
        svc.add_evidence("bob", incident["id"], {"reference": f"action-result://{action['id']}"})


def test_change_completion_requires_verified_canonical_run(db):
    work=WorkEngine(db); run=work.create_run("alice", {"domain":"homelab"})
    svc=IncidentChangeService(db)
    change=svc.create_change("alice", {"objective":"Verified test change", "run_id":run["id"], "status":"validated"})
    executing=svc.transition_change("alice", change["id"], "executing")
    svc.transition_change("alice", change["id"], "verifying")
    with pytest.raises(WorkError, match="verified Run"):
        svc.transition_change("alice", change["id"], "completed")
    # Advance the canonical Run through its explicit verified lifecycle.
    for state in ("planning", "ready", "executing", "verifying"):
        work.verified_execution_step("alice", run["id"], state)
    work.complete_verification("alice", run["id"], success=True, details={"postcondition":"healthy"})
    completed=svc.transition_change("alice", change["id"], "completed", outcome={"verified":True})
    assert executing["status"] == "executing" and completed["status"] == "completed"
    assert completed["run_state"]["verification"]["success"] is True


def test_change_lifecycle_revalidates_linked_run_before_validation(db):
    work = WorkEngine(db)
    run = work.create_run("alice", {"domain":"network", "plan":[{"capability_id":"homelab.manage", "action_id":"execute_network_discovery", "target_resources":["network:public"]}]})
    svc = IncidentChangeService(db)
    draft = svc.create_change("alice", {"objective":"Unsafe scope test", "run_id":run["id"]})
    with pytest.raises(WorkError, match="change requires valid Run plan.*scope_invalid"):
        svc.transition_change("alice", draft["id"], "validated")
    with pytest.raises(WorkError, match="change requires valid Run plan.*scope_invalid"):
        svc.create_change("alice", {"objective":"Unsafe immediate change", "run_id":run["id"], "status":"validated"})
