import asyncio
import json

from src.aci import (
    CapabilityGapResolution,
    CapabilityGapStage,
    CapabilityCreationRequest,
    CompositeStep,
    SelectionMode,
    canonical_read_fast_path_payload,
    canonical_asset_read_answer,
    canonical_household_read_answer,
    canonical_network_read_answer,
    canonical_inventory_mutation_answer,
    canonical_result_answer,
    project_final_answer,
    project_model_decision,
    AnswerSource,
    assistant_requested_followup,
    classify_action_escalation,
    classify_post_result,
    compile_composite_action,
    ground_action_completion,
    project_action_selection,
    project_post_result_transition,
    project_result_observation,
    should_project_safe_auto_continuation,
    provisional_intent_projection,
    recent_context_for_retrieval,
    is_contextual_retry_continuation,
    project_capability_palette,
    safe_contract_fallback_selection,
    selected_action_for_decision,
    resolve_decision_outcome,
    resolve_decision_recovery,
    resolve_invalid_decision,
    dependency_ready_for_action,
    legacy_completion_verifier_allowed,
    validate_capability_creation_request,
    validate_capability_gap_resolution,
    action_trace,
    insert_before_latest_user,
    last_user_message,
    user_turn_count,
    stream_aci_turn,
)
from src.intent_contracts import canonical_domain_projection, compile_intent, resolve_intent
from src.capability_registry import action_for_tool, capability_for_tool
from src.tool_capabilities import ToolEffect, capabilities_for_action
from src.tool_policy import web_access_mode


def test_owner_computer_collection_variants_compile_to_canonical_asset_reads():
    for query in (
        "yo what computers do i got",
        "what kinda computers?",
        "what it assets do we have",
        "I do got a computer, tell me about it",
    ):
        frame = compile_intent(query)
        resolved = resolve_intent(frame)
        assert frame.domain_concept == "TECHNICAL_ASSET", query
        assert frame.operation_class == "READ", query
        assert resolved.action_id == "list", query
        assert resolved.binding_name == "manage_assets", query


def test_production_aci_stream_entrypoint_forces_canonical_mode(monkeypatch):
    import src.agent_loop as legacy

    captured = {}

    def fake_stream(*args, **kwargs):
        captured.update(kwargs)
        return "canonical-stream"

    monkeypatch.setattr(legacy, "stream_agent_loop", fake_stream)
    assert stream_aci_turn("endpoint", aci_mode="legacy") == "canonical-stream"
    assert captured["aci_mode"] == "aci"


def test_canonical_asset_read_answer_uses_only_structured_result():
    answer = canonical_asset_read_answer([
        {
            "tool": "manage_assets",
            "exit_code": 0,
            "output": json.dumps({
                "status": "SUCCESS",
                "assets": [{"id": "a-1", "name": "Thanatos", "role": "server", "gpu": "RTX 2080"}],
                "asset_count": 1,
            }),
        },
    ])
    assert answer == "I found 1 canonical IT asset:\n- Thanatos (role=server, gpu=RTX 2080)"


def test_canonical_asset_read_answer_preserves_empty_and_rejects_failed_results():
    empty = canonical_asset_read_answer([{
        "tool": "manage_assets", "exit_code": 0,
        "output": '{"status":"SUCCESS_EMPTY","assets":[]}',
    }])
    assert empty == "No canonical IT assets are recorded for this owner."
    assert canonical_asset_read_answer([{
        "tool": "manage_assets", "exit_code": 1,
        "output": '{"status":"FAILED","assets":[]}',
    }]) is None


def test_canonical_asset_read_answer_counts_only_structured_filtered_rows():
    answer = canonical_asset_read_answer([{
        "tool": "manage_assets", "exit_code": 0,
        "output": json.dumps({
            "status": "SUCCESS",
            "query": "2080",
            "result_projection": "count",
            "assets": [
                {"id": "a-1", "name": "Thanatos", "attributes": {"gpu": "RTX 2080"}},
                {"id": "a-2", "name": "Morpheus", "attributes": {"gpu": "RTX 2080"}},
            ],
        }),
    }])
    assert answer == "I found 2 canonical IT assets matching '2080'."


