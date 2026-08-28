import pytest

from src.aci import (
    ACIProfile, AgentTaskPacket, ActionCard, CompletionContract,
    ContextEnvelope, DecisionMode, ObjectiveSpec, TurnDisposition, WorkingSet,
    PostResultState, classify_post_result, project_post_result_transition,
    resolve_turn_disposition,
    resolve_turn_intent,
    adaptive_shortlist, hard_filter_actions, model_burden,
    parse_decision_json, state_fingerprint,
    build_base_prompt,
)
from src.agent_loop import _minimal_aci_model_fallback_messages


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

    decision, error = parse_decision_json('{"decision":"CLARIFY","ambiguity_class":"target"}', _packet())
    assert error is None and decision.state_fingerprint == "fp"


def test_weak_model_action_label_with_explanation_is_safe_clarification():
    decision, error = parse_decision_json(
        '{"decision":"ACTION","choice":"ask_user","answer":"Which service?"}', _packet()
    )
    assert error is None
    assert decision.decision is DecisionMode.CLARIFY


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


def test_base_prompt_projection_is_owned_by_aci():
    rendered = []

    def render(names, **kwargs):
        rendered.append((set(names), dict(kwargs)))
        return "bounded prompt"

    prompt, skills = build_base_prompt(
        tool_sections={"read_file": "read", "manage_memory": "memory"},
        agent_system_prompt="full prompt",
        disabled_tools={"manage_memory"},
        mcp_mgr=None,
        needs_admin=False,
        relevant_tools={"read_file", "manage_memory"},
        always_available={"read_file"},
        admin_tools=set(),
        suppress_skills=True,
        assemble=render,
    )
    assert prompt == "bounded prompt"
    assert skills == ""
    assert len(rendered) == 1
    selected, options = rendered[0]
    assert selected == {"read_file", "manage_memory", "ask_user", "update_plan"}
    assert options["disabled_tools"] == {"manage_memory", "generate_image"}
    assert options["compact"] is False
    assert options["intent_domains"] is None
    metrics = model_burden(framework=7, model=2, labels={"reference": "FRAMEWORK"})
    assert metrics["model_ratio"] == 0.2222
    assert state_fingerprint({"x": 1}) == state_fingerprint({"x": 1})


def test_canonical_intent_resolution_does_not_consult_compatibility_classifier():
    calls = []

    def provisional(messages, text):
        return {"domain_concept": "NETWORK", "operation_class": "READ"}, True

    def compatibility(messages, text):
        calls.append("classifier")
        return {"domain_concept": "LEGACY"}

    def normalizer(intent, text):
        calls.append("normalizer")
        return intent

    intent, owned = resolve_turn_intent(
        [],
        "what network am i on",
        aci_enabled=True,
        provisional_resolver=provisional,
        compatibility_classifier=compatibility,
        compatibility_normalizers=(normalizer,),
    )

    assert owned is True
    assert intent["domain_concept"] == "NETWORK"
    assert calls == []


def test_unowned_intent_resolution_uses_compatibility_adapter_only_as_fallback():
    calls = []

    def provisional(messages, text):
        return None, False

    def compatibility(messages, text):
        calls.append("classifier")
        return {"domain_concept": "DOCUMENT", "retrieval_query": text}

    def normalizer(intent, text):
        calls.append("normalizer")
        intent["adapted"] = True
        return intent

    intent, owned = resolve_turn_intent(
        [],
        "find the document",
        aci_enabled=True,
        provisional_resolver=provisional,
        compatibility_classifier=compatibility,
        compatibility_normalizers=(normalizer,),
    )

    assert owned is False
    assert intent["domain_concept"] == "DOCUMENT"
    assert intent["adapted"] is True
    assert calls == ["classifier", "normalizer"]


def test_post_result_state_does_not_reenter_decision_for_sufficient_canonical_read():
    assert classify_post_result(
        {"status": "SUCCESS_WITH_DATA", "exit_code": 0}, canonical_read=True,
    ) is PostResultState.COMPLETE_AFTER_ANSWER
    assert classify_post_result(
        {"status": "SUCCESS_WITH_DATA", "exit_code": 0},
        canonical_read=True, unresolved_required_information=True,
    ) is PostResultState.NEEDS_CONTEXT
    assert classify_post_result(
        {"status": "SUCCESS", "exit_code": 0}, canonical_read=False,
    ) is PostResultState.NEEDS_BOUNDED_REASONING
    assert classify_post_result(
        {"approval_required": True}, canonical_read=True,
    ) is PostResultState.NEEDS_APPROVAL


