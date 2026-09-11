"""Intent-level regressions for bounded network discovery execution."""

import asyncio
import json

import src.agent_loop as agent_loop
from src.aci import ground_action_completion
from src.intent_contracts import network_discovery_request_cidr, is_network_service_enumeration_request
from src.tool_approvals import ToolApprovalStore
from src.tool_capabilities import capabilities_for_action


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
    assert network_discovery_request_cidr(query) is None


def test_unscoped_network_deep_dive_is_not_rejected_before_context_resolution():
    from src.intent_contracts import compile_intent

    frame = compile_intent("Do a deep dive on my local network.")
    assert frame.domain_concept == "NETWORK"
    assert "network_scope_requires_authorization" not in frame.constraints


def test_unscoped_network_deep_dive_can_reach_bounded_selection(monkeypatch):
    calls = []
    provider_calls = []

    monkeypatch.setattr(agent_loop, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *args, **kwargs: 10)
    monkeypatch.setattr(agent_loop, "blocked_tools_for_owner", lambda owner: set())

    async def fake_provider(_candidates, messages, **kwargs):
        provider_calls.append({"messages": messages, "tools": kwargs.get("tools")})
        yield 'data: {"delta":"I need an explicitly authorized network scope."}\n\n'
        yield "data: [DONE]\n\n"

    async def fail_execute(block, *args, **kwargs):
        calls.append(block)
        raise AssertionError("unscoped network deep dive must not execute")

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_provider)
    monkeypatch.setattr(agent_loop, "execute_tool_block", fail_execute)

    chunks = _collect(agent_loop.stream_agent_loop(
        "http://local.test/v1",
        "local-model",
        [{"role": "user", "content": "Do a deep dive on my local network."}],
        max_rounds=3,
        relevant_tools={"manage_homelab"},
        owner="alice",
        aci_mode="aci",
    ))
    events = _events(chunks)

    assert calls == []
    assert provider_calls
    assert not any(
        "explicitly authorized target scope" in str(event.get("delta") or "")
        for event in events
    )
    metrics = next(event["data"] for event in reversed(events) if event.get("type") == "metrics")
    assert metrics["aci_turn_disposition"] != "CLARIFY"


def test_service_enumeration_intent_is_distinct_and_grounding_rejects_plan_as_active_scan():
    assert is_network_service_enumeration_request(
        "perform a deeper service scan on all discovered hosts"
    ) is True
    assert is_network_service_enumeration_request(
        "show the network discovery status"
    ) is False
    response = ground_action_completion(
        "The service scan is actively probing all hosts now.",
        intent_domains={"network_ops"},
        tool_events=[{
            "command": json.dumps({"action": "plan_network_service_enumeration"}),
            "exit_code": 0,
        }],
    )
    assert response.startswith("No action completed:")


def test_network_preflight_is_not_terminal_before_approval_or_execution():
    assert agent_loop._is_bounded_network_plan(
        "manage_homelab", "plan_network_service_enumeration",
    ) is True
    assert agent_loop._is_bounded_network_plan(
        "manage_homelab", "execute_network_service_enumeration",
    ) is False
    assert agent_loop._is_bounded_network_plan(
        "manage_assets", "plan_network_service_enumeration",
    ) is False


def test_service_result_action_supports_grounded_active_execution_language():
    response = ground_action_completion(
        "The bounded service scan is running now.",
        intent_domains={"network_ops"},
        tool_events=[{
            "command": json.dumps({"action": "execute_network_service_enumeration"}),
            "exit_code": 0,
        }],
    )
    assert response == "The bounded service scan is running now."


def test_successful_network_execution_is_terminal_for_the_current_turn():
    """A completed scan must not be replanned into a second approval card."""
    assert agent_loop._successful_bounded_network_execution(
        "manage_homelab",
        json.dumps({"action": "execute_network_discovery"}),
        {"success": True, "observations_recorded": True},
    ) is True
    assert agent_loop._successful_bounded_network_execution(
        "manage_homelab",
        json.dumps({"action": "execute_network_discovery"}),
        {"success": True, "approval_required": True},
    ) is False


