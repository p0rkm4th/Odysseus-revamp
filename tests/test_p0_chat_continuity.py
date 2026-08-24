"""P0 regressions: provider context is reconstructed from durable recent chat."""

from src.context_compactor import context_trace, trim_for_context
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
