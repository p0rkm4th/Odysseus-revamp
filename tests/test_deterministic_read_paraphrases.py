import pytest

from benchmarks.hades_aci_metamorphic import (
    DETERMINISTIC_READ_MUST_NOT,
    DETERMINISTIC_READ_TRAJECTORY,
    NEGATIVE_NEAR_MISSES,
    READ_PARAPHRASE_SETS,
)
from src.agent_loop import (
    _canonical_asset_read_payload,
    _canonical_read_fast_path_payload,
    _canonical_read_action,
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


@pytest.mark.parametrize("query", [
    "Tell me about the first physical one.",
    "Tell me about the second machine.",
])
def test_resolved_asset_reference_projects_get_instead_of_relisting(query):
    frame = compile_intent(query, reference_context={
        "ordered_entities": [
            {"ref": "PHYSICAL-001", "concept": "TECHNICAL_ASSET"},
            {"ref": "PHYSICAL-002", "concept": "TECHNICAL_ASSET"},
        ],
    })
    payload = _canonical_read_fast_path_payload(
        "manage_assets", "get", frame.as_dict(),
    )
    assert payload["action"] == "get"
    assert payload["asset"] in {"PHYSICAL-001", "PHYSICAL-002"}
    resolved = resolve_intent(frame)
    assert resolved.action_id == "get"
    assert _canonical_read_action(
        "TECHNICAL_ASSET", frame.filters,
        entity_reference=frame.entity_reference,
    ) == "get"


def test_resolved_asset_fast_path_preserves_strong_identity():
    frame = compile_intent("Tell me about the first physical one.", reference_context={
        "ordered_entities": [
            {"ref": "PHYSICAL-001", "concept": "TECHNICAL_ASSET"},
        ],
    })
    # The ACI fast path must pass the same canonical payload as the
    # asset-specific repair path; an action-only ``get`` cannot execute.
    payload = _canonical_asset_read_payload(frame.as_dict())
    assert payload == {"action": "get", "asset": "PHYSICAL-001"}


def test_ambiguous_asset_pronoun_does_not_become_lexical_target():
    frame = compile_intent("what about that one", reference_context={
        "ordered_entities": [
            {"ref": "PHYSICAL-001", "concept": "TECHNICAL_ASSET"},
            {"ref": "PHYSICAL-002", "concept": "TECHNICAL_ASSET"},
        ],
    })
    assert frame.reference_resolution["status"] == "AMBIGUOUS"
    assert frame.entity_reference is None


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
    "What is my default route?",
    "What interface is carrying traffic?",
    "What is the current network context?",
    "What subnet am I on?",
])
def test_network_context_detail_paraphrases_use_host_context_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "NETWORK"
    assert resolved.frame.filters["view"] == "context"
    assert resolved.action_id == "read_network_context"


@pytest.mark.parametrize("query", [
    "Can you inspect the host?",
    "Check this host.",
    "Show me the current host.",
])
def test_explicit_host_inspection_uses_host_read_not_network_observations(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "HOMELAB_HOST"
    assert resolved.action_id == "inspect_host"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "Remind me what I've got going.",
    "What have I got going on?",
    "What's keeping me busy?",
    "What projects are currently in progress?",
    "alright what am i working on again",
    "okay so what am i working on",
])
def test_work_status_paraphrases_are_canonical_reads(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "WORK"
    assert resolved.action_id == "overview"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "Do a deep dive on my local network.",
    "Investigate my network.",
    "Look into the current LAN.",
])
def test_unscoped_network_deep_dive_requires_explicit_authorized_scope(query):
    frame = compile_intent(query)
    assert frame.domain_concept == "NETWORK"
    assert frame.operation_class == "RESEARCH"
    assert "network_scope_requires_authorization" in frame.constraints
    assert resolve_intent(frame).available is False


def test_explicit_bounded_network_scope_keeps_normal_plan_contract():
    frame = compile_intent("Scan the network 192.168.1.0/24")
    assert frame.domain_concept == "NETWORK"
    assert frame.operation_class == "EXECUTE"
    assert "network_scope_requires_authorization" not in frame.constraints
    assert resolve_intent(frame).action_id == "plan_network_discovery"


@pytest.mark.parametrize("query", ["Where did we leave off?", "Where'd I leave off?"])
def test_work_status_continuity_question_is_a_safe_work_read(query):
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
    "Are my services alive?",
    "Is everything healthy?",
    "Anything broken?",
])
def test_infrastructure_status_paraphrases_use_safe_service_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "SERVICE"
    assert resolved.action_id == "service_status"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "whats running",
    "hows Hades doing",
    "anything dead",
    "anything down right now",
    "what the hell is busted",
    "are we good",
    "how is the stack",
])
def test_casual_infrastructure_status_paraphrases_use_safe_service_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "SERVICE"
    assert resolved.action_id == "service_status"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "tell me abotu me",
    "give me my lore",
    "what's my background",
    "what's my deal",
    "what do you actually have saved",
])
def test_messy_owner_self_knowledge_stays_on_memory_read_family(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "MEMORY"
    assert resolved.action_id == "summarize_owner_memory"
    assert resolved.action.approval.value == "none"


def test_physical_host_inventory_is_not_shadowed_by_network_host_language():
    resolved = resolve_intent(compile_intent("What physical hosts do I own?"))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "TECHNICAL_ASSET"
    assert resolved.action_id == "list"


def test_current_network_context_is_not_filtered_as_a_definition():
    resolved = resolve_intent(compile_intent("What is the current network context?"))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "NETWORK"
    assert resolved.action_id == "read_network_context"


def test_unknown_selfstate_capability_question_does_not_become_work_read():
    frame = compile_intent("What capabilities are working?")
    assert frame.domain_concept == "UNKNOWN"
    assert resolve_intent(frame).available is False


@pytest.mark.parametrize("query", ["go on", "please go on", "keep going"])
def test_natural_resume_language_is_classified_as_continuation(query):
    assert compile_intent(query).operation_class == "CONTINUE"


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