def test_canonical_household_read_answer_uses_only_inventory_result():
    answer = canonical_household_read_answer([{
        "tool": "read_household", "exit_code": 0,
        "output": json.dumps({
            "status": "SUCCESS_WITH_DATA",
            "items": [{"id": "i-1", "name": "Angel hair pasta", "domain": "kitchen", "stock_quantity": "2", "default_unit": "box"}],
        }),
    }])
    assert answer == "I found 1 kitchen/household item:\n- Angel hair pasta (domain=kitchen, quantity=2 box)"
    assert canonical_household_read_answer([{
        "tool": "read_household", "exit_code": 0,
        "output": '{"status":"SUCCESS_EMPTY","items":[]}',
    }]) == "No kitchen or household inventory is recorded for this owner."


def test_canonical_result_answer_selects_one_authoritative_source():
    answer = canonical_result_answer([{
        "tool": "manage_assets", "exit_code": 0,
        "output": json.dumps({"status": "SUCCESS", "assets": [{"name": "Thanatos"}]}),
    }])
    assert answer is not None
    assert answer.source is AnswerSource.DETERMINISTIC_RESULT
    assert answer.provenance == "canonical Asset Result"
    assert answer.content == "I found 1 canonical IT asset:\n- Thanatos"


def test_canonical_answer_suppresses_intermediate_untrusted_summary():
    events = [{
        "tool": "manage_homelab", "exit_code": 0,
        "output": json.dumps({
            "status": "SUCCESS_WITH_DATA", "action": "read_network_context",
            "interfaces": [{"name": "enp1s0", "kind": "PHYSICAL_LAN", "addresses": []}],
            "default_routes": [],
        }),
    }]
    answer = canonical_result_answer(events)
    assert answer is not None
    assert answer.source is AnswerSource.DETERMINISTIC_RESULT
    assert answer.content == "Current host network context (observed):\n- enp1s0 (PHYSICAL_LAN)\nNo default route was observed."


def test_project_final_answer_prefers_canonical_result_over_model_prose():
    response, answer = project_final_answer(
        "The network has a Kubernetes cluster with four nodes.",
        [{
            "tool": "manage_homelab", "exit_code": 0,
            "output": json.dumps({
                "status": "SUCCESS_WITH_DATA", "action": "read_network_context",
                "interfaces": [], "default_routes": [],
            }),
        }],
        intent_domains=("network_ops",),
    )
    assert answer is not None
    assert answer.source is AnswerSource.DETERMINISTIC_RESULT
    assert "Kubernetes" not in response
    assert response == "No current host network interfaces were observed."


def test_project_final_answer_owns_failed_network_read_without_model_fallback():
    response, answer = project_final_answer(
        "Your network has twelve active connections and a Kubernetes cluster.",
        [{
            "tool": "manage_homelab", "exit_code": 1,
            "command": '{"action":"read_network_context"}',
            "output": json.dumps({"status": "UNAVAILABLE", "action": "read_network_context", "error": "broker unavailable"}),
        }],
        intent_domains=("network_ops",),
    )
    assert answer is not None
    assert answer.source is AnswerSource.ERROR
    assert "No current state was inferred" in response
    assert "Kubernetes" not in response
    assert "twelve" not in response


def test_project_final_answer_owns_malformed_asset_read_without_model_fallback():
    response, answer = project_final_answer(
        "You have several servers, GPUs, and databases.",
        [{
            "tool": "manage_assets", "exit_code": 0,
            "command": '{"action":"list"}',
            "output": '{"status":"SUCCESS"}',
        }],
        intent_domains=("asset_inventory",),
    )
    assert answer is not None
    assert answer.source is AnswerSource.ERROR
    assert "canonical asset inventory" in response
    assert "several servers" not in response


def test_canonical_network_read_answer_uses_structured_host_context():
    answer = canonical_network_read_answer([{
        "tool": "manage_homelab", "exit_code": 0,
        "output": json.dumps({
            "status": "SUCCESS_WITH_DATA", "action": "read_network_context",
            "interfaces": [{"name": "enp1s0", "kind": "PHYSICAL_LAN", "addresses": [{"address": "192.168.1.10"}]}],
            "default_routes": [{"gateway": "192.168.1.1"}],
        }),
    }])
    assert answer == (
        "Current host network context (observed):\n"
        "- enp1s0 (PHYSICAL_LAN) addresses=192.168.1.10\n"
        "Default route gateway: 192.168.1.1."
    )
    assert "2001:db8" not in answer


