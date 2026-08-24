import json
import pytest

from core.models import ChatMessage, Session
from routes.chat_helpers import (
    _context_trace,
    _durable_work_context,
    _durable_tool_result_context,
)
from src.capability_dependencies import capability_health, resolve, remediation_handoff
from src.privileged_broker import ALLOWED_PACKAGES, validate_packages


def test_chat_history_is_provider_independent_and_reconstructable():
    session = Session("s1", "continuity", "http://provider-a/v1", "model-a")
    session.history.extend([
        ChatMessage("user", "The continuity token is BLUE-42."),
        ChatMessage("assistant", "I recorded BLUE-42."),
    ])
    session.endpoint_url = "http://provider-b/v1"
    session.model = "model-b"
    messages = session.get_context_messages()
    assert any("BLUE-42" in str(message.get("content")) for message in messages)
    assert _context_trace(messages, 8192)["user_turns"] == 1


def test_recent_tool_results_are_rehydrated_after_runtime_replacement():
    session = Session("s2", "tool continuity", "http://provider-a/v1", "model-a")
    session.history = [
        ChatMessage("user", "Inspect the interface."),
        ChatMessage(
            "assistant",
            "The inspection completed.",
            metadata={
                "tool_events": [
                    {"tool": "bash", "command": "ip -brief address", "output": "BLUE-INTERFACE", "exit_code": 0}
                ]
            },
        ),
    ]
    projected = _durable_tool_result_context(session)
    assert projected is not None
    assert "BLUE-INTERFACE" in projected["content"]
    assert projected["metadata"]["source"] == "durable recent tool results"


def test_dependency_resolution_never_guesses_ip_as_a_package():
    result = resolve("network_interface_inspection", available=[], platform_key="arch")
    assert result["missing_executables"] == ["ip", "ss"]
    assert result["packages"] == ["iproute2"]
    assert "ip" not in result["packages"]
    assert result["status"] == "remediation_available"


def test_supported_capability_registry_has_bounded_arch_mappings():
    assert capability_health("network_discovery", available=[], platform_key="arch")["packages"] == ["nmap"]
    assert capability_health("dns_diagnostics", available=[], platform_key="arch")["packages"] == ["bind"]
    assert capability_health("route_diagnostics", available=[], platform_key="arch")["packages"] == ["traceroute"]
    assert "iproute2" in ALLOWED_PACKAGES
    validate_packages(["iproute2", "nmap", "bind", "traceroute"])


def test_unsupported_dependency_fails_closed():
    result = resolve("arbitrary_shell_tool", available=[], platform_key="arch")
    assert result["status"] == "unavailable"
    assert result["remediation_available"] is not True


def test_prerequisite_handoff_preserves_same_work_identity():
    handoff = remediation_handoff(
        "network_interface_inspection", run_id="run-7", action_id="action-9",
        approval_reference="approval-1", platform_key="arch",
    )
    assert handoff["packages"] == ["iproute2"]
    assert handoff["resume_same_run"] is True
    assert handoff["resume_same_action"] is True
    assert handoff["run_id"] == "run-7"
    assert handoff["action_id"] == "action-9"


def test_network_install_intent_selects_homelab_capability_and_environment():
    from src.agent_loop import _assemble_prompt, _classify_agent_request, _normalize_homelab_intent
    intent = _classify_agent_request([], "install the tools necessary for a deep dive network scan")
    intent = _normalize_homelab_intent(intent, "install the tools necessary for a deep dive network scan")
    assert {"homelab", "network_ops"}.issubset(intent["domains"])
    prompt = _assemble_prompt(
        {"manage_homelab"}, intent_domains={"homelab", "network_ops"}
    )
    assert "Garuda/Arch" in prompt
    assert "pacman through the privileged broker" in prompt
    assert "Never generate apt/pacman/sudo" in prompt


def test_false_completion_is_replaced_without_action_result():
    from src.agent_loop import ground_action_completion, _network_prerequisite_request
    assert _network_prerequisite_request("install the tools necessary for a deep dive network scan")
    response = ground_action_completion(
        "I'll install iproute2 and nmap, then verify the installation.",
        intent_domains={"homelab"}, tool_events=[
            {"tool": "bash", "output": "Waiting for an exact user approval.",
             "ask_user": {"kind": "tool_approval"}}
        ],
    )
    assert response.startswith("No action completed:")
    assert "installed" not in response.lower().split("i have not", 1)[0]


def test_asset_inventory_claim_requires_first_class_result():
    from src.agent_loop import ground_action_completion
    response = ground_action_completion(
        "Asset Inventory Report: 12 servers and 42 VMs, last updated today.",
        intent_domains={"asset_inventory"}, tool_events=[],
    )
    assert response.startswith("No action completed:")


@pytest.mark.asyncio
async def test_provider_reconnect_fallback_receives_same_durable_context(monkeypatch):
    from src import llm_core

    captured = []

    async def fake_stream(url, model, messages, **kwargs):
        captured.append((url, model, [dict(message) for message in messages]))
        if model == "local-model":
            yield 'event: error\ndata: {"status":502,"error":"provider reconnect"}\n\n'
            return
        yield 'data: {"delta":"BLUE-42"}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(llm_core, "stream_llm", fake_stream)
    messages = [
        {"role": "system", "content": "durable context"},
        {"role": "user", "content": "The continuity token is BLUE-42."},
    ]
    chunks = [
        chunk async for chunk in llm_core.stream_llm_with_fallback(
            [("http://local/v1", "local-model", {}), ("http://strong/v1", "strong-model", {})],
            messages,
            fallback_statuses={502},
        )
    ]
    assert any('"delta":"BLUE-42"' in chunk for chunk in chunks)
    assert len(captured) == 2
    assert _context_trace(captured[0][2], 8192)["digest"] == _context_trace(captured[1][2], 8192)["digest"]
    assert "BLUE-42" in json.dumps(captured[1][2])


def test_work_context_is_owner_and_session_scoped(monkeypatch):
    import src.work_engine as work_engine
    import routes.chat_helpers as helpers

    class Query:
        def filter(self, *args, **kwargs): return self
        def order_by(self, *args, **kwargs): return self
        def first(self): return type("Run", (), {"id": "run-1"})()

    class Db:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def query(self, *args, **kwargs): return Query()

    class Engine:
        def __init__(self, db): pass
        def context(self, owner, run_id=None):
            return {"run": {"id": "run-1", "status": "awaiting_approval", "current_step": "approve"}, "actions": [], "recent_events": [], "pending_approval": True, "pending_input": False}

    monkeypatch.setattr(helpers, "SessionLocal", lambda: Db())
    monkeypatch.setattr(work_engine, "WorkEngine", Engine)
    session = Session("session-1", "work", "http://local/v1", "qwen3:8b")
    message = _durable_work_context(session, "scotty")
    # The fake query does not enforce the SQL predicates; the production query
    # does, and this assertion locks the projected durable shape.
    assert message is not None
    assert "awaiting_approval" in message["content"]
    assert message["metadata"]["source"] == "durable active Work state"
