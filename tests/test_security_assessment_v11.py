import sqlite3
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from src.cmdb_security_context import CmdbSecurityContext
from src.security_assessment import SecurityAssessmentError, SecurityAssessmentService


@pytest.fixture()
def service(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    cmdb_path = tmp_path / "assets.db"
    with sqlite3.connect(cmdb_path) as db:
        db.executescript("""
        CREATE TABLE assets(id TEXT PRIMARY KEY, name TEXT, type TEXT, status TEXT, manufacturer TEXT, model TEXT, hostname TEXT, location TEXT, notes TEXT, source TEXT, confidence REAL, attributes_json TEXT, created_at TEXT, updated_at TEXT, retired_at TEXT);
        CREATE TABLE identifiers(id INTEGER PRIMARY KEY, asset_id TEXT, kind TEXT, value TEXT, confidence REAL, source TEXT, first_seen TEXT, last_seen TEXT);
        CREATE TABLE observations(id INTEGER PRIMARY KEY, asset_id TEXT, observed_at TEXT, source TEXT, kind TEXT, confidence REAL, data_json TEXT);
        CREATE TABLE relationships(id INTEGER PRIMARY KEY, parent_asset_id TEXT, child_asset_id TEXT, relation TEXT, started_at TEXT, ended_at TEXT, source TEXT, notes TEXT);
        INSERT INTO assets VALUES ('asset-1','test host','server','active','Acme','Model X','test-host','lab','','test',1.0,'{}','2026-08-23','2026-08-23',NULL);
        INSERT INTO identifiers VALUES (1,'asset-1','serial','SER-1',1.0,'test','2026-08-23','2026-08-23');
        INSERT INTO observations VALUES (1,'asset-1','2026-08-23','test','service',0.9,'{"port":443}');
        INSERT INTO assets VALUES ('asset-retired','old','server','retired',NULL,NULL,NULL,NULL,NULL,'test',1.0,'{}','2026-08-23','2026-08-23','2026-08-23');
        """)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        svc = SecurityAssessmentService(db)
        svc.cmdb = CmdbSecurityContext(cmdb_path)
        yield svc


def _authorized(service):
    engagement = service.create_engagement("alice", "alice", {"name": "CMDB V1.1"})
    scope = service.add_scope("alice", engagement["id"], {"includes": [{"kind": "asset", "value": "asset-1"}, {"kind": "asset", "value": "asset-retired"}, {"kind": "asset", "value": "does-not-exist"}], "allowed_actions": ["observation"]})
    service.authorize("alice", engagement["id"], "alice", {"reference": "ROE-V11", "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()})
    return engagement, scope


def test_canonical_context_resolves_and_retired_target_cannot_run(service):
    engagement, scope = _authorized(service)
    target = service.add_target("alice", engagement["id"], {"scope_id": scope["id"], "target_kind": "asset", "target_value": "test-host", "canonical_asset_id": "asset-1"})
    assert target["resolution_state"] == "canonical"
    assert target["canonical_context_json"]["identifiers"][0]["value"] == "SER-1"
    assert target["canonical_context_json"]["observations"][0]["data"]["port"] == 443
    retired = service.add_target("alice", engagement["id"], {"scope_id": scope["id"], "target_kind": "asset", "target_value": "old", "canonical_asset_id": "asset-retired"})
    assert retired["resolution_state"] == "retired"
    with pytest.raises(SecurityAssessmentError, match="retired"):
        service.plan_run("alice", "alice", engagement["id"], {"target_id": retired["id"], "run_class": "posture_review"})


def test_homelab_observation_is_idempotent_evidence_and_candidate_needs_confirmation(service):
    engagement, scope = _authorized(service)
    target = service.add_target("alice", engagement["id"], {"scope_id": scope["id"], "target_kind": "asset", "target_value": "test-host", "canonical_asset_id": "asset-1"})
    run = service.plan_run("alice", "alice", engagement["id"], {"target_id": target["id"], "run_class": "posture_review"})
    first = service.ingest_homelab_observation("alice", "alice", run["id"], {"idempotency_key": "obs-1", "observation": {"service": "https", "port": 443}})
    replay = service.ingest_homelab_observation("alice", "alice", run["id"], {"idempotency_key": "obs-1", "observation": {"service": "changed"}})
    assert replay["replayed"] is True and replay["id"] == first["id"]
    candidate = service.propose_finding("alice", "alice", engagement["id"], {"target_id": target["id"], "run_id": run["id"], "evidence_refs": [first["id"]], "title": "Review service", "description": "Operator review candidate.", "category": "service", "severity": "low", "source_kind": "operator"})
    assert candidate["status"] == "proposed"
    confirmed = service.confirm_candidate("alice", "alice", candidate["id"])
    assert confirmed["finding"]["status"] == "confirmed"
    assert confirmed["finding"]["scoring_basis"] == "explicit_candidate_confirmation"
    assert service.confirm_candidate("alice", "alice", candidate["id"])["replayed"] is True


def test_missing_canonical_asset_is_unresolved_and_blocks_run(service):
    engagement, scope = _authorized(service)
    target = service.add_target("alice", engagement["id"], {"scope_id": scope["id"], "target_kind": "asset", "target_value": "missing", "canonical_asset_id": "does-not-exist"})
    assert target["resolution_state"] == "unresolved"
    with pytest.raises(SecurityAssessmentError, match="unresolved"):
        service.plan_run("alice", "alice", engagement["id"], {"target_id": target["id"], "run_class": "posture_review"})
