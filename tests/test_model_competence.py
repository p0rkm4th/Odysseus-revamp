import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.evaluation_service import EvaluationService
from src.model_competence import ModelCompetenceService


@pytest.fixture()
def db():
    engine=create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); session=sessionmaker(bind=engine)()
    try: yield session
    finally: session.close(); engine.dispose()


def test_competence_requires_evidence_before_qualification(db):
    evaluations=EvaluationService(db); scenario=evaluations.create_scenario("alice", {"scenario_key":"read-1","title":"Read","domain":"homelab","task_class":"canonical_read"})
    for passed in (True, True, True): evaluations.record_run("alice", scenario["id"], {"model":{"name":"qwen"},"passed":passed,"failure_category":"none"})
    rows=ModelCompetenceService(db).recompute("alice")
    assert rows[0]["sample_count"] == 3 and rows[0]["qualification"] == "qualified"
    assert ModelCompetenceService(db).list("bob") == []


def test_competence_exposes_failure_classes_and_degraded_state(db):
    evaluations=EvaluationService(db); scenario=evaluations.create_scenario("alice", {"scenario_key":"safe-1","title":"Safe","domain":"network","task_class":"network_read"})
    for passed in (False, False, True): evaluations.record_run("alice", scenario["id"], {"model":{"name":"weak"},"passed":passed,"failure_category":"tool_exposure_failure" if not passed else "none"})
    row=ModelCompetenceService(db).recompute("alice")[0]
    assert row["qualification"] == "degraded" and "tool_exposure_failure" in row["failure_classes"]