def test_canonical_inventory_mutation_answer_requires_structured_result_and_readback():
    event = {
        "tool": "manage_assets", "exit_code": 0,
        "command": '{"action":"add_item","domain":"kitchen","name":"pasta"}',
        "output": json.dumps({
            "success": True, "item": {"id": "i-1", "name": "pasta"},
            "verification": {"status": "VERIFIED", "readback": {"item": {"id": "i-1"}}},
        }),
    }
    assert canonical_inventory_mutation_answer([event]) == (
        "Recorded pasta; the canonical inventory readback is verified."
    )
    event["output"] = '{"success":true,"item":{"name":"pasta"},"verification":{"status":"INCOMPLETE"}}'
    assert "verification is incomplete" in canonical_inventory_mutation_answer([event])
    event["exit_code"] = 1
    assert "not completed" in canonical_inventory_mutation_answer([event])


def test_canonical_memory_and_work_reads_have_terminal_answers():
    from src.aci import canonical_result_answer

    memory = canonical_result_answer([{
        "tool": "read_memory", "exit_code": 0,
        "result_projection": {
            "status": "zero_result", "query_type": "summary", "retrieved_count": 0,
        },
    }])
    assert memory is not None
    assert memory.source.value == "DETERMINISTIC_RESULT"
    assert "No applicable owner-scoped memories" in memory.content

    work = canonical_result_answer([{
        "tool": "read_work", "exit_code": 0,
        "output": '{"status":"SUCCESS_EMPTY","goals":[],"projects":[],"tasks":[]}',
    }])
    assert work is not None
    assert work.source.value == "DETERMINISTIC_RESULT"
    assert "No outstanding work" in work.content


def _collect_stream_events(generator):
    async def _collect():
        return [chunk async for chunk in generator]

    events = []
    for chunk in asyncio.run(_collect()):
        if not chunk.startswith("data: ") or chunk.startswith("data: [DONE]"):
            continue
        try:
            events.append(json.loads(chunk[6:]))
        except json.JSONDecodeError:
            continue
    return events


def _intent(text):
    frame = compile_intent(text)
    contract = resolve_intent(frame)
    return {
        "intent_frame": frame.as_dict(),
        "resolved_contract": contract.as_dict(),
        "retrieval_query": text,
    }


def test_continuation_context_classifiers_are_aci_projections():
    messages = [
        {"role": "user", "content": "launch the Ollama model"},
        {"role": "assistant", "content": "Which model should I launch?"},
        {"role": "user", "content": "qwen3:8b"},
    ]
    assert assistant_requested_followup(messages)
    assert is_contextual_retry_continuation(
        messages + [{"role": "user", "content": "it failed, try again"}],
        "it failed, try again",
    )


def test_provisional_intent_projection_owns_supported_route_entry():
    intent, owned = provisional_intent_projection(
        [{"role": "user", "content": "what network am i on"}],
        "what network am i on",
    )
    assert owned is True
    assert intent["continuation"] is False
    assert intent["retrieval_query"] == "what network am i on"


def test_aci_completion_uses_canonical_transition_not_legacy_verifier():
    assert legacy_completion_verifier_allowed(
        aci_mode="aci", effectful_used=True, claimed_done=True,
        force_answer=False, verifier_rounds=0, max_verifier_rounds=2,
        enabled=True,
    ) is False
    assert legacy_completion_verifier_allowed(
        aci_mode="legacy", effectful_used=True, claimed_done=True,
        force_answer=False, verifier_rounds=0, max_verifier_rounds=2,
        enabled=True,
    ) is True


def test_provisional_intent_projection_leaves_compatibility_concepts_to_legacy_route():
    intent, owned = provisional_intent_projection([], "draft an email to Alex")
    assert owned is False
    assert intent is None


def test_aci_retrieval_context_excludes_untrusted_tool_envelopes():
    context = recent_context_for_retrieval([
        {"role": "user", "content": "inspect Thanatos"},
        {"role": "user", "content": "[tool output] secret", "metadata": {"trusted": False}},
        {"role": "user", "content": "what changed"},
    ], max_user=5, max_chars=200)
    assert "inspect Thanatos" in context
    assert "secret" not in context


def test_completion_grounding_is_an_aci_projection():
    assert ground_action_completion(
        "The scan is actively probing the lab now.",
        intent_domains={"network_ops"},
        tool_events=[{"command": '{"action":"plan_network_discovery"}', "exit_code": 0}],
    ).startswith("No action completed:")
    assert ground_action_completion(
        "The scan is actively probing the lab now.",
        intent_domains={"network_ops"},
        tool_events=[{"command": '{"action":"execute_network_discovery"}', "exit_code": 0}],
    ) == "The scan is actively probing the lab now."


