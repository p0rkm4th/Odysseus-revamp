"""Intent-level regressions for bounded network discovery execution."""

import asyncio
import json

import src.agent_loop as agent_loop
from src.homelab_operations import DEFAULT_PRIVATE_DISCOVERY_CIDR


def _collect(generator):
    async def run():
        return [item async for item in generator]

    return asyncio.run(run())


def _events(chunks):
    values = []
    for chunk in chunks:
        if not chunk.startswith("data: ") or chunk.startswith("data: [DONE]"):
            continue
        try:
            values.append(json.loads(chunk[6:]))
        except json.JSONDecodeError:
            pass
    return values


def test_network_discovery_request_without_cidr_stays_on_bounded_scope():
    query = (
        "do a deep dive network discovery scan, download whatever network "
        "tools you need, such as nmap or ip. list all hosts and what you "
        "think they are and may do. Begin now"
    )
    assert agent_loop._network_discovery_request_cidr(query) == DEFAULT_PRIVATE_DISCOVERY_CIDR


def test_qwen_prose_only_network_request_gets_one_canonical_plan_repair(monkeypatch):
    """A weak model cannot strand a recognizable action behind prose."""

    query = (
        "do a deep dive network discovery scan, download whatever network "
        "tools you need, such as nmap or ip. list all hosts and what you "
        "think they are and may do. Begin now"
    )
    calls = []
    provider_round = {"value": 0}

    monkeypatch.setattr(agent_loop, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *args, **kwargs: 10)
    monkeypatch.setattr(agent_loop, "blocked_tools_for_owner", lambda owner: set())
    monkeypatch.setattr(agent_loop, "_suppress_automatic_skills", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        agent_loop,
        "_agent_route_tool_mode",
        lambda *args, **kwargs: (True, False, True),
    )

    async def fake_provider(_candidates, _messages, **_kwargs):
        provider_round["value"] += 1
        # Simulate Qwen's observed failure: prose on the initial turn and on
        # the bounded repair prompt, with no native or textual tool call.
        text = (
            "I will use ARP and nmap to inspect the network."
            if provider_round["value"] < 3
            else "The bounded discovery plan is ready for approval."
        )
        yield f'data: {json.dumps({"delta": text})}\n\n'
        yield "data: [DONE]\n\n"

    async def fake_execute(block, *args, **kwargs):
        calls.append(block)
        payload = json.loads(block.content)
        return "manage_homelab", {
            "kind": "plan",
            "action": payload["action"],
            "target": payload["cidr"],
            "operation_digest": "a" * 64,
            "exit_code": 0,
        }

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_provider)
    monkeypatch.setattr(agent_loop, "execute_tool_block", fake_execute)

    chunks = _collect(
        agent_loop.stream_agent_loop(
            "http://ollama:11434/v1",
            "qwen3:8b",
            [{"role": "user", "content": query}],
            max_rounds=3,
            relevant_tools={"manage_homelab"},
            owner="alice",
        )
    )

    assert len(calls) == 1
    assert calls[0].tool_type == "manage_homelab"
    payload = json.loads(calls[0].content)
    assert payload == {
        "action": "plan_network_discovery",
        "cidr": DEFAULT_PRIVATE_DISCOVERY_CIDR,
    }
    assert any(
        event.get("type") == "tool_start" and event.get("tool") == "manage_homelab"
        for event in _events(chunks)
    )
    # The grounding boundary remains intact: only the synthetic tool result,
    # not the model's ARP prose, authorizes an action-completed response.
    assert not any("No action completed" in str(event.get("delta")) for event in _events(chunks))

