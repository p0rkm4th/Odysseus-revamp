"""Synthetic cross-domain acceptance over canonical projections."""
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base

from core.work_models import WorkCommitment, WorkRun
from src.incident_change import IncidentChangeService
from src.mission_projection import MissionService
from src.persistent_agent import PersistentAgent
from src.setup_center import SetupCenterService
from src.work_engine import WorkEngine


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close(); engine.dispose()


def test_synthetic_control_plane_domains_share_canonical_run_and_owner_scope(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr("src.setup_center.SETUP_STATE_FILE", tmp_path / "setup.json")
    owner = "alice"
    work = WorkEngine(db_session)
    mission = MissionService(db_session).create(owner, {
        "title": "Keep the service healthy", "desired_outcome": "verified recovery",
        "success_criteria": {"health": "verified"}, "constraints": {"allowed_capabilities": ["homelab.manage"]},
    })
    run = work.create_run(owner, {"goal_id": mission["id"], "domain": "homelab", "intent": {"kind": "health_check"}})
    incident_service = IncidentChangeService(db_session)
    incident = incident_service.create_incident(owner, {"title": "Synthetic service symptom", "severity": "medium", "affected_entities": ["service:demo"]})
    change = incident_service.create_change(owner, {"objective": "Verify service recovery", "incident_id": incident["id"], "run_id": run["id"], "risk": "low"})
    incident_service.add_evidence(owner, incident["id"], {"reference": f"run://{run['id']}", "source_kind": "observed", "run_id": run["id"]})

    # Mission, Incident, and Change all project the same owner-scoped Run.
    assert MissionService(db_session).get(owner, mission["id"])["runs"][0]["id"] == run["id"]
    assert incident_service.get_incident(owner, incident["id"])["runs"][0]["id"] == run["id"]
    change_dossier = incident_service.get_change(owner, change["id"])
    assert change_dossier["run_id"] == run["id"]
    assert change_dossier["run_state"]["lifecycle_state"] == "created"

    # A Watch produces reviewable work only; it never executes the Run.
    db_session.add(WorkCommitment(id="dogfood-commitment", owner=owner, text="Review recovery", status="open", due_at=datetime.utcnow() - timedelta(hours=1)))
    db_session.commit()
    agent = PersistentAgent(db_session)
    agent.create_monitor(owner, {"name": "Recovery review", "condition_type": "commitment_overdue", "source_domain": "work", "consequence_tier": 2})
    notes = agent.evaluate_monitors(owner)
    assert notes and notes[0]["response_policy"] == "create_work"
    proposal = db_session.query(WorkRun).filter_by(id=notes[0]["proposal_run_id"], owner=owner).one()
    assert proposal.intent["kind"] == "monitor_work_proposal"
    assert proposal.id != run["id"]

    setup = SetupCenterService().projection(owner)
    assert setup["authority_unchanged"] is True
    assert setup["secrets_exposed"] is False
    assert setup["selected_profile"] is None
    assert SetupCenterService().apply_profile(owner, "SECURITY_RESEARCH")["selected_profile"] == "SECURITY_RESEARCH"
