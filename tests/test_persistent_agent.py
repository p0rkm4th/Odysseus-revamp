import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from datetime import datetime, timedelta
from core.work_models import WorkCommitment, WorkRun
from src.persistent_agent import PersistentAgent, monitor_response_policy
from src.delegated_grants import DelegatedGrantService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close(); engine.dispose()


def test_persistent_agent_identity_and_grounded_context(db_session):
    agent = PersistentAgent(db_session)
    first = agent.instance("scotty")
    second = agent.instance("scotty")
    assert first.id == second.id
    assert first.installation_id == second.installation_id
    context = agent.self_context("scotty")
    assert context["identity"]["installation_id"] == first.installation_id
    assert "capabilities" in context
    assert context["work"]["pending_approval"] is False


def test_episode_and_lesson_require_evidence_link(db_session):
    agent = PersistentAgent(db_session)
    episode = agent.create_episode("scotty", title="Network discovery", summary="Observed bounded hosts", episode_type="network_discovery", source_run_id="run-1", evidence_references=["result-1"], significance=80)
    lesson = agent.propose_lesson("scotty", "The bridge listener must persist through restart.", evidence_episode_refs=[episode["id"]], domain="infrastructure")
    assert lesson["status"] == "proposed"
    assert lesson["evidence_episode_refs"] == [episode["id"]]
    assert episode["provenance"]["evidence_required"] is True


def test_monitor_notification_deduplication_and_tier_guard(db_session):
    agent = PersistentAgent(db_session)
    try:
        agent.create_monitor("scotty", {"name": "unsafe", "condition_type": "commitment_overdue", "consequence_tier": 3})
    except ValueError as exc:
        assert "tier 3" in str(exc)
    monitor = agent.create_monitor("scotty", {"name": "Overdue work", "condition_type": "commitment_overdue", "consequence_tier": 1, "cooldown_seconds": 60})
    notes = agent.evaluate_monitors("scotty")
    assert notes == []
    assert monitor["consequence_tier"] == 1


def test_monitor_response_policy_is_bounded_and_authority_preserving():
    assert [monitor_response_policy(tier) for tier in range(4)] == ["observe", "notify", "create_work", "execute_pre_authorized_action"]


def test_tier_two_monitor_creates_reviewable_run_proposal_without_execution(db_session):
    agent = PersistentAgent(db_session)
    db_session.add(WorkCommitment(id="commitment-monitor", owner="scotty", text="Review monitor", status="open", due_at=datetime.utcnow() - timedelta(hours=1)))
    db_session.commit()
    agent.create_monitor("scotty", {"name":"Review overdue work", "condition_type":"commitment_overdue", "source_domain":"work", "consequence_tier":2})
    notes = agent.evaluate_monitors("scotty")
    assert notes[0]["response_policy"] == "create_work"
    assert notes[0]["dedupe_key"].startswith("monitor:")
    assert notes[0]["proposal_run_id"]
    proposal = db_session.query(WorkRun).filter_by(owner="scotty", id=notes[0]["proposal_run_id"]).one()
    assert proposal.status == "queued" and proposal.intent["kind"] == "monitor_work_proposal"


def test_tier_three_monitor_requires_active_delegated_grant(db_session):
    agent = PersistentAgent(db_session)
    with pytest.raises(ValueError, match="active delegated grant"):
        agent.create_monitor("scotty", {"name":"unsafe", "condition_type":"commitment_overdue", "consequence_tier":3, "explicitly_allowed":True})
    work = __import__("src.work_engine", fromlist=["WorkEngine"]).WorkEngine(db_session)
    run = work.create_run("scotty", {"domain":"homelab"})
    action = work.create_action("scotty", run["id"], {"capability_id":"homelab.manage", "action_id":"execute_network_discovery", "approval_reference":"approval-watch", "normalized_input":{"scope":"private"}})
    grant = DelegatedGrantService(db_session).issue("scotty", action["id"], {"approval_reference":"approval-watch", "sealed_input_digest":action["sealed_input_digest"], "parameter_constraints":{"scope":"private"}, "expires_at":(datetime.utcnow()+timedelta(hours=1)).isoformat()})
    monitor = agent.create_monitor("scotty", {"name":"bounded watch", "condition_type":"commitment_overdue", "consequence_tier":3, "delegated_grant_id":grant["id"]})
    assert monitor["notification_policy"]["delegated_grant_id"] == grant["id"]


def test_overdue_commitment_notification_preserves_entity_reference_and_attention(db_session):
    agent = PersistentAgent(db_session)
    commitment = WorkCommitment(
        id="commitment-1", owner="scotty", text="Renew the certificate",
        status="open", due_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add(commitment); db_session.commit()
    result = agent.evaluate_commitments("scotty")
    assert result["notifications"][0]["source_entity_id"] == "commitment-1"
    attention = agent.attention("scotty")
    assert attention["count"] == 1
    assert attention["items"][0]["source_entity_id"] == "commitment-1"


def test_operating_brief_is_deterministic_and_grounded_in_existing_records(db_session):
    brief = PersistentAgent(db_session).operating_brief("scotty")
    assert brief["period"] == "day"
    assert brief["horizon_hours"] == 48
    assert brief["grounding"]["model_generated"] is False
    assert brief["grounding"]["action_claims"] is False
    assert "work_engine" in brief["grounding"]["canonical_sources"]
    assert "counts_by_status" in brief["capabilities"]


def test_operating_brief_weekly_projection_has_bounded_horizon(db_session):
    brief = PersistentAgent(db_session).operating_brief("scotty", period="week")
    assert brief["period"] == "week"
    assert brief["horizon_hours"] == 168
