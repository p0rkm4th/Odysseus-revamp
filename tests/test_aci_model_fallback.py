"""Focused regressions for the safe conversational floor below ACI."""

import asyncio
import json


def test_conceptual_storage_explanation_does_not_route_to_storage_operations():
    from src.aci import compatibility_intent_projection as _classify_agent_request

    for query in (
        "Explain why RAID isn't a backup.",
        "Why isn't RAID a backup?",
        "Explain in one short sentence why RAID is not a backup.",
    ):
        intent = _classify_agent_request([], query)
        assert "storage_ops" not in intent["domains"]


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


def test_direct_unknown_safe_turn_releases_fallback_prose(monkeypatch):
    """Direct MODEL_FALLBACK must not remain trapped in ACI's text buffer."""
    import src.agent_loop as agent_loop

    monkeypatch.setattr(agent_loop, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *args, **kwargs: 10, raising=False)
    monkeypatch.setattr(agent_loop, "blocked_tools_for_owner", lambda owner: set(), raising=False)

    calls = []

    async def fake_stream(candidates, messages, **kwargs):
        calls.append({"messages": messages, "tools": kwargs.get("tools")})
        yield 'data: {"delta":"A normal answer from the general model."}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream)

    events = _events(agent_loop.stream_agent_loop(
        "http://local.test/v1",
        "local-model",
        [{"role": "user", "content": "Explain why RAID isn't a backup."}],
        max_rounds=2,
        relevant_tools={"manage_homelab"},
        aci_mode="aci",
    ))

    assert any(event.get("delta") == "A normal answer from the general model." for event in events)
    assert len(calls) == 1
    assert calls[0]["tools"] in (None, [])
    metrics = next(event["data"] for event in reversed(events) if event.get("type") == "metrics")
    assert metrics["aci_turn_disposition"] == "MODEL_FALLBACK"
