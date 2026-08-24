from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.observability import ObservabilityService, metric_dimensions, sanitize_attributes
from src.work_engine import WorkEngine


def test_trace_attributes_are_redacted_bounded_and_metric_dimensions_low_cardinality():
    long_value = "x" * 500
    safe = sanitize_attributes({"run.id": "run-1", "authorization": "Bearer secret", "prompt": "private", "large": long_value, "provider": "local", "arbitrary_entity_id": "asset-1"})
    assert safe["authorization"] == "[REDACTED]"
    assert safe["prompt"] == "[REDACTED]"
    assert safe["large"]["length"] == 500
    assert "arbitrary_entity_id" not in metric_dimensions(safe)
    assert metric_dimensions({"provider": "local", "domain": "network", "run.id": "run-1"}) == {"provider": "local", "domain": "network"}


def test_trace_span_persists_owner_run_link_and_parent():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        service = ObservabilityService(db)
        run = WorkEngine(db).create_run("alice", {"domain": "network"})
        parent = service.record_span("alice", "request.receive", run_id=run["id"], trace_id="trace-1", attributes={"provider": "local"})
        child = service.record_span("alice", "model.inference", run_id=run["id"], trace_id="trace-1", parent_span_id=parent["span_id"], attributes={"api_key": "no-store"}, status="ok")
        spans = service.list_spans("alice", run_id=run["id"])
        assert [span["name"] for span in spans] == ["request.receive", "model.inference"]
        assert child["attributes"]["api_key"] == "[REDACTED]"
        assert service.list_spans("bob", run_id=run["id"]) == []
    finally:
        db.close(); engine.dispose()
