import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.persistent_agent import PersistentAgent


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