@pytest.mark.parametrize(
    ("result", "kwargs", "expected"),
    [
        ({"exit_code": 0}, {"deterministic_next_step": True}, PostResultState.CONTINUE_DETERMINISTICALLY),
        ({"exit_code": 0}, {"unresolved_required_information": True}, PostResultState.NEEDS_CONTEXT),
        ({"exit_code": 0}, {}, PostResultState.NEEDS_BOUNDED_REASONING),
        ({"approval_required": True}, {}, PostResultState.NEEDS_APPROVAL),
        ({"error": "denied"}, {}, PostResultState.BLOCKED),
        ({"exit_code": 1}, {}, PostResultState.BLOCKED),
        (None, {}, PostResultState.BLOCKED),
    ],
)
def test_post_result_classifier_covers_canonical_lifecycle_states(result, kwargs, expected):
    assert classify_post_result(result, **kwargs) is expected


def test_post_result_transition_does_not_claim_completion_for_approval_or_reasoning():
    approval = project_post_result_transition({"approval_required": True})
    assert approval.state is PostResultState.NEEDS_APPROVAL
    assert approval.answer_only is False
    assert approval.completion_satisfied is False

    reasoning = project_post_result_transition({"exit_code": 0})
    assert reasoning.state is PostResultState.NEEDS_BOUNDED_REASONING
    assert reasoning.answer_only is False
    assert reasoning.completion_satisfied is False


def test_model_fallback_is_a_non_authoritative_turn_disposition():
    assert TurnDisposition.MODEL_FALLBACK.value == "MODEL_FALLBACK"


def test_typed_turn_disposition_has_one_authoritative_precedence():
    assert resolve_turn_disposition(model_fallback=True, packet_present=True) is TurnDisposition.MODEL_FALLBACK
    assert resolve_turn_disposition(clarification_only=True, fast_path=True) is TurnDisposition.CLARIFY
    assert resolve_turn_disposition(answer_only=True, fast_path=True) is TurnDisposition.ANSWER
    assert resolve_turn_disposition(completion_satisfied=True) is TurnDisposition.ANSWER
    assert resolve_turn_disposition(fast_path=True, packet_present=True) is TurnDisposition.EXECUTE_DIRECT
    assert resolve_turn_disposition(packet_present=True) is TurnDisposition.DECIDE
    assert resolve_turn_disposition() is None


def test_model_fallback_context_excludes_internal_execution_plumbing():
    messages = _minimal_aci_model_fallback_messages([
        {"role": "system", "content": "manage_memory ActionSpec ToolBinding"},
        {"role": "assistant", "content": "Prior answer"},
        {"role": "user", "content": "Do the thing to Cerberus."},
        {"role": "tool", "content": "secret raw result"},
    ])
    assert messages[-1] == {"role": "user", "content": "Do the thing to Cerberus."}
    assert all(message.get("role") != "tool" for message in messages)
    serialized = " ".join(str(message.get("content", "")) for message in messages)
    assert "manage_memory" not in serialized
    assert "ToolBinding" not in serialized
    assert "Execution authority: NONE" in serialized


def test_model_fallback_can_receive_sanitized_runtime_self_state_without_authority():
    messages = _minimal_aci_model_fallback_messages(
        [{"role": "user", "content": "What model are you using?"}],
        runtime_self_state={
            "active": True,
            "model": "qwen3:8b",
            "provider": "ollama",
            "active_branch": "hades-aci-v1",
            "endpoint": "http://secret.example.invalid/token",
        },
    )
    serialized = " ".join(str(message.get("content", "")) for message in messages)
    assert "qwen3:8b" in serialized
    assert "ollama" in serialized
    assert "hades-aci-v1" in serialized
    assert "secret.example.invalid" not in serialized
    assert "Execution authority: NONE" in serialized
    assert "ToolBinding" not in serialized
