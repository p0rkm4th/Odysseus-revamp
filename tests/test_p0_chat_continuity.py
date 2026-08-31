"""P0 regressions: provider context is reconstructed from durable recent chat."""

from src.context_compactor import context_trace, trim_for_context
from src.aci import compatibility_intent_projection as _classify_agent_request
from src.aci import (
    deterministic_reference_acknowledgement as _deterministic_reference_acknowledgement,
    reference_resolution_hint as _recent_reference_resolution_hint,
)
from src.user_time import current_datetime_context_message


def _turns():
    return [
        {"role": "user", "content": "Please offer the available operations."},
        {"role": "assistant", "content": "I can: A. inspect the server B. scan the private network C. summarize the results."},
        {"role": "user", "content": "yes, all of the above, thanks"},
    ]


def test_recent_assistant_turn_survives_context_trim():
    messages = [
        {"role": "system", "content": "security and execution rules " * 3000},
        *_turns(),
    ]
    result = trim_for_context(messages, 8192, reserve_tokens=1024)
    contents = [m.get("content", "") for m in result]
    assert any("A. inspect the server" in text for text in contents)
    assert any("all of the above" in text for text in contents)
    roles = [m["role"] for m in result]
    assert roles[-2:] == ["assistant", "user"]


def test_clock_supplement_does_not_count_as_recent_conversation():
    messages = [
        {"role": "system", "content": "rules"},
        *_turns()[:2],
        current_datetime_context_message(),
        _turns()[-1],
    ]
    result = trim_for_context(messages, 8192)
    trace = context_trace(result, 8192)
    assert trace["user_turns"] == 2
    assert [row["role"] for row in trace["recent"]][-2:] == ["assistant", "user"]
    assert any(m.get("_context_supplement") for m in result)


def test_reference_resolution_turns_are_sent_with_roles_and_order():
    messages = [
        {"role": "system", "content": "Use the conversation to resolve references."},
        {"role": "user", "content": "Should I use the local model or strong model?"},
        {"role": "assistant", "content": "The first option is the local model."},
        {"role": "user", "content": "the first one"},
        {"role": "assistant", "content": "The next step is checking port 443."},
        {"role": "user", "content": "do that"},
    ]
    result = trim_for_context(messages, 8192)
    assert [m["role"] for m in result[-5:]] == ["user", "assistant", "user", "assistant", "user"]
    assert "local model" in result[-4]["content"]
    assert "checking port 443" in result[-2]["content"]


def test_confirmation_after_assistant_scan_prompt_keeps_network_route():
    messages = [
        {"role": "user", "content": "scan my network and tell me what you find on the 192 network"},
        {"role": "assistant", "content": "I found the private subnet. Proceed with the bounded scan?"},
        {"role": "user", "content": "yes, proceed with the scan"},
    ]
    intent = _classify_agent_request(messages, messages[-1]["content"])
    assert intent["continuation"] is True
    assert "network_ops" in set(intent["domains"])


def test_answer_to_scan_range_question_keeps_network_route():
    messages = [
        {"role": "user", "content": "scan my network and tell me what you find on the 192 network"},
        {"role": "assistant", "content": "Which private range should I scan?"},
        {"role": "user", "content": "192.168.10.0/24"},
    ]
    intent = _classify_agent_request(messages, messages[-1]["content"])
    assert intent["continuation"] is True
    assert "network_ops" in set(intent["domains"])


def test_all_of_the_above_gets_immediate_reference_hint():
    hint = _recent_reference_resolution_hint(
        _turns(), "yes, all of the above, thanks"
    )
    assert "A, B, and C" in hint
    ack = _deterministic_reference_acknowledgement(hint)
    assert "selected all three preceding options" in ack
    assert "No action is claimed complete yet" in ack


def test_reference_options_ignore_persisted_no_action_status():
    messages = [
        {"role": "user", "content": "Offer options."},
        {
            "role": "assistant",
            "content": (
                "I can: A. inspect the server B. scan the network "
                "C. summarize the results.\n\n"
                "No action completed: I did not receive a valid tool execution."
            ),
        },
        {"role": "user", "content": "yes, all of the above"},
    ]
    hint = _recent_reference_resolution_hint(messages, messages[-1]["content"])
    assert "C: summarize the results." in hint
    assert "No action completed" not in hint


def test_reference_hint_is_protected_from_local_model_context_trim():
    hint = _recent_reference_resolution_hint(
        _turns(), "yes, all of the above, thanks"
    )
    messages = [
        {"role": "system", "content": "policy " * 1800},
        {"role": "system", "content": hint, "_protected": True},
        *_turns(),
    ]
    # Match the effective local-model route budget (context budget minus the
    # response reserve), where an unprotected hint was previously discarded.
    result = trim_for_context(messages, 6963, reserve_tokens=1024)
    protected = [m for m in result if m.get("_protected")]
    assert len(protected) == 1
    assert "selects A, B, and C" in protected[0]["content"]


def test_ordinal_and_do_that_get_immediate_reference_hints():
    messages = [
        {"role": "user", "content": "Should I use local or strong?"},
        {"role": "assistant", "content": "The first option is local."},
        {"role": "user", "content": "the first one"},
        {"role": "assistant", "content": "The next step is checking port 443."},
        {"role": "user", "content": "do that"},
    ]
    assert "immediately preceding" in _recent_reference_resolution_hint(
        messages, "the first one"
    )
    assert "exact step" in _recent_reference_resolution_hint(messages, "do that")
