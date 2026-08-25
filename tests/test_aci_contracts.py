from src.aci import (
    ACIProfile, AgentTaskPacket, ActionCard, CompletionContract,
    ContextEnvelope, DecisionMode, ObjectiveSpec, WorkingSet,
    adaptive_shortlist, hard_filter_actions, model_burden,
    parse_decision_json, state_fingerprint,
)


def _packet(cards=(ActionCard("A", "inspect", "Inspect", "Read state"),)):
    return AgentTaskPacket(
        task_type="BOUNDED_REASONING", objective={"summary": "diagnose"},
        progress={"allowed_context": ["RESULT_DETAIL"]}, entities=(),
        current_state={}, evidence=(), knowns=(), unknowns=("cause",),
        decisions=("ACTION", "NEED_CONTEXT", "CLARIFY", "BLOCKED"),
        action_cards=cards, constraints=("owner scope",), completion={"kind": "answer"},
        output_contract="concise verified answer", state_fingerprint="fp",
    )


def test_decision_json_can_only_select_current_packet_choice():
    decision, error = parse_decision_json('{"decision":"ACTION","choice":"A","state_fingerprint":"fp"}', _packet())
    assert error is None
    assert decision.decision is DecisionMode.ACTION

    rejected, error = parse_decision_json('{"decision":"ACTION","choice":"shell","state_fingerprint":"fp"}', _packet())
    assert rejected is None
    assert error == "choice_not_in_packet"

    rejected, error = parse_decision_json('{"decision":"ACTION","choice":"A","state_fingerprint":"old"}', _packet())
    assert rejected is None and error == "stale_state_fingerprint"


def test_decision_context_is_packet_bounded():
    decision, error = parse_decision_json('{"decision":"NEED_CONTEXT","context_type":"RESULT_DETAIL","state_fingerprint":"fp"}', _packet())
    assert error is None and decision.context_type == "RESULT_DETAIL"
    decision, error = parse_decision_json('{"decision":"NEED_CONTEXT","context_type":"SECRETS","state_fingerprint":"fp"}', _packet())
    assert decision is None and error == "context_type_not_allowed"


def test_hard_filter_precedes_shortlist_and_keeps_policy_downstream():
    actions = [
        {"action_id": "wrong-domain", "domain": "email"},
        {"action_id": "unhealthy", "domain": "homelab", "required_dependencies": ["broker"]},
        {"action_id": "inspect", "domain": "homelab", "operation_class": "READ", "policy_allowed": True},
    ]
    filtered = hard_filter_actions(actions, domain="homelab", operation_class="READ", healthy_dependencies=set())
    assert [a["action_id"] for a in filtered] == ["inspect"]
    assert adaptive_shortlist(filtered, "high")[0]["action_id"] == "inspect"


def test_working_set_fingerprint_is_stable_and_changes_with_state():
    base = WorkingSet(objective={"id": "o1"}, current_state={"status": "ok"}).with_fingerprint()
    same = WorkingSet(objective={"id": "o1"}, current_state={"status": "ok"}).with_fingerprint()
    changed = WorkingSet(objective={"id": "o1"}, current_state={"status": "failed"}).with_fingerprint()
    assert base.state_fingerprint == same.state_fingerprint
    assert base.state_fingerprint != changed.state_fingerprint


def test_context_envelope_does_not_confuse_architecture_with_effective_budget():
    envelope = ContextEnvelope(architecture_max_context=131072, provider_configured_max_context=8192,
                               runtime_allocated_context=4096, aci_profile_target=2000, reserved_output_budget=512)
    assert envelope.effective_context == 2512


def test_objective_and_burden_are_machine_state_not_prose():
    objective = ObjectiveSpec("o1", "owner", "work", "Fix test", completion=CompletionContract("tests"))
    assert objective.completion.kind == "tests"
    metrics = model_burden(framework=7, model=2, labels={"reference": "FRAMEWORK"})
    assert metrics["model_ratio"] == 0.2222
    assert state_fingerprint({"x": 1}) == state_fingerprint({"x": 1})
