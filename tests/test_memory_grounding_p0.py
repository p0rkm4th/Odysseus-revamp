from pathlib import Path

from src.intent_contracts import suppress_automatic_skills
from src.memory_grounding import minimal_saved_memory_message
from src.memory_grounding import is_explicit_memory_query
from src.context_compactor import context_trace, tool_projection_trace
from src.intent_contracts import compile_intent, resolve_intent
from src.domain_resolvers.memory import memory_mutation_payload
from src.aci import project_action_selection
from src.aci import provisional_intent_projection, canonical_memory_mutation_answer
from src.tool_execution import _resolve_memory_delete_id


def test_breakdown_wording_is_an_explicit_canonical_memory_query():
    query = "give me a concise breakdown of all the information you have about me."
    assert is_explicit_memory_query(query)
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "MEMORY"
    assert resolved.binding_name == "read_memory"


def test_explicit_memory_queries_suppress_procedural_skills():
    assert suppress_automatic_skills(
        "check your memories, are you sure?", {},
        explicit_memory_query=is_explicit_memory_query,
    ) is True


def test_qwen_compact_projection_preserves_explicit_zero_and_failure_status():
    for status in ("ZERO_RESULT", "RETRIEVAL_FAILED"):
        message = {
            "role": "user",
            "content": f"CANONICAL MEMORY RESULT\nSTATUS: {status}\nDo not invent personal facts.",
            "metadata": {"source": "saved memory: explicit canonical result", "context_kind": "explicit_memory_result"},
        }
        compact = minimal_saved_memory_message([message])
        assert compact is not None
        assert status in compact["content"]


def test_memory_domain_rule_separates_brain_from_skills():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "src/legacy_domain_contract.py",
            "src/legacy_prompt_contract.py",
            "src/agent_loop.py",
        )
    )
    assert '"memory": {"manage_memory"}' in source
    assert "Skills are not user memory" in source


def test_provider_context_trace_reports_memory_presence_without_content():
    trace = context_trace([
        {"role": "system", "content": "policy"},
        {
            "role": "user",
            "content": "CANONICAL MEMORY RESULT\nSTATUS: OK",
            "metadata": {
                "source": "saved memory: explicit canonical result",
                "context_kind": "explicit_memory_result",
                "memory_retrieved_count": 2,
            },
        },
        {"role": "user", "content": "What do you remember about me?"},
    ], 4096)
    assert trace["memory"]["provider_payload_present"] is True
    assert trace["memory"]["retrieved_count"] == 2
    assert trace["memory"]["content_logged"] is False
    assert "CANONICAL MEMORY RESULT" not in str(trace)


def test_owner_memory_mutations_resolve_to_bounded_actions_and_user_fields():
    add_query = "Remember that my test color is ultraviolet orange."
    add_frame = compile_intent(add_query)
    add_contract = resolve_intent(add_frame)
    assert (add_frame.operation_class, add_frame.domain_concept) == ("CREATE", "MEMORY")
    assert add_contract.action_id == "add"
    assert add_contract.binding_name == "manage_memory"
    assert memory_mutation_payload(add_query, "add")["text"] == "my test color is ultraviolet orange"

    delete_query = "Forget my test color."
    delete_frame = compile_intent(delete_query)
    delete_contract = resolve_intent(delete_frame)
    assert (delete_frame.operation_class, delete_frame.domain_concept) == ("DELETE", "MEMORY")
    assert delete_contract.action_id == "delete"
    projection = project_action_selection(
        intent={"intent_frame": delete_frame.as_dict(), "resolved_contract": delete_contract.as_dict()},
        relevant_tools=None, disabled_tools=set(), owner="fixture", active_run=None,
        query=delete_query,
    )
    selected = next(iter(projection.choice_map.values()))
    assert selected["payload"] == {"action": "delete", "query": "test color"}
    assert projection.fast_path == {"action": "delete", "query": "test color"}

    add_query = "Remember that my test color is ultraviolet orange."
    add_frame = compile_intent(add_query)
    add_contract = resolve_intent(add_frame)
    add_projection = project_action_selection(
        intent={"intent_frame": add_frame.as_dict(), "resolved_contract": add_contract.as_dict()},
        relevant_tools=None, disabled_tools=set(), owner="fixture", active_run=None,
        query=add_query,
    )
    assert add_projection.fast_path == {
        "action": "add",
        "text": "my test color is ultraviolet orange",
        "category": "fact",
    }


def test_owner_memory_correction_without_forget_invalidates_prior_property():
    for correction in ("Actually, that's not true anymore.", "Actually, that is not true anymore."):
        frame = compile_intent(correction, continuation=True)
        contract = resolve_intent(frame)
        assert (frame.operation_class, frame.domain_concept) == ("DELETE", "MEMORY")
        assert contract.action_id == "delete"
        assert memory_mutation_payload(
            f"{correction} What is my test color? Remember that my test color is ultraviolet orange.",
            "delete",
        ) == {"action": "delete", "query": "test color"}


def test_memory_property_followup_uses_canonical_read_after_correction():
    intent, owned = provisional_intent_projection(
        [
            {"role": "user", "content": "Remember that my test color is ultraviolet orange."},
            {"role": "assistant", "content": "Your test color is ultraviolet orange."},
            {"role": "user", "content": "Actually, that is not true anymore."},
            {"role": "assistant", "content": "That memory was removed."},
            {"role": "user", "content": "What is my test color now?"},
        ],
        "What is my test color now?",
    )
    assert owned is True
    assert intent["retrieval_query"] == "What do you remember about me?"
    assert intent["canonical_query"] == "What is my test color now?"


def test_memory_delete_resolution_ignores_recalled_context_contamination():
    entries = [{"id": "m1", "text": "my test color is ultraviolet orange"}]
    assert _resolve_memory_delete_id(
        "test color. Remember that my test color is ultraviolet orange",
        entries,
    ) == "m1"


def test_memory_delete_resolution_fails_closed_for_ambiguous_clauses():
    entries = [
        {"id": "m1", "text": "my test color is ultraviolet orange"},
        {"id": "m2", "text": "my test color is infrared blue"},
    ]
    assert _resolve_memory_delete_id("test color", entries) == ""


def test_verified_memory_mutation_has_one_human_answer():
    assert canonical_memory_mutation_answer([
        {
            "tool": "manage_memory",
            "command": '{"action":"delete","memory_id":"m1"}',
            "output": '{"success":true,"verification":{"status":"VERIFIED"}}',
            "result_projection": {"success": True, "action": "delete", "verification": {"status": "VERIFIED"}},
            "exit_code": 0,
        },
    ]) == "Removed that memory; the canonical Memory readback is verified."


def test_tool_projection_trace_explains_route_and_policy_exclusions_without_content():
    candidate = [
        {"function": {"name": "read_memory"}},
        {"function": {"name": "manage_assets"}},
        {"function": {"name": "manage_settings"}},
    ]
    projected = [candidate[0]]
    trace = tool_projection_trace(
        candidate,
        projected,
        route_relevant_tools={"read_memory"},
        disabled_tools={"manage_assets"},
        policy_exclusions={"manage_settings"},
    )
    assert trace["candidate_action_count"] == 3
    assert trace["projected_tool_count"] == 1
    assert trace["route_filtered_count"] == 2
    assert trace["disabled_tools"] == ["manage_assets"]
    assert trace["policy_exclusions"] == ["manage_settings"]
    assert trace["schema_serialization_failures"] == 0
    assert "read_memory" not in str(trace.get("messages", ""))
