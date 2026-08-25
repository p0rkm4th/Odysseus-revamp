import pytest

from src.intent_contracts import (
    DOMAIN_CONTRACTS,
    compile_intent,
    resolve_continuation,
    generated_parity_matrix,
    resolve_intent,
    result_status,
    validate_result,
    validate_contracts,
    resolve_structured_reference,
)


def test_contract_registry_is_complete_for_registered_contracts():
    assert validate_contracts() == []


def test_communications_read_uses_canonical_owner_scoped_projection():
    frame = compile_intent("What communications are configured?")
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "COMMUNICATIONS"
    assert frame.operation_class == "READ"
    assert resolved.available is True
    assert resolved.contract.capability_id == "communications.read"
    assert resolved.action_id == "overview"
    assert resolved.binding_name == "read_communications"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "What IT assets do I have?",
    "What machines are recorded?",
    "Show my servers.",
    "What technical equipment do we know about?",
])
def test_technical_asset_paraphrases_compile_to_one_read_contract(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "TECHNICAL_ASSET"
    assert frame.operation_class == "READ"
    assert resolved.available is True
    assert resolved.contract.capability_id == "inventory.manage"
    assert resolved.action_id == "list"
    assert resolved.binding_name == "manage_assets"
    assert resolved.action.approval.value == "none"


def test_continuation_and_depth_are_structured_not_phrase_specific():
    frame = compile_intent(
        "perform a deep scan of all discovered hosts",
        continuation=False,
        run_reference="run-1",
    )
    assert frame.domain_concept == "NETWORK"
    assert frame.operation_class == "EXECUTE"
    assert frame.depth == "DEEP"
    continued = compile_intent("continue", continuation=True, run_reference="run-1")
    assert continued.operation_class == "CONTINUE"
    assert continued.run_reference == "run-1"
    assert continued.workspace_hint is None


@pytest.mark.parametrize(("query", "view", "action_id"), [
    ("Which hosts are unidentified on my network?", "unidentified", "list_unidentified_hosts"),
    ("Which devices look like servers?", "roles", "infer_role_hypotheses"),
])
def test_network_read_views_compile_to_specialized_canonical_contracts(query, view, action_id):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "NETWORK"
    assert frame.operation_class == "READ"
    assert frame.filters["view"] == view
    assert resolved.available is True
    assert resolved.action_id == action_id
    assert resolved.action.approval.value == "none"


def test_network_specialized_result_contracts_are_structured():
    unidentified = compile_intent("Which hosts are unidentified on my network?")
    roles = compile_intent("Which devices look like servers?")
    assert validate_result(unidentified, {"status": "EMPTY_RESULT", "hosts": []}) == (True, "EMPTY_RESULT")
    assert validate_result(roles, {"status": "SUCCESS", "hypotheses": []}) == (True, "SUCCESS")
    assert validate_result(unidentified, {"status": "SUCCESS", "nodes": [], "edges": []}) == (False, "INVALID_RESULT")


def test_structured_reference_resolves_single_opaque_entity_without_authority():
    context = {"entities": [{"ref": "network-host:abc", "concept": "NETWORK"}]}
    resolution = resolve_structured_reference("scan it", context)
    assert resolution == {
        "status": "RESOLVED",
        "refs": ["network-host:abc"],
        "concept": "NETWORK",
        "concepts": ["NETWORK"],
        "selection": "ONE",
    }
    frame = compile_intent("scan it", reference_context=context)
    assert frame.entity_reference == "network-host:abc"
    assert frame.domain_concept == "NETWORK"
    assert frame.operation_class == "EXECUTE"


def test_structured_reference_preserves_exact_plural_scope_and_fails_closed():
    context = {"entities": [
        {"ref": "network-host:a", "concept": "NETWORK"},
        {"ref": "network-host:b", "concept": "NETWORK"},
    ]}
    frame = compile_intent("scan those devices", reference_context=context)
    assert frame.filters["entity_refs"] == ["network-host:a", "network-host:b"]
    assert frame.reference_resolution["selection"] == "ALL"
    ambiguous = resolve_structured_reference("scan that", context)
    assert ambiguous["status"] == "AMBIGUOUS"
    assert ambiguous["refs"] == []


def test_structured_reference_ordinal_is_bounded_and_durable():
    context = {"entities": [
        {"ref": "asset:first", "concept": "TECHNICAL_ASSET"},
        {"ref": "asset:second", "concept": "TECHNICAL_ASSET"},
    ]}
    frame = compile_intent("show the second one", reference_context=context)
    assert frame.entity_reference == "asset:second"
    assert frame.domain_concept == "TECHNICAL_ASSET"
    assert resolve_structured_reference("show the third one", context)["status"] == "UNRESOLVED"


@pytest.mark.parametrize("query", [
    "continue until the network report is complete",
    "please resume that task",
    "go ahead and finish it",
    "keep going with the current Run",
    "do that",
    "all of them",
    "do all of the above",
])
def test_natural_continuation_qualifiers_resolve_to_the_active_run(query):
    frame = compile_intent(query, run_reference="run-1")
    assert frame.operation_class == "CONTINUE"
    assert frame.continuation_reference == "run-1"


def test_imperative_work_request_is_not_projected_as_canonical_read():
    assert compile_intent("do a long multi-step task").read_explicit is False
    assert compile_intent("What am I working on?").read_explicit is True


def test_continuation_resolves_against_durable_run_without_executing():
    frame = compile_intent("go ahead", run_reference="run-1")
    assert frame.operation_class == "CONTINUE"
    resolved = resolve_continuation(frame, {"id": "run-1", "status": "awaiting_input", "continuation_state": {"pending_action_id": "action-1"}})
    assert resolved.status == "RESOLVED"
    assert resolved.run_reference == "run-1"
    assert resolved.action_reference == "action-1"
    assert resolved.phase == "AWAITING_INPUT"
    assert resolve_continuation(frame, {"id": "run-1", "status": "completed"}).status == "BLOCKED"


def test_continuation_derives_pending_action_phase_from_durable_actions():
    frame = compile_intent("continue", continuation=True, run_reference="run-2")
    resolved = resolve_continuation(frame, {
        "id": "run-2", "status": "running", "continuation_state": {},
        "actions": [{"id": "action-2", "status": "approved"}],
    })
    assert resolved.status == "RESOLVED"
    assert resolved.action_reference == "action-2"
    assert resolved.phase == "APPROVED"


def test_continuation_uses_canonical_durable_next_step_projection():
    frame = compile_intent("continue", continuation=True, run_reference="run-2")
    resolved = resolve_continuation(frame, {
        "id": "run-2", "status": "queued", "continuation_state": {}, "actions": [],
        "next_step": {
            "status": "READY",
            "action": {"id": "planned-action", "action_id": "service_status"},
            "reason": "next declared Action is valid",
        },
    })
    assert resolved.status == "RESOLVED"
    assert resolved.action_reference == "planned-action"
    assert resolved.phase == "READY"
    assert resolved.reason == "durable next Action is available"


def test_continuation_blocks_ambiguous_execution_even_when_run_is_running():
    frame = compile_intent("continue", continuation=True, run_reference="run-3")
    resolved = resolve_continuation(frame, {
        "id": "run-3", "status": "running",
        "continuation_state": {"execution_ambiguous": True, "pending_action_id": "action-3"},
    })
    assert resolved.status == "BLOCKED"
    assert resolved.phase == "EXECUTION_AMBIGUOUS"


def test_result_status_distinguishes_empty_from_failure():
    assert result_status({"status": "SUCCESS", "assets": []}) == "SUCCESS"
    assert result_status({"assets": []}) == "EMPTY_RESULT"
    assert result_status({"error": "CMDB unavailable"}) == "FAILED"
    assert result_status({"unavailable": True}) == "UNAVAILABLE"
    assert result_status({}) == "INVALID_RESULT"


def test_result_contract_validation_rejects_failure_shaped_or_unstructured_reads():
    frame = compile_intent("What IT assets do I have?")
    assert validate_result(frame, {"status": "EMPTY_RESULT", "assets": []}) == (True, "EMPTY_RESULT")
    assert validate_result(frame, {"error": "CMDB unavailable"}) == (False, "FAILED")
    assert validate_result(frame, {"status": "SUCCESS"}) == (False, "INVALID_RESULT")


def test_exposure_is_explicit_and_not_implied_for_automation():
    exposure = DOMAIN_CONTRACTS["TECHNICAL_ASSET"].exposures
    assert exposure["MODEL"] == "YES"
    assert exposure["WORK"] == "YES"
    assert exposure["AUTOMATION"] == "N/A"


@pytest.mark.parametrize("query", [
    "What do you remember about me?",
    "Show me what you remember about my work",
])
def test_memory_reads_compile_to_the_canonical_read_binding(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.contract.capability_id == "memory.read"
    assert resolved.action_id == "summarize_owner_memory"
    assert resolved.binding_name == "read_memory"
    assert resolved.action.approval.value == "none"


def test_work_reads_compile_to_the_canonical_read_binding():
    resolved = resolve_intent(compile_intent("What am I working on?"))
    assert resolved.available is True
    assert resolved.contract.capability_id == "work.read"
    assert resolved.action_id == "overview"
    assert resolved.binding_name == "read_work"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize(("query", "concept", "action_id"), [
    ("What goals do I have?", "GOAL", "list_goals"),
    ("What projects am I working on?", "PROJECT", "list_projects"),
    ("What tasks are open?", "TASK", "list_tasks"),
    ("What runs are active?", "RUN", "list_runs"),
    ("What commitments are open?", "COMMITMENT", "list_commitments"),
    ("What missions are active?", "MISSION", "list_missions"),
    ("What watches are active?", "WATCH", "list_watches"),
])
def test_work_subconcept_reads_resolve_to_first_class_canonical_actions(query, concept, action_id):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == concept
    assert resolved.frame.operation_class == "READ"
    assert resolved.contract.capability_id == "work.read"
    assert resolved.action_id == action_id
    assert resolved.binding_name == "read_work"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "What needs attention?",
    "What is Hades waiting on?",
    "Show pending approvals",
])
def test_attention_reads_use_the_canonical_owner_scoped_projection(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "WORK"
    assert resolved.frame.filters["view"] == "attention"
    assert resolved.contract.capability_id == "work.read"
    assert resolved.action_id == "attention"
    assert resolved.binding_name == "read_work"
    assert resolved.action.approval.value == "none"
    assert resolved.frame.workspace_hint == "work"


@pytest.mark.parametrize(("query", "concept", "action_id", "binding"), [
    ("What is the status of my homelab services?", "SERVICE", "service_status", "manage_homelab"),
    ("Inspect my homelab host", "HOMELAB_HOST", "inspect_host", "manage_homelab"),
    ("Show my security engagements", "SECURITY_ENGAGEMENT", "list_engagements", "manage_security_assessment"),
    ("Show my security evidence", "SECURITY_EVIDENCE", "list_evidence", "manage_security_assessment"),
    ("What research history do I have?", "RESEARCH", "list_cases", "manage_osint"),
])
def test_existing_domain_read_bindings_are_semantically_exposed(query, concept, action_id, binding):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == concept
    assert resolved.action_id == action_id
    assert resolved.binding_name == binding
    assert resolved.action.approval.value == "none"


def test_osint_reads_compile_to_the_existing_case_store_binding():
    resolved = resolve_intent(compile_intent("What investigations do I have?"))
    assert resolved.available is True
    assert resolved.contract.capability_id == "research.public_sources"
    assert resolved.action_id == "list_cases"
    assert resolved.binding_name == "manage_osint"
    assert resolved.action.approval.value == "none"


def test_household_reads_compile_to_the_canonical_read_binding():
    resolved = resolve_intent(compile_intent("What is in my pantry?"))
    assert resolved.available is True
    assert resolved.contract.capability_id == "household.read"
    assert resolved.action_id == "overview"
    assert resolved.binding_name == "read_household"
    assert resolved.action.approval.value == "none"


def test_setup_reads_compile_to_the_canonical_read_binding():
    resolved = resolve_intent(compile_intent("What is configured and connected?"))
    assert resolved.available is True
    assert resolved.contract.capability_id == "setup.read"
    assert resolved.action_id == "state"
    assert resolved.binding_name == "read_setup"
    assert resolved.action.approval.value == "none"


def test_generated_parity_rows_have_explicit_transport_applicability():
    rows = generated_parity_matrix()
    assert rows
    for row in rows:
        assert row["capability_id"] and row["action_id"] and row["result_contract"]
        assert set(row["exposure"]) == {"MODEL", "API", "WORK", "UI", "AUTOMATION"}
        assert all(value in {"YES", "NO", "N/A"} for value in row["exposure"].values())


@pytest.mark.parametrize("concept", sorted(DOMAIN_CONTRACTS))
def test_every_contract_read_has_a_canonical_projection_action(concept):
    """The loop's generic read projection cannot drift from contract metadata."""
    from src.agent_loop import _canonical_read_action

    contract = DOMAIN_CONTRACTS[concept]
    if "READ" not in contract.actions:
        pytest.skip(f"{concept} has no ordinary READ operation")
    assert _canonical_read_action(concept) == contract.actions["READ"]


def test_specialized_read_views_use_contract_operations():
    from src.agent_loop import _canonical_read_action

    assert _canonical_read_action("WORK", {"view": "attention"}) == DOMAIN_CONTRACTS["WORK"].actions["READ_ATTENTION"]
    assert _canonical_read_action("INTEGRATION", {"view": "integrations"}) == DOMAIN_CONTRACTS["INTEGRATION"].actions["READ_INTEGRATIONS"]