def test_action_trace_reports_existing_registry_identity_without_selecting():
    trace = action_trace("A", {
        "binding": "manage_homelab",
        "payload": {"action": "read_network_context"},
    })
    assert trace == {
        "choice": "A",
        "binding": "manage_homelab",
        "action_id": "read_network_context",
        "executor": "manage_homelab",
    }
    assert action_trace(None, {"binding": "", "payload": {}}) is None


def test_message_envelope_projection_is_aci_owned():
    messages = [
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": [{"text": "inspect Thanatos"}]},
    ]
    assert last_user_message(messages) == "inspect Thanatos"
    assert user_turn_count(messages) == 1
    context = {"role": "system", "content": "bounded context", "_protected": True}
    projected = insert_before_latest_user(messages, context)
    assert projected[-2] == context
    assert projected[-1] == messages[-1]


def test_canonical_read_projection_uses_zero_model_decision_and_no_raw_tool_schema():
    intent = _intent("what network am i on")
    projection = project_action_selection(
        intent=intent,
        relevant_tools=["manage_homelab"],
        disabled_tools=set(),
        owner="owner",
        active_run=None,
        query="what network am i on",
    )
    assert projection.mode is SelectionMode.DIRECT_ACTION
    assert projection.fast_path == {"action": "read_network_context"}
    assert projection.packet is not None
    assert projection.packet.action_cards
    assert all("action_id" not in card for card in projection.packet.model_projection()["action_cards"])


def test_canonical_projection_does_not_depend_on_route_tool_preparation():
    projection = project_action_selection(
        intent=_intent("what network am i on"),
        relevant_tools=None,
        disabled_tools=set(),
        owner="owner",
        active_run=None,
        query="what network am i on",
    )
    assert projection.mode is SelectionMode.DIRECT_ACTION
    assert projection.fast_path == {"action": "read_network_context"}
    assert set(item["binding"] for item in projection.choice_map.values()) == {"manage_homelab"}


def test_action_projection_carries_canonical_dependency_plan():
    intent = _intent("discover hosts on 192.168.10.0/24")
    projection = project_action_selection(
        intent=intent,
        relevant_tools=["manage_homelab"],
        disabled_tools=set(),
        owner="owner",
        active_run=None,
        query="discover hosts on 192.168.10.0/24",
        network_cidr="192.168.10.0/24",
    )
    selected = next(
        value for value in projection.choice_map.values()
        if value["payload"].get("action") == "execute_network_discovery"
    )
    assert selected["dependency_plan"]["canonical_source"] == "ActionSpec.dependencies"
    assert [item["dependency_id"] for item in selected["dependency_plan"]["dependencies"]] == ["binary.nmap"]
    card = next(card for card in projection.packet.action_cards if card.choice == next(
        choice for choice, value in projection.choice_map.items() if value is selected
    ))
    assert f"dependency_status:{selected['dependency_plan']['status']}" in card.preconditions


def test_dependency_status_blocks_action_revalidation_until_remediation():
    from src.aci import DecisionContract, DecisionMode

    action = {
        "binding": "manage_homelab", "action_id": "execute_network_discovery",
        "payload": {"action": "execute_network_discovery"},
        "dependency_plan": {"status": "REQUIRES_APPROVAL"},
    }
    assert not dependency_ready_for_action(action)
    assert selected_action_for_decision(
        DecisionContract(decision=DecisionMode.ACTION, choice="A"), {"A": action}
    ) is None
    assert safe_contract_fallback_selection(
        {"resolved_contract": {"binding": "manage_homelab", "action_id": "execute_network_discovery"}},
        {"A": action},
    ) is None

    ready = {**action, "dependency_plan": {"status": "AVAILABLE"}}
    assert dependency_ready_for_action(ready)
    assert selected_action_for_decision(
        DecisionContract(decision=DecisionMode.ACTION, choice="A"), {"A": ready}
    ) == ready


def test_canonical_read_payload_builder_owns_memory_and_developer_shapes():
    assert canonical_read_fast_path_payload(
        "read_memory", "summarize_owner_memory", {}, query="what did I save"
    ) == {"action": "summarize_owner_memory", "query": "what did I save"}
    assert canonical_read_fast_path_payload(
        "developer_read", "search_code", {}, query="search for compile_intent"
    ) == {"action": "search_code", "query": "compile_intent"}
    assert canonical_read_fast_path_payload(
        "developer_read", "show_repo_map", {"filters": {"view": "map"}}, query="show files"
    ) == {"action": "show_repo_map", "query": "**/*"}