def test_exact_network_approval_resume_executes_once_without_replanning(monkeypatch):
    """The UI approval continuation must finish the sealed scan in one turn."""
    store = ToolApprovalStore()
    content = json.dumps({
        "action": "execute_network_discovery",
        "cidr": "192.168.10.0/24",
        "plan_digest": "a" * 64,
    })
    pending = store.create(
        owner="alice",
        session_id="session-1",
        origin_run_id="run-1",
        tool_name="manage_homelab",
        content=content,
        workspace=None,
        external_untrusted_context_seen=False,
        capabilities=capabilities_for_action("manage_homelab", content),
    )
    grant = store.consume(
        pending.approval_id,
        decision="approve_task",
        owner="alice",
        session_id="session-1",
    )
    assert grant is not None
    calls = []

    async def fake_execute(block, **kwargs):
        calls.append(block)
        return "manage_homelab", {
            "output": json.dumps({
                "action": "execute_network_discovery",
                "success": True,
                "candidate_count": 2,
                "observations_recorded": True,
            }),
            "exit_code": 0,
        }

    async def fail_provider(*args, **kwargs):
        raise AssertionError("approved network execution must not re-enter the model")
        yield  # pragma: no cover

    monkeypatch.setattr(agent_loop, "execute_tool_block", fake_execute)
    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fail_provider)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None)
    monkeypatch.setattr(agent_loop, "blocked_tools_for_owner", lambda owner: set())
    monkeypatch.setattr(agent_loop, "get_setting", lambda key, default=None: default)

    chunks = _collect(agent_loop.stream_aci_runtime(
        "http://local.test/v1",
        "local-model",
        [{"role": "user", "content": "Scan my network"}],
        max_rounds=3,
        relevant_tools={"manage_homelab"},
        owner="alice",
        session_id="session-1",
        exact_approval=grant,
    ))
    events = _events(chunks)

    assert len(calls) == 1
    assert not any(event.get("type") == "ask_user" for event in events)
    assert sum(event.get("type") == "tool_start" for event in events) == 1
    assert sum(event.get("type") == "tool_output" for event in events) == 1
    assert agent_loop._successful_bounded_network_execution(
        "manage_homelab",
        json.dumps({"action": "plan_network_discovery"}),
        {"success": True},
    ) is False


def test_stored_canonical_evidence_supports_truthful_followup_without_new_action():
    response = ground_action_completion(
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
        if payload["action"] == "read_network_context":
            return "manage_homelab", {
                "action": "read_network_context", "status": "UNAVAILABLE",
                "error_code": "HOST_NETWORK_CONTEXT_UNAVAILABLE", "exit_code": 1,
            }
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

    assert [json.loads(call.content)["action"] for call in calls] == ["read_network_context"]
    assert not any(
        json.loads(call.content).get("action") == "plan_network_discovery"
        for call in calls
    )
    # The grounding boundary remains intact: only the synthetic tool result,
    # not the model's ARP prose, authorizes an action-completed response.
    assert not any("No action completed" in str(event.get("delta")) for event in _events(chunks))
def test_nested_broker_success_terminates_network_turn_without_replanning():
    assert agent_loop._successful_bounded_network_execution(
        "manage_homelab",
        '{"action":"execute_network_discovery","plan_digest":"' + "a" * 64 + '"}',
        {"success": True, "data": {"success": True, "action": "execute_network_discovery"}},
    ) is True
    assert agent_loop._successful_bounded_network_execution(
        "manage_homelab",
        '{"action":"execute_network_discovery","plan_digest":"' + "a" * 64 + '"}',
        {
            "output": json.dumps({
                "action": "execute_network_discovery",
                "success": True,
                "observations_recorded": True,
            }),
            "exit_code": 0,
        },
    ) is True


def test_structured_tool_result_unwraps_approval_resume_output():
    payload = agent_loop._structured_tool_result({
        "output": json.dumps({
            "action": "execute_network_discovery",
            "success": True,
            "observations_recorded": True,
        }),
        "exit_code": 0,
    })
    assert payload["action"] == "execute_network_discovery"
    assert payload["success"] is True
    nested = agent_loop._structured_tool_result({
        "data": {
            "output": json.dumps({
                "action": "execute_network_discovery",
                "success": True,
            }),
            "exit_code": 0,
        },
    })
    assert nested["action"] == "execute_network_discovery"
    assert nested["success"] is True
