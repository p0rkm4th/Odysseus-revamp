from src.local_intelligence import route_request
from src.developer_mode import _DENY, WORKSPACE
from src.execution_profiles import resolve_execution_profile

def test_local_route_is_explicit_for_safe_read_domains():
    result=route_request("How much rice do I have?", requested_profile="hades-local-test")
    assert result["model_profile"] == "hades-local-test"
    assert result["domains"] == ["household_inventory"]

def test_security_and_mutation_do_not_route_local():
    result=route_request("execute a security scan")
    assert result["model_profile"] == "strong-default"
    assert result["consequential_execution"] is True

def test_workspace_yolo_is_explicit_profile_and_denies_escape():
    assert resolve_execution_profile("workspace_yolo").requires_workspace
    assert WORKSPACE.startswith("/home/")
    assert _DENY.search("docker ps")
    assert _DENY.search("sudo id")

def test_network_projection_rule_is_not_ip_identity():
    from src.network_projection import map_projection
    assert "IP addresses remain observations" in map_projection().get("identity_rule", "")