def test_aci_domain_projection_replaces_legacy_transport_domain_for_supported_concepts():
    assert canonical_domain_projection(compile_intent("what network am i on")) == frozenset({"network_ops"})
    assert canonical_domain_projection(compile_intent("what hardware is in Thanatos")) == frozenset({"asset_inventory"})
    assert canonical_domain_projection(compile_intent("what is a network")) == frozenset()


def test_disabled_capability_cannot_become_a_projected_action():
    projection = project_action_selection(
        intent=_intent("what network am i on"),
        relevant_tools=["manage_homelab"],
        disabled_tools={"manage_homelab"},
        owner="owner",
        active_run=None,
        query="what network am i on",
    )
    assert not projection.choice_map
    assert projection.fast_path is None


def test_selected_action_resolution_revalidates_registry_backing():
    from src.aci import DecisionContract, DecisionMode

    decision = DecisionContract(decision=DecisionMode.ACTION, choice="A")
    selected = selected_action_for_decision(decision, {
        "A": {"binding": "manage_assets", "action_id": "list", "payload": {"action": "list"}},
    })
    assert selected is not None
    assert selected["action_id"] == "list"

    assert selected_action_for_decision(decision, {
        "A": {"binding": "not-a-registered-binding", "action_id": "list"},
    }) is None


def test_decision_outcome_keeps_action_and_fallback_interpretation_in_aci():
    from src.aci import DecisionContract, DecisionMode

    choices = {
        "A": {"binding": "manage_assets", "action_id": "list",
              "payload": {"action": "list"}},
    }
    selected = resolve_decision_outcome(
        DecisionContract(decision=DecisionMode.ACTION, choice="A"),
        choices,
    )
    assert selected.action == choices["A"]
    assert not selected.invalid_action

    answer = resolve_decision_outcome(
        DecisionContract(decision=DecisionMode.ANSWER, answer="already known"),
        choices,
    )
    assert answer.action is None
    assert answer.answer == "already known"

    invalid = resolve_decision_outcome(
        DecisionContract(decision=DecisionMode.ACTION, choice="A"),
        {"A": {"binding": "not-a-registered-binding", "action_id": "list"}},
    )
    assert invalid.action is None
    assert invalid.invalid_action


def test_invalid_decision_recovery_is_bounded_and_authority_free():
    repair = resolve_decision_recovery(
        "malformed_json", repair_count=0, max_repairs=1,
    )
    assert repair.mode == "REPAIR"
    assert repair.repair_count == 1
    assert repair.reason == "malformed_json"

    fallback = resolve_decision_recovery(
        "stale_state_fingerprint", repair_count=1, max_repairs=1,
    )
    assert fallback.mode == "MODEL_FALLBACK"
    assert fallback.repair_count == 1
    assert fallback.reason == "stale_state_fingerprint"


def test_invalid_decision_resolution_converges_fallback_repair_and_model_modes():
    choices = {
        "A": {"binding": "manage_assets", "action_id": "list",
              "payload": {"action": "list"}},
    }
    intent = _intent("what computers do i own")
    contract = resolve_invalid_decision(
        "malformed_json", intent=intent, choice_map=choices,
        contract_fallback_used=False, repair_count=0, max_repairs=1,
    )
    assert contract.mode == "CONTRACT_FALLBACK"
    assert contract.action == choices["A"]

    repair = resolve_invalid_decision(
        "malformed_json", intent=_intent("do something"), choice_map={},
        contract_fallback_used=False, repair_count=0, max_repairs=1,
    )
    assert repair.mode == "REPAIR"
    assert repair.repair_count == 1

    fallback = resolve_invalid_decision(
        "malformed_json", intent=_intent("do something"), choice_map={},
        contract_fallback_used=True, repair_count=1, max_repairs=1,
    )
    assert fallback.mode == "MODEL_FALLBACK"
    assert fallback.action is None


def test_project_model_decision_keeps_parse_recovery_and_selection_in_aci():
    from src.aci import ActionCard, AgentTaskPacket, DecisionMode

    packet = AgentTaskPacket(
        task_type="read",
        objective={},
        progress={},
        entities=(),
        current_state={},
        evidence=(),
        knowns=(),
        unknowns=(),
        decisions=(),
        action_cards=(ActionCard("A", "list", "List", "List assets"),),
        constraints=(),
        completion={},
        output_contract="json",
        state_fingerprint="fp-1",
    )
    decision, error, recovery, outcome = project_model_decision(
        '{"decision":"ACTION","choice":"A","state_fingerprint":"fp-1"}',
        packet,
        choice_map={"A": {"binding": "manage_assets", "action_id": "list"}},
    )
    assert decision is not None and decision.decision is DecisionMode.ACTION
    assert error is None and recovery is None
    assert outcome is not None and outcome.action["action_id"] == "list"

    decision, error, recovery, outcome = project_model_decision(
        "not json",
        packet,
        choice_map={},
        repair_count=0,
        max_repairs=1,
    )
    assert decision is None and error == "malformed_json"
    assert recovery is not None and recovery.mode == "REPAIR"
    assert outcome is None


