"""Focused regressions for the safe conversational floor below ACI."""

import asyncio
import json


def _events(generator):
    async def collect():
        return [chunk async for chunk in generator]

    parsed = []
    for chunk in asyncio.run(collect()):
        if not chunk.startswith("data: ") or chunk.startswith("data: [DONE]"):
            continue
        try:
            parsed.append(json.loads(chunk[6:]))
        except json.JSONDecodeError:
            pass
    return parsed


def test_invalid_aci_decision_falls_back_without_tool_authority(monkeypatch):
    import src.agent_loop as agent_loop

    monkeypatch.setattr(agent_loop, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *args, **kwargs: 10, raising=False)
    monkeypatch.setattr(agent_loop, "blocked_tools_for_owner", lambda owner: set(), raising=False)

    responses = iter(["not-json", "still-not-json", "A general answer from the active model."])
    provider_calls = []
    executed = []

    async def fake_stream(candidates, messages, **kwargs):
        provider_calls.append({
            "messages": messages,
            "tools": kwargs.get("tools"),
            "response_format": kwargs.get("response_format"),
        })
        yield f'data: {json.dumps({"delta": next(responses)})}\n\n'
        yield "data: [DONE]\n\n"

    async def fail_execute(block, *args, **kwargs):
        executed.append(block.tool_type)
        raise AssertionError("MODEL_FALLBACK must not execute a tool")

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream)
    monkeypatch.setattr(agent_loop, "execute_tool_block", fail_execute)

    events = _events(agent_loop.stream_agent_loop(
        "http://local.test/v1",
        "local-model",
        [{"role": "user", "content": "Do you think this architecture is overcomplicated?"}],
        max_rounds=4,
        relevant_tools={"manage_homelab"},
        aci_mode="aci",
    ))

    assert any(event.get("type") == "aci_fallback" for event in events)
    assert any(event.get("delta") == "A general answer from the active model." for event in events)
    assert executed == []
    assert len(provider_calls) == 3
    assert provider_calls[-1]["tools"] in (None, [])
    assert provider_calls[-1]["response_format"] is None
    fallback_text = " ".join(
        str(message.get("content", "")) for message in provider_calls[-1]["messages"]
    )
    assert "Execution authority: NONE" in fallback_text
    assert "I could not produce a valid bounded decision" not in " ".join(
        str(event.get("delta", "")) for event in events
    )
