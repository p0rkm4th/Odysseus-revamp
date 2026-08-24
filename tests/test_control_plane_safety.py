from src.control_plane_safety import action_fingerprint, classify_knowledge_gaps, detect_action_loop


def test_equivalent_actions_are_fingerprinted_and_loop_stops_without_new_information():
    action = {"capability_id": "homelab.manage", "action_id": "service_status", "normalized_input": {"service": "nginx"}, "target_resources": ["service:nginx"], "result_reference": "result://same"}
    assert action_fingerprint(action) == action_fingerprint(dict(action))
    result = detect_action_loop([action, dict(action)])
    assert result["stop"] is True
    assert result["reason"] == "no_information_gain"


def test_new_state_version_or_result_prevents_false_loop_stop():
    base = {"capability_id": "network", "action_id": "read", "normalized_input": {"target": "host-1"}}
    result = detect_action_loop([base | {"state_version": 1, "result_reference": "result://1"}, base | {"state_version": 2, "result_reference": "result://2"}])
    assert result["stop"] is False


def test_knowledge_gaps_distinguish_known_stale_and_unknown():
    required = [{"subject_ref": "service:nginx", "predicate": "status"}, {"subject_ref": "service:nginx", "predicate": "config_digest"}, {"subject_ref": "service:nginx", "predicate": "pid"}]
    claims = [{"subject_ref": "service:nginx", "predicate": "status", "value": "healthy", "status": "active"}, {"subject_ref": "service:nginx", "predicate": "config_digest", "value": "old", "valid_until": "2026-01-01T00:00:00", "status": "active"}]
    gaps = classify_knowledge_gaps(required, claims, at="2026-08-24T00:00:00")
    assert len(gaps["known"]) == 1
    assert len(gaps["stale"]) == 1
    assert len(gaps["unknown"]) == 1
    assert gaps["complete"] is False