def test_safe_contract_fallback_reuses_only_the_resolved_private_read():
    intent = _intent("what network am i on")
    projection = project_action_selection(
        intent=intent,
        relevant_tools=["manage_homelab"],
        disabled_tools=set(),
        owner="owner",
        active_run=None,
        query="what network am i on",
    )
    assert safe_contract_fallback_selection(intent, projection.choice_map) is not None

    write_intent = _intent("restart jellyfin")
    assert safe_contract_fallback_selection(write_intent, {"A": {
        "binding": "manage_homelab", "payload": {"action": "restart_service"},
    }}) is None


def test_resolved_direct_action_does_not_project_unrelated_route_tools():
    projection = project_action_selection(
        intent=_intent("what computers do i own"),
        relevant_tools=["manage_assets", "manage_homelab", "read_memory"],
        disabled_tools=set(),
        owner="owner",
        active_run=None,
        query="what computers do i own",
    )
    assert projection.fast_path == {"action": "list"}
    assert {item["binding"] for item in projection.choice_map.values()} == {"manage_assets"}


def test_aci_turn_does_not_reenter_legacy_tool_index_projection(monkeypatch):
    import src.agent_loop as agent_loop
    import src.tool_index as tool_index

    monkeypatch.setattr(agent_loop, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "blocked_tools_for_owner", lambda owner: set(), raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *args, **kwargs: 10, raising=False)

    def unexpected_tool_index_lookup():
        raise AssertionError("canonical ACI turn re-entered legacy tool index")

    monkeypatch.setattr(tool_index, "get_tool_index", unexpected_tool_index_lookup)
    for name in (
        "_normalize_asset_inventory_intent",
        "_normalize_homelab_intent",
        "_normalize_operational_intent_evidence",
    ):
        monkeypatch.setattr(
            agent_loop,
            name,
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("canonical ACI turn re-entered legacy intent normalizer")
            ),
        )
    executed = []

    async def fake_execute(block, *args, **kwargs):
        executed.append(block.tool_type)
        return block.tool_type, {"output": "network context", "exit_code": 0}

    async def fake_stream(*args, **kwargs):
        yield 'data: {"delta":"The current network context is available."}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream, raising=False)

    events = _collect_stream_events(
        agent_loop.stream_agent_loop(
            "http://local.test/v1",
            "small-local-model",
            [{"role": "user", "content": "what network am i on"}],
            aci_mode="aci",
            tool_executor=fake_execute,
        )
    )

    assert executed == ["manage_homelab"]
    assert any(event.get("type") == "metrics" for event in events)


def test_canonical_aci_turn_does_not_append_legacy_hard_capability_directive(monkeypatch):
    import src.agent_loop as agent_loop

    monkeypatch.setattr(agent_loop, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "blocked_tools_for_owner", lambda owner: set(), raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *args, **kwargs: 10, raising=False)

    def unexpected_legacy_directive(*args, **kwargs):
        raise AssertionError("canonical ACI turn re-entered legacy hard capability prompt")

    monkeypatch.setattr(agent_loop, "_hard_turn_capability_directive", unexpected_legacy_directive)

    async def fake_execute(block, *args, **kwargs):
        return block.tool_type, {"output": "network context", "exit_code": 0}

    async def fake_stream(*args, **kwargs):
        yield 'data: {"delta":"The current network context is available."}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream, raising=False)
    events = _collect_stream_events(agent_loop.stream_agent_loop(
        "http://local.test/v1", "small-local-model",
        [{"role": "user", "content": "what network am i on"}],
        aci_mode="aci", tool_executor=fake_execute,
    ))
    assert any(event.get("type") == "metrics" for event in events)


def test_canonical_aci_projection_skips_post_packet_legacy_network_repair():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "src" / "agent_loop.py").read_text(encoding="utf-8")
    start = source.index("# A caller/RAG route may have selected an observation reader")
    end = source.index("if _ody_doc_finetune_mode", start)
    repair = source[start:end]
    assert "and not _aci_canonical_tool_projection" in repair


