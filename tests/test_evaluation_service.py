import pytest
from benchmarks.jarvis.core import load_json, validate_suite
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.evaluation_service import EvaluationError, EvaluationService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close(); engine.dispose()


def test_scenario_run_and_failure_review_are_owner_scoped(db):
    service = EvaluationService(db)
    scenario = service.create_scenario("alice", {
        "scenario_key": "network.discovery.grounded", "domain": "network",
        "task_class": "bounded_discovery", "title": "Grounded private discovery",
        "user_intent": "scan the private network", "expected": {"required_action": "execute_network_discovery"},
        "forbidden": {"public_scan": True},
    })
    run = service.record_run("alice", scenario["id"], {
        "model": {"provider": "local", "name": "qwen3:8b"},
        "trajectory": {"actions": ["plan", "execute", "verify"]},
        "score": {"grounding": 1.0, "verification": 1.0}, "passed": True,
    })
    failure = service.record_failure("alice", {
        "evaluation_run_id": run["id"], "title": "Missing discovery action",
        "taxonomy": "tool_exposure_failure", "impact": "high",
        "sanitized_context": {"roles": ["system", "user", "assistant"]},
        "expected_behavior": {"action": "execute_network_discovery"},
        "actual_behavior": {"action": None},
    })
    assert service.review_failure("alice", failure["id"], decision="admitted", reviewed_by="owner")["status"] == "admitted"
    assert service.list_failures("bob") == []
    with pytest.raises(EvaluationError, match="taxonomy"):
        service.record_failure("alice", {"title": "bad", "taxonomy": "made_up"})


def test_duplicate_scenario_keys_are_rejected(db):
    service = EvaluationService(db)
    payload = {"scenario_key": "same", "domain": "chat", "task_class": "continuity", "title": "Same"}
    service.create_scenario("alice", payload)
    with pytest.raises(EvaluationError, match="already exists"):
        service.create_scenario("alice", payload)


def test_control_plane_regression_corpus_is_valid_and_covers_known_failures():
    suite = validate_suite(load_json("benchmarks/jarvis/control_plane_v1.json"))
    ids = {case["id"] for case in suite["cases"]}
    assert len(ids) == 15
    assert {"tool-exposure-network", "approval-digest-mutation", "duplicate-read-loop"} <= ids
