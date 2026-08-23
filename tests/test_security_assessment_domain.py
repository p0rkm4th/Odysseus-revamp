from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from src.security_assessment import SecurityAssessmentError, SecurityAssessmentService


@pytest.fixture()
def service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        yield SecurityAssessmentService(db)


def _engagement(service, owner="alice"):
    return service.create_engagement(owner, owner, {"name": "Home security review"})


def test_unauthorized_run_and_scope_exclusion_are_blocked(service):
    engagement = _engagement(service)
    scope = service.add_scope("alice", engagement["id"], {
        "includes": [{"kind": "cidr", "value": "192.168.1.0/24"}],
        "exclusions": [{"kind": "ip", "value": "192.168.1.10"}],
        "allowed_actions": ["reconnaissance"],
    })
    with pytest.raises(SecurityAssessmentError, match="authorized"):
        service.plan_run("alice", "alice", engagement["id"], {"target_id": "missing", "run_class": "host_discovery"})
    target = service.add_target("alice", engagement["id"], {"scope_id": scope["id"], "target_kind": "host", "target_value": "192.168.1.20"})
    with pytest.raises(SecurityAssessmentError, match="authorized"):
        service.plan_run("alice", "alice", engagement["id"], {"target_id": target["id"], "run_class": "host_discovery"})
    service.authorize("alice", engagement["id"], "alice", {"reference": "ROE-1", "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()})
    with pytest.raises(SecurityAssessmentError, match="outside"):
        service.add_target("alice", engagement["id"], {"scope_id": scope["id"], "target_kind": "host", "target_value": "192.168.1.10"})


def test_authorized_run_evidence_finding_and_report(service):
    engagement = _engagement(service)
    scope = service.add_scope("alice", engagement["id"], {"includes": [{"kind": "asset", "value": "cmdb-1"}], "allowed_actions": ["reconnaissance"]})
    target = service.add_target("alice", engagement["id"], {"scope_id": scope["id"], "target_kind": "asset", "target_value": "host-a", "canonical_asset_id": "cmdb-1"})
    service.authorize("alice", engagement["id"], "alice", {"reference": "signed-roe", "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()})
    run = service.plan_run("alice", "alice", engagement["id"], {"target_id": target["id"], "run_class": "reconnaissance"})
    assert run["authorization_decision"] == "authorized"
    run = service.complete_run("alice", run["id"], {"result_summary": {"mode": "review_only", "observations": 1}})
    evidence = service.add_evidence("alice", "alice", engagement["id"], {"run_id": run["id"], "target_id": target["id"], "reference": "observation://one", "facts": {"service": "ssh"}, "source_trust": "system"})
    finding = service.add_finding("alice", "alice", engagement["id"], {"run_id": run["id"], "target_id": target["id"], "title": "Observed service", "description": "Operator-recorded observation.", "severity": "low", "evidence_refs": [evidence["id"]]})
    assert service.update_finding("alice", finding["id"], {"status": "confirmed"})["status"] == "confirmed"
    report = service.report("alice", "alice", engagement["id"])
    assert report["projection"]["findings"][0]["id"] == finding["id"]
    assert report["projection"]["methodology_runs"][0]["status"] == "completed"


def test_owner_isolation(service):
    engagement = _engagement(service, "alice")
    with pytest.raises(SecurityAssessmentError, match="not found"):
        service.get_engagement("bob", engagement["id"])