def test_canonical_aci_projection_skips_legacy_action_repairs_after_provider_round():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "src" / "agent_loop.py").read_text(encoding="utf-8")
    start = source.index('if not _aci_canonical_tool_projection and (')
    end = source.index("# A skill the model just loaded", start)
    post_round = source[start:end]
    assert post_round.count("not _aci_canonical_tool_projection") >= 6
    assert "and all(block.tool_type in {\"bash\", \"run_shell\"}" in post_round
    assert "_ody_network_execute_match" in post_round
    assert "_hard_action_no_action" in post_round


def test_failed_aci_action_is_not_retried_without_new_evidence(monkeypatch):
    import src.agent_loop as agent_loop

    monkeypatch.setattr(agent_loop, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "blocked_tools_for_owner", lambda owner: set(), raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *args, **kwargs: 10, raising=False)
    executed = []

    async def fake_execute(block, *args, **kwargs):
        executed.append(block.tool_type)
        return block.tool_type, {"error": "fixture unavailable", "exit_code": 1}

    async def fake_stream(*args, **kwargs):
        yield 'data: {"delta":"{\\"decision\\":\\"ACTION\\",\\"choice\\":\\"A\\"}"}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream, raising=False)
    events = _collect_stream_events(
        agent_loop.stream_agent_loop(
            "http://local.test/v1",
            "small-local-model",
            [{"role": "user", "content": "scan 192.168.1.0/24"}],
            aci_mode="aci",
            tool_executor=fake_execute,
        )
    )

    assert executed == ["manage_homelab"]
    metrics = next(event["data"] for event in events if event.get("type") == "metrics")
    assert metrics["aci_trace"]["failed_actions"] == 1
    assert metrics["aci_trace"]["post_result_state"] == "BLOCKED"


def test_no_applicable_action_escalates_in_bounded_order():
    assert classify_action_escalation(
        domain="X", operation="READ", action_count=0,
    ) is SelectionMode.NO_APPLICABLE_ACTION
    palette = project_capability_palette(("memory.read",), limit=1)
    assert classify_action_escalation(
        domain="X", operation="READ", action_count=0,
        retrieval_expanded=True, palette=palette,
    ) is SelectionMode.COMPOSE
    gap = classify_action_escalation(
        domain="X", operation="CREATE", action_count=0,
        retrieval_expanded=True,
    )
    assert gap.selection is SelectionMode.CREATE_CAPABILITY


def test_failed_canonical_read_is_terminal_for_the_current_action_attempt():
    assert classify_post_result(
        {"error": "unavailable", "exit_code": 1}, canonical_read=True,
    ).value == "BLOCKED"


def test_post_result_transition_projects_completion_without_loop_authority():
    completed = project_post_result_transition(
        {"output": "current state", "exit_code": 0},
        deterministic_fast_path=True,
    )
    assert completed.state.value == "COMPLETE_AFTER_ANSWER"
    assert completed.answer_only is True
    assert completed.completion_satisfied is True

    failed = project_post_result_transition(
        {"error": "unavailable", "exit_code": 1},
        selected_action={"binding": "manage_homelab", "action_id": "service_status"},
    )
    assert failed.state.value == "BLOCKED"
    assert failed.answer_only is True
    assert failed.framework_event == "canonical_action_failure"


def test_composition_only_accepts_registered_primitives_and_acyclic_graphs():
    composite, errors = compile_composite_action(
        owner="owner",
        domain="MEMORY",
        steps=[
            CompositeStep("read", "memory.read", "summarize_owner_memory"),
            CompositeStep("inspect", "memory.read", "inspect_memory", depends_on=("read",)),
        ],
    )
    assert errors == ()
    assert composite is not None
    assert composite.state_fingerprint

    invalid, errors = compile_composite_action(
        owner="owner",
        domain="MEMORY",
        steps=[
            {"id": "a", "capability_id": "memory.read", "action_id": "summarize_owner_memory", "depends_on": ["b"]},
            {"id": "b", "capability_id": "memory.read", "action_id": "inspect_memory", "depends_on": ["a"]},
        ],
    )
    assert invalid is None
    assert "dependency_cycle" in errors


def test_capability_creation_is_staged_and_cannot_widen_authority():
    request = CapabilityCreationRequest(
        owner="owner", domain="TEST", operation="read_status",
        workspace="/workspace", tests=("test_read_status",),
    )
    assert validate_capability_creation_request(request) == (True, ())
    unsafe = CapabilityCreationRequest(
        owner="owner", domain="TEST", operation="read_status",
        workspace="/workspace", tests=("test_read_status",),
        authority_constraints=("no_new_filesystem_scope",),
    )
    valid, errors = validate_capability_creation_request(unsafe)
    assert not valid
    assert "authority_constraints_incomplete" in errors


