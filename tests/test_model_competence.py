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


def test_recommendation_requires_qualified_evidence_and_is_owner_scoped(db):
    evaluations=EvaluationService(db)
    scenario=evaluations.create_scenario("alice", {"scenario_key":"route-1","title":"Route","domain":"homelab","task_class":"homelab_diagnostics"})
    for passed in (True, True, True):
        evaluations.record_run("alice", scenario["id"], {"model":{"name":"qwen3:8b"},"passed":passed,"failure_category":"none"})
    ModelCompetenceService(db).recompute("alice")
    result=ModelCompetenceService(db).recommend("alice", task_class="homelab_diagnostics", candidates=[{"model_key":"strong-default","profile":"strong-default"},{"model_key":"hades-local-test","profile":"hades-local-test","model":"qwen3:8b"}])
    assert result["selected"]["profile"] == "hades-local-test"
    assert result["evidence_backed"] is True
    assert result["authority_unchanged"] is True
    assert result["evidence_summary"]["selected_sample_count"] == 3
    assert result["evidence_summary"]["selected_evidence_refs"]
    assert ModelCompetenceService(db).recommend("bob", task_class="homelab_diagnostics", candidates=[{"model_key":"hades-local-test"}])["selected"]["competence"]["qualification"] == "unknown"


def test_recommendation_does_not_call_unknown_model_qualified(db):
    result=ModelCompetenceService(db).recommend("alice", task_class="security_action", candidates=[{"model_key":"qwen","profile":"hades-local-test"}], require_qualified=True)
    assert result["selected"] is None
    assert result["reason_codes"] == ["no_qualified_candidate"]


def test_local_route_exposes_task_class_without_changing_authority():
    from src.local_intelligence import route_request
    result=route_request("how is my homelab service doing?", requested_profile="hades-local-test")
    assert result["task_class"] == "network_read"
    assert result["consequential_execution"] is False
