"""Intent-level regressions for bounded network discovery execution."""

import asyncio
import json

import src.agent_loop as agent_loop


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


def test_network_discovery_request_without_cidr_does_not_reuse_historical_scope():
    query = (
        "do a deep dive network discovery scan, download whatever network "
        "tools you need, such as nmap or ip. list all hosts and what you "
        "think they are and may do. Begin now"
    )
    assert agent_loop._network_discovery_request_cidr(query) is None


def test_service_enumeration_intent_is_distinct_and_grounding_rejects_plan_as_active_scan():
    assert agent_loop._network_service_enumeration_request(
        "perform a deeper service scan on all discovered hosts"
    ) is True
    assert agent_loop._network_service_enumeration_request(
        "show the network discovery status"
    ) is False
    response = agent_loop.ground_action_completion(
        "The service scan is actively probing all hosts now.",
        intent_domains={"network_ops"},
        tool_events=[{
            "command": json.dumps({"action": "plan_network_service_enumeration"}),
            "exit_code": 0,
        }],
    )
    assert response.startswith("No action completed:")


def test_service_result_action_supports_grounded_active_execution_language():
    response = agent_loop.ground_action_completion(
        "The bounded service scan is running now.",
        intent_domains={"network_ops"},
        tool_events=[{
            "command": json.dumps({"action": "execute_network_service_enumeration"}),
            "exit_code": 0,
        }],
    )
    assert response == "The bounded service scan is running now."


def test_stored_canonical_evidence_supports_truthful_followup_without_new_action():
    response = agent_loop.ground_action_completion(
        "The containers currently recorded for Odysseus are healthy.",
        intent_domains={"homelab"},
        tool_events=[],
        stored_evidence=True,
    )
    assert response == "The containers currently recorded for Odysseus are healthy."


def test_qwen_prose_only_network_request_does_not_get_a_stale_scope_repair(monkeypatch):
    """A weak model cannot cause a historical scope to be scanned by prose."""

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

    assert calls == []
    assert not any(event.get("type") == "tool_start" for event in _events(chunks))
    # The grounding boundary remains intact: only the synthetic tool result,
    # not the model's ARP prose, authorizes an action-completed response.
    assert not any("No action completed" in str(event.get("delta")) for event in _events(chunks))
