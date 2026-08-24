import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.execution_nodes import ExecutionNodeService
from src.sandbox import SandboxService
from src.work_engine import WorkEngine, WorkError


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close(); engine.dispose()


def _sandbox(db, owner="alice"):
    run = WorkEngine(db).create_run(owner, {"domain": "developer"})
    ExecutionNodeService(db).register(owner, {"node_key": "safe-node", "health": "healthy", "trust_class": "standard", "capabilities": ["sandbox"]})
    return run, SandboxService(db)


def test_sandbox_lifecycle_is_durable_bounded_and_owner_scoped(db):
    run, svc = _sandbox(db)
    row = svc.create("alice", {"run_id": run["id"], "node_key": "safe-node", "workload_type": "generated_code", "resource_limits": {"memory_mb": 512, "wall_seconds": 60}, "network_policy": {"mode": "none"}, "workspace_ref": "workspace://run-1"})
    assert row["status"] == "planned" and row["runtime_adapter"] == "not_configured"
    created = svc.transition("alice", row["id"], "creating")
    active = svc.transition("alice", row["id"], "active")
    destroyed = svc.transition("alice", row["id"], "destroyed", artifacts=["artifact://sha256:test"])
    assert created["revision"] == "2" and active["started_at"] and destroyed["ended_at"]
    assert destroyed["artifact_refs"] == ["artifact://sha256:test"]
    assert svc.list("bob") == []
    with pytest.raises(WorkError, match="sandbox not found"):
        svc.get("bob", row["id"])


def test_sandbox_rejects_privileged_or_unadvertised_nodes_and_bad_policy(db):
    run = WorkEngine(db).create_run("alice", {"domain": "developer"})
    nodes = ExecutionNodeService(db)
    nodes.register("alice", {"node_key": "privileged", "health": "healthy", "trust_class": "privileged", "capabilities": ["sandbox"]})
    with pytest.raises(WorkError, match="privileged"):
        SandboxService(db).create("alice", {"run_id": run["id"], "node_key": "privileged"})
    nodes.register("alice", {"node_key": "ordinary", "health": "healthy"})
    with pytest.raises(WorkError, match="advertise sandbox"):
        SandboxService(db).create("alice", {"run_id": run["id"], "node_key": "ordinary"})
    nodes.register("alice", {"node_key": "safe", "health": "healthy", "capabilities": ["sandbox"]})
    with pytest.raises(WorkError, match="network policy"):
        SandboxService(db).create("alice", {"run_id": run["id"], "node_key": "safe", "network_policy": {"mode": "public"}})


def test_sandbox_requires_verified_healthy_execution_node(db):
    run = WorkEngine(db).create_run("alice", {"domain": "developer"})
    ExecutionNodeService(db).register("alice", {
        "node_key": "unknown-node",
        "health": "unknown",
        "trust_class": "standard",
        "capabilities": ["sandbox"],
    })
    with pytest.raises(WorkError, match="not healthy"):
        SandboxService(db).create("alice", {"run_id": run["id"], "node_key": "unknown-node"})


def test_sandbox_lifecycle_and_artifact_exports_fail_closed(db):
    run, svc = _sandbox(db)
    row = svc.create("alice", {"run_id": run["id"], "node_key": "safe-node"})
    with pytest.raises(WorkError, match="invalid sandbox lifecycle"):
        svc.transition("alice", row["id"], "destroyed")
    svc.transition("alice", row["id"], "creating")
    svc.transition("alice", row["id"], "active")
    svc.transition("alice", row["id"], "exporting")
    with pytest.raises(WorkError, match="artifact references"):
        svc.transition("alice", row["id"], "destroyed", artifacts=[""])
    result = svc.transition("alice", row["id"], "destroyed", artifacts=["artifact://one"])
    assert result["authority_unchanged"] is True
