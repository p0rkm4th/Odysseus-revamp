import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from src.execution_nodes import ExecutionNodeService
from src.work_engine import WorkError


@pytest.fixture()
def db():
    engine=create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); session=sessionmaker(bind=engine)()
    try: yield session
    finally: session.close(); engine.dispose()


def test_execution_nodes_are_owner_scoped_and_deterministically_selected(db):
    svc=ExecutionNodeService(db)
    svc.register("alice", {"node_key":"host-broker", "display_name":"Host Broker", "trust_class":"privileged", "platform":"linux", "architecture":"x86_64", "runtimes":["python"], "capabilities":["network_discovery"], "privilege_classes":["brokered"], "network_reachability":["private_lan"], "utilization":{"cpu_percent":40}, "health":"healthy"})
    svc.register("alice", {"node_key":"gpu-node", "capabilities":["network_discovery"], "utilization":{"cpu_percent":10}, "health":"healthy"})
    result=svc.select("alice", {"capability":"network_discovery"}, limit=2)
    assert [x["node_key"] for x in result["nodes"]] == ["gpu-node", "host-broker"]
    assert result["authority_unchanged"] is True
    assert svc.list("bob") == []


def test_execution_node_requirements_fail_closed_and_heartbeat_is_durable(db):
    svc=ExecutionNodeService(db)
    svc.register("alice", {"node_key":"sandbox", "capabilities":["sandbox"], "health":"degraded"})
    assert svc.select("alice", {"sandbox":True})["eligible"] is False
    row=svc.heartbeat("alice", "sandbox", health="healthy", utilization={"cpu_percent":5})
    assert row["last_heartbeat"] and row["health"] == "healthy"
    assert svc.select("alice", {"sandbox":True})["nodes"][0]["node_key"] == "sandbox"
    with pytest.raises(WorkError, match="invalid execution node trust"):
        svc.register("alice", {"node_key":"bad", "trust_class":"root"})