def test_developer_aci_cannot_make_an_implementation_trusted_before_registration():
    request = CapabilityCreationRequest(
        owner="owner", domain="TEST", operation="read_status",
        workspace="/workspace", tests=("test_read_status",),
    )
    staged = CapabilityGapResolution(
        request=request,
        stage=CapabilityGapStage.STAGED,
        implementation_digest="sha256:test",
        tests_passed=True,
        security_validated=True,
        policy_validated=True,
    )
    assert validate_capability_gap_resolution(staged) == (True, ())
    invalid = CapabilityGapResolution(
        request=request,
        stage=CapabilityGapStage.REGISTERED,
        implementation_digest="sha256:test",
        tests_passed=True,
        security_validated=True,
        policy_validated=True,
        registered=False,
    )
    assert validate_capability_gap_resolution(invalid) == (True, ())
    unvalidated = CapabilityGapResolution(
        request=request, stage=CapabilityGapStage.REGISTERED,
        implementation_digest="sha256:test", registered=True,
    )
    valid, errors = validate_capability_gap_resolution(unvalidated)
    assert not valid
    assert "tests_not_passed" in errors


def test_web_is_an_auto_evidence_capability_with_an_explicit_off_policy():
    assert web_access_mode(None, None) == "AUTO"
    assert web_access_mode("false", None) == "OFF"
    assert web_access_mode(None, "true") == "ON"
    assert capability_for_tool("web_search").capability_id == "web.evidence"
    assert action_for_tool("web_search", {"action": "search"}).known is True
    assert action_for_tool("web_fetch", {"action": "fetch"}).known is True
    assert ToolEffect.BROKERED_NETWORK_READ in capabilities_for_action(
        "web_search", {"action": "search"}
    ).effects
    assert ToolEffect.NETWORK_EGRESS in capabilities_for_action(
        "web_fetch", {"action": "fetch"}
    ).effects


def test_web_evidence_projects_as_a_read_without_a_manual_routing_mode():
    projection = project_action_selection(
        intent=_intent("what is the newest NVIDIA driver"),
        relevant_tools=["web_search", "web_fetch"],
        disabled_tools=set(),
        owner="owner",
        active_run=None,
        query="what is the newest NVIDIA driver",
    )
    assert projection.mode is SelectionMode.DIRECT_ACTION
    assert {item["binding"] for item in projection.choice_map.values()} == {"web_search"}
    assert all(card.effect == "read only" for card in projection.packet.action_cards)


def test_safe_auto_continuation_gate_is_bounded_and_pure():
    base = {
        "persisted_work_result": {"status": "completed"},
        "result": {"exit_code": 0},
        "work_run_id": "run-1",
        "continuation_count": 0,
        "max_continuations": 8,
        "initial_tool_block_count": 1,
        "current_tool_index": 0,
        "tool_block_count": 1,
    }
    assert should_project_safe_auto_continuation(**base) is True
    for key, value in (
        ("result", {"error": "failed"}),
        ("continuation_count", 8),
        ("initial_tool_block_count", 2),
        ("current_tool_index", 1),
        ("work_run_id", ""),
    ):
        candidate = dict(base)
        candidate[key] = value
        assert should_project_safe_auto_continuation(**candidate) is False


def test_result_observation_projection_preserves_trace_state_without_authority():
    completed = project_post_result_transition(
        {"exit_code": 0, "verified": True}, canonical_read=True,
    )
    observed = project_result_observation(
        {"exit_code": 0, "verified": True, "approved": True}, completed,
        selected_action={"executor": "host.inspect"},
    )
    assert observed == {
        "verification": "VERIFIED",
        "approval_state": "GRANTED",
        "policy_state": "EVALUATED",
        "executors": ["host.inspect"],
    }

    blocked = project_post_result_transition({"blocked": True})
    observed = project_result_observation(
        {"blocked": True, "policy_blocked": True}, blocked,
        previous_approval_state="REQUIRED",
        previous_policy_state="EVALUATED",
        executors=["host.inspect"],
    )
    assert observed["verification"] == "FAILED"
    assert observed["approval_state"] == "REQUIRED"
    assert observed["policy_state"] == "BLOCKED"
    assert observed["executors"] == ["host.inspect"]
