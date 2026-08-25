"""Focused regression checks for the recovered Odysseus upgrade."""

import json

from src.agent_loop import _append_tool_results, _is_explicit_continuation
from src.tool_capabilities import capabilities_for_action


def test_explicit_continuation_phrases_inherit_context():
    for text in (
        "Continue",
        "please continue",
        "yes, continue",
        "yes, please continue",
        "go ahead and continue",
        "keep going",
        "continue with that",
        "continue the task",
        "continue until the network report is complete",
        "do that",
        "all of them",
        "do all of the above",
        "resume",
    ):
        assert _is_explicit_continuation(text), text


def test_substantive_request_does_not_inherit_context():
    for text in (
        "thanks",
        "okay, what is DNS?",
        "yes, search the web for X",
        "search the web for current package versions",
    ):
        assert not _is_explicit_continuation(text), text


def test_privileged_status_is_system_read_only():
    capabilities = capabilities_for_action(
        "privileged_action", json.dumps({"action": "status"})
    )
    assert capabilities.known
    assert not capabilities.effects


def test_empty_textual_replay_does_not_append_empty_assistant_turn():
    messages = [{"role": "user", "content": "run the approved action"}]
    _append_tool_results(messages, "", [], ["tool output"], ["tool output"], False, 1)
    assert not any(
        message.get("role") == "assistant"
        and not str(message.get("content") or "").strip()
        for message in messages
    )
