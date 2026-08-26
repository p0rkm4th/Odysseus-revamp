import pytest

from benchmarks.hades_aci_metamorphic import (
    DETERMINISTIC_READ_MUST_NOT,
    DETERMINISTIC_READ_TRAJECTORY,
    NEGATIVE_NEAR_MISSES,
    READ_PARAPHRASE_SETS,
)
from src.agent_loop import (
    _classify_agent_request,
    _minimal_aci_answer_messages,
    _matches_resolved_canonical_read,
    _prefetched_explicit_memory_result,
    _strip_agent_injected_messages,
)
from src.deterministic_reads import deterministic_read_concept
from src.intent_contracts import compile_intent, resolve_intent
from src.memory_grounding import is_explicit_memory_query
from src.tool_parsing import ToolBlock


@pytest.mark.parametrize("query", READ_PARAPHRASE_SETS["MEMORY"])
def test_owner_memory_paraphrases_converge_before_model_selection(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    agent_intent = _classify_agent_request([], query)
    assert is_explicit_memory_query(query)
    assert deterministic_read_concept(query) == "MEMORY"
    assert frame.domain_concept == "MEMORY"
    assert frame.operation_class == "READ"
    assert frame.read_explicit is True
    assert agent_intent["explicit_memory_query"] is True
    assert agent_intent["domains"] == {"memory"}
    assert resolved.available is True
    assert resolved.binding_name == "read_memory"
    assert resolved.action_id == "summarize_owner_memory"
    assert resolved.action.approval.value == "none"
    assert DETERMINISTIC_READ_TRAJECTORY[-3:] == ("RESULT_PROJECTION", "ANSWER", "COMPLETE")
    assert "BOUNDED_ACTION_SELECTION" in DETERMINISTIC_READ_MUST_NOT
    assert "APPROVAL" in DETERMINISTIC_READ_MUST_NOT


@pytest.mark.parametrize("query", READ_PARAPHRASE_SETS["WORK"])
def test_work_paraphrases_converge_on_owner_safe_work_reads(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.binding_name == "read_work"
    assert resolved.action.approval.value == "none"
    assert resolved.frame.operation_class == "READ"
    assert resolved.frame.read_explicit is True


@pytest.mark.parametrize("query", READ_PARAPHRASE_SETS["TECHNICAL_ASSET"])
def test_asset_paraphrases_converge_on_owner_safe_asset_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "TECHNICAL_ASSET"
    assert resolved.binding_name == "manage_assets"
    assert resolved.action_id == "list"
    assert resolved.action.approval.value == "none"
    assert resolved.frame.read_explicit is True


@pytest.mark.parametrize("query", READ_PARAPHRASE_SETS["NETWORK_CONTEXT"])
def test_current_network_paraphrases_converge_on_context_read_not_discovery(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "NETWORK"
    assert resolved.frame.filters["view"] == "context"
    assert resolved.binding_name == "manage_homelab"
    assert resolved.action_id == "read_network_context"
    assert resolved.action.approval.value == "none"
    assert resolved.frame.operation_class == "READ"


@pytest.mark.parametrize("query", [
    "Remind me what I've got going.",
    "What have I got going on?",
    "What's keeping me busy?",
    "What projects are currently in progress?",
])
def test_work_status_paraphrases_are_canonical_reads(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "WORK"
    assert resolved.action_id == "overview"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", ["Review outstanding work.", "Show my open work."])
def test_outstanding_work_review_is_the_existing_work_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "WORK"
    assert resolved.action_id == "overview"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "What's running in Odysseus?",
    "Anything unhealthy right now?",
    "What services are alive?",
])
def test_infrastructure_status_paraphrases_use_safe_service_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "SERVICE"
    assert resolved.action_id == "service_status"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "What's the difference between a VM and a container?",
    "Explain containers versus virtual machines.",
])
def test_general_container_explanations_do_not_become_host_inspection(query):
    frame = compile_intent(query)
    assert frame.domain_concept == "UNKNOWN"
    assert resolve_intent(frame).available is False


@pytest.mark.parametrize("query", [
    *NEGATIVE_NEAR_MISSES["MEMORY"],
    *NEGATIVE_NEAR_MISSES["WORK"],
    *NEGATIVE_NEAR_MISSES["TECHNICAL_ASSET"],
    *NEGATIVE_NEAR_MISSES["NETWORK"],
])
def test_negative_near_misses_do_not_become_owner_state_reads(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert not (resolved.available and frame.operation_class == "READ")


def test_answer_only_projection_has_no_tool_prompt_or_binding_identity():
    messages = [
        {"role": "system", "content": "Use manage_memory and read_memory schemas."},
        {
            "role": "user",
            "content": "CANONICAL MEMORY RESULT\nSTATUS: OK\n- REMEMBERED: owner fact",
            "_protected": True,
            "metadata": {
                "trusted": False,
                "context_kind": "explicit_memory_result",
                "memory_result_status": "ok",
            },
        },
        {"role": "user", "content": "Tell me about me."},
    ]
    assert _prefetched_explicit_memory_result(messages)
    projected = _minimal_aci_answer_messages(messages)
    serialized = "\n".join(str(message.get("content") or "") for message in projected)
    assert "manage_memory" not in serialized
    assert "read_memory" not in serialized
    assert "owner fact" in serialized
    assert projected[-1]["content"] == "Tell me about me."


def test_answer_only_projection_discards_unrelated_session_residue():
    messages = [
        {"role": "user", "content": "What do you remember about me?"},
        {"role": "assistant", "content": "Old work answer mentioning a stale project."},
        {"role": "user", "content": "What's on my plate right now?"},
        {
            "role": "tool",
            "content": '{"status":"SUCCESS_WITH_DATA","output":"current work items"}',
            "metadata": {"assistant_tool_result": True},
        },
    ]
    projected = _minimal_aci_answer_messages(messages)
    serialized = "\n".join(str(message.get("content") or "") for message in projected)
    assert "stale project" not in serialized
    assert "current work items" in serialized
    assert projected[-1]["content"] == "What's on my plate right now?"


def test_protected_aci_state_survives_provider_route_rebuild():
    packet = {
        "role": "system",
        "content": "HADES ACI MACHINE DECISION MODE",
        "_agent_injected": "hades_aci_packet",
        "_protected": True,
    }
    assert packet in _strip_agent_injected_messages([
        {"role": "system", "content": "old", "_agent_injected": "prompt"},
        packet,
        {"role": "user", "content": "request"},
    ])


@pytest.mark.parametrize(
    "query",
    (
        *READ_PARAPHRASE_SETS["MEMORY"],
        *READ_PARAPHRASE_SETS["WORK"],
        *READ_PARAPHRASE_SETS["TECHNICAL_ASSET"],
        *READ_PARAPHRASE_SETS["NETWORK_CONTEXT"],
    ),
)
def test_exact_resolved_read_result_is_answer_terminal(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert resolved.available is True
    block = ToolBlock(resolved.binding_name, '{"action":"' + resolved.action_id + '"}')
    assert _matches_resolved_canonical_read(block, frame.as_dict(), resolved.as_dict())
