import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.mission_projection import MissionService
from src.work_engine import WorkEngine, WorkError


@pytest.fixture()
def db():
    engine=create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); session=sessionmaker(bind=engine)()
    try: yield session
    finally: session.close(); engine.dispose()


def test_mission_reuses_goal_and_projects_linked_runs(db):
    svc=MissionService(db)
    mission=svc.create("alice", {"title":"Keep test service healthy", "desired_outcome":"Healthy endpoint", "success_criteria":{"checks":2}, "deadline":"2030-01-01T00:00:00"})
    run=WorkEngine(db).create_run("alice", {"goal_id":mission["id"], "domain":"homelab"})
    current=svc.get("alice", mission["id"])
    assert current["lifecycle"] == "DRAFT" and current["objective"] == "Healthy endpoint"
    assert current["runs"][0]["id"] == run["id"] and current["canonical_ref"] == f"goal://{mission['id']}"
    assert svc.list("bob") == []


def test_non_mission_goal_is_not_reachable_as_mission(db):
    goal=WorkEngine(db).create_goal("alice", {"title":"Ordinary goal"})
    assert MissionService(db).list("alice") == []
    with pytest.raises(WorkError, match="mission not found"):
        MissionService(db).get("alice", goal["id"])
