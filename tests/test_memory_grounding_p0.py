from pathlib import Path

from src.agent_loop import _classify_agent_request, _suppress_automatic_skills
from src.memory_grounding import minimal_saved_memory_message
from src.memory_grounding import is_explicit_memory_query
from src.context_compactor import context_trace, tool_projection_trace


def test_breakdown_wording_is_an_explicit_canonical_memory_query():
    query = "give me a concise breakdown of all the information you have about me."
    assert is_explicit_memory_query(query)
    intent = _classify_agent_request([], query)
    assert intent["explicit_memory_query"] is True
    assert intent["domains"] == {"memory"}


def test_explicit_memory_queries_suppress_procedural_skills():
    assert _suppress_automatic_skills("check your memories, are you sure?", {}) is True


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
    source = Path("src/agent_loop.py").read_text(encoding="utf-8")
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
