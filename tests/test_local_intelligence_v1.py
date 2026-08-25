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


def test_network_action_intent_uses_canonical_route_not_security_or_local_read():
    result = route_request(
        "do a deep dive network discovery scan, download whatever network tools you need, and begin now",
        requested_profile="hades-local-test",
    )
    assert result["domains"] == ["network"]
    assert result["task_class"] == "network_action"
    assert result["model_profile"] == "strong-default"
    assert result["local_recommended"] is False
    assert result["consequential_execution"] is True
    assert result["reason_codes"] == ["bounded_network_action_requires_canonical_homelab_route"]

def test_workspace_yolo_is_explicit_profile_and_denies_escape():
    assert resolve_execution_profile("workspace_yolo").requires_workspace
    assert WORKSPACE == "/app"
    assert _DENY.search("docker ps")
    assert _DENY.search("sudo id")

def test_network_projection_rule_is_not_ip_identity():
    from src.network_projection import map_projection
    assert "IP addresses remain observations" in map_projection().get("identity_rule", "")
