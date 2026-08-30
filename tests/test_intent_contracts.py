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
    validate_bound_result,
    resolve_structured_reference,
    explicit_private_discovery_cidr,
    is_explicit_network_discovery_request,
    is_network_prerequisite_request,
    is_network_service_enumeration_request,
    network_discovery_request_cidr,
    explicitly_allows_diagnostic_install,
    network_substantive_fallback_command,
    is_explicit_continuation,
)
from src.aci import compile_turn_contract, is_contextual_reference_followup


def test_contract_registry_is_complete_for_registered_contracts():
    assert validate_contracts() == []


def test_contextual_reference_followup_uses_recent_semantic_context_only():
    messages = [
        {"role": "user", "content": "scan the current network"},
        {"role": "assistant", "content": "Discovery requires an authorized scope."},
        {"role": "user", "content": "what did that discovery find"},
    ]
    assert is_contextual_reference_followup(messages, messages[-1]["content"])
    assert not is_contextual_reference_followup(
        messages[:-1] + [{"role": "user", "content": "what is the weather?"}],
        "what is the weather?",
    )


def test_explicit_continuation_classifier_is_owned_by_intent_contracts():
    assert is_explicit_continuation("yes, please continue")
    assert is_explicit_continuation("the second one")
    assert is_explicit_continuation("all of them")
    assert not is_explicit_continuation("what is the current network?")


def test_turn_contract_keeps_explicit_continuation_out_of_retrieval_context():
    frame, _resolved, continuation, _domains = compile_turn_contract(
        {"continuation": False, "retrieval_query": "current date and time setup"},
        "Continue.",
        active_run=None,
    )
    assert frame.operation_class == "CONTINUE"
    assert continuation.status == "BLOCKED"


@pytest.mark.parametrize("text, expected", [
    ("scan 192.168.10.17/24", "192.168.10.0/24"),
    ("discover 10.20.30.0/25", "10.20.30.0/25"),
    ("scan 172.16.4.0/24", "172.16.4.0/24"),
    ("scan 8.8.8.0/24", None),
    ("scan 192.168.10.0/23", None),
    ("scan the current network", None),
])
def test_network_scope_projection_requires_explicit_bounded_private_cidr(text, expected):
    assert explicit_private_discovery_cidr(text) == expected
    assert network_discovery_request_cidr(text) == expected


def test_network_action_predicates_are_semantic_and_non_authorizing():
    assert is_network_prerequisite_request("install the tools needed for an nmap scan")
    assert is_explicit_network_discovery_request("discover hosts on my LAN")
    assert is_network_service_enumeration_request("enumerate services on discovered hosts")
    assert not is_explicit_network_discovery_request("what is a network scan?")
    assert not is_network_service_enumeration_request("show the network discovery status")


@pytest.mark.parametrize("text, expected", [
    ("install nmap", True),
    ("you may install nmap if needed", True),
    ("explain how to install nmap", False),
    ("scan the network without installing anything", False),
])
def test_diagnostic_install_projection_preserves_authority_boundary(text, expected):
    assert explicitly_allows_diagnostic_install(text) is expected


def test_network_fallback_projection_is_canonical_and_bounded():
    assert network_substantive_fallback_command(set(), "install nmap") == ""
    assert network_substantive_fallback_command({"network_ops"}, "install nmap") == (
        "python -m src.asset_inventory network-discover --install-authorized --record-observations"
    )
    assert "--install-authorized" not in network_substantive_fallback_command(
        {"network_ops"}, "explain how to install nmap"
    )


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


@pytest.mark.parametrize("query", [
    "Thanatos hardware",
    "tell me about the Thanatos machine",
    "what hardware is in Thanatos",
])
def test_named_asset_language_is_a_bounded_detail_candidate(query):
    frame = compile_intent(query)
    assert frame.domain_concept == "TECHNICAL_ASSET"
    assert frame.entity_reference == "Thanatos"
    assert frame.read_explicit is True
    assert resolve_intent(frame).action_id == "get"


def test_inventory_state_is_a_canonical_asset_read_but_household_inventory_is_not():
    frame = compile_intent("What is the inventory state?")
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "TECHNICAL_ASSET"
    assert resolved.action_id == "list"
    assert resolved.binding_name == "manage_assets"

    household = compile_intent("What is my pantry inventory?")
    assert household.domain_concept == "HOUSEHOLD_ITEM"


@pytest.mark.parametrize("query", [
    "look up summary in my technical asset state",
    "show my technical asset list information",
    "what is the current search for my technical asset",
])
def test_asset_collection_view_nouns_are_not_misread_as_asset_targets(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "TECHNICAL_ASSET"
    assert frame.entity_reference is None
    assert resolved.action_id == "list"


@pytest.mark.parametrize("query", [
    "which machines have GPUs",
    "search my assets for GPU",
    "how much RAM do my AI nodes have",
    "how many 2080s do I have",
])
def test_owner_asset_property_queries_use_collection_read_contract(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "TECHNICAL_ASSET"
    assert frame.entity_reference is None
    assert frame.filters.get("asset_property") in {"gpu", "ram", None}
    assert resolved.action_id == "list"


def test_conceptual_component_question_does_not_become_asset_read():
    frame = compile_intent("What is a GPU?")
    assert frame.domain_concept == "UNKNOWN"
    assert frame.operation_class == "ANSWER"
    assert resolve_intent(frame).available is False


@pytest.mark.parametrize("query", [
    "Show me what's in the kitchen.",
    "Add angel hair pasta to my kitchen inventory.",
    "What do you know about me?",
    "Actually, that is not true anymore.",
    "What work is outstanding?",
    "What projects do I have?",
    "What tasks are open?",
])
def test_owner_read_or_mutation_enters_bounded_aci_capability_path(query):
    from src.intent_contracts import is_bounded_owner_capability_turn

    assert is_bounded_owner_capability_turn(compile_intent(query)) is True


def test_structured_reference_followup_enters_bounded_aci_path_without_domain_noun():
    from src.intent_contracts import is_bounded_owner_capability_turn

    frame = compile_intent("Actually I meant the first one.")

    assert frame.domain_concept == "UNKNOWN"
    assert frame.reference_resolution["status"] == "UNRESOLVED"
    assert is_bounded_owner_capability_turn(frame) is True


def test_asset_property_followup_beats_generic_continuation():
    context = {
        "ordered_entities": [
            {"ref": "atlas", "concept": "TECHNICAL_ASSET"},
            {"ref": "erebus", "concept": "TECHNICAL_ASSET"},
        ],
        "last": {"ref": "atlas", "concept": "TECHNICAL_ASSET"},
    }
    frame = compile_intent(
        "And what RAM does that one have?",
        continuation=True,
        reference_context=context,
    )

    assert frame.operation_class == "READ"
    assert frame.domain_concept == "TECHNICAL_ASSET"
    assert frame.entity_reference == "atlas"
    assert frame.filters["asset_property"] == "ram"


@pytest.mark.parametrize(("query", "action"), [
    ("Add this server to my IT asset inventory.", "add"),
    ("Update Thanatos in my asset inventory.", "update"),
])
def test_explicit_asset_writes_resolve_existing_canonical_actions(query, action):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.action_id == action
    assert resolved.binding_name == "manage_assets"
    assert resolved.contract.capability_id == "inventory.manage"


def test_general_household_explanation_never_resolves_to_mutation():
    from src.intent_contracts import is_bounded_owner_capability_turn

    frame = compile_intent("What is the difference between a pantry and a kitchen?")
    assert is_bounded_owner_capability_turn(frame) is True
    assert resolve_intent(frame).action_id == "overview"
    assert resolve_intent(frame).contract.capability_id == "household.read"


@pytest.mark.parametrize("query", [
    "What is memory?",
    "What is work management?",
])
def test_conceptual_memory_and_work_questions_do_not_enter_owner_capability_path(query):
    from src.intent_contracts import is_bounded_owner_capability_turn

    assert is_bounded_owner_capability_turn(compile_intent(query)) is False


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


def test_continuation_rejects_terminal_lifecycle_even_if_status_is_stale():
    frame = compile_intent("Continue", continuation=True, run_reference="run-1")
    resolution = resolve_continuation(frame, {
        "id": "run-1", "status": "running", "lifecycle_state": "succeeded",
    })
    assert resolution.status == "BLOCKED"
    assert resolution.phase == "TERMINAL"


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


def test_registered_result_validation_uses_binding_and_action_contract():
    assert validate_bound_result(
        "manage_homelab", "read_network_observations",
        {"status": "SUCCESS", "nodes": [], "edges": []},
    ) == (True, "SUCCESS")
    assert validate_bound_result(
        "manage_homelab", "read_network_observations",
        {"status": "SUCCESS", "hosts": []},
    ) == (False, "INVALID_RESULT")


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


def test_ordinal_reference_keeps_canonical_asset_identity_over_lexical_about_fragment():
    frame = compile_intent(
        "Tell me about the first physical one",
        reference_context={"entities": [{"ref": "asset:strong-1", "concept": "TECHNICAL_ASSET"}]},
    )
    assert frame.domain_concept == "TECHNICAL_ASSET"
    assert frame.entity_reference == "asset:strong-1"


def test_ordinal_reference_uses_ordered_eligible_result_set_over_mixed_chat_refs():
    context = {
        "entities": [
            {"ref": "service:recent", "concept": "SERVICE"},
            {"ref": "asset:second", "concept": "TECHNICAL_ASSET"},
        ],
        "ordered_entities": [
            {"ref": "asset:first", "concept": "TECHNICAL_ASSET", "eligible": True},
            {"ref": "asset:second", "concept": "TECHNICAL_ASSET", "eligible": True},
            {"ref": "asset:hidden", "concept": "TECHNICAL_ASSET", "eligible": False},
        ],
        "last": {"ref": "service:recent", "concept": "SERVICE"},
    }
    resolution = resolve_structured_reference("tell me about the first physical one", context)
    assert resolution["status"] == "RESOLVED"
    assert resolution["refs"] == ["asset:first"]
    assert resolution["concept"] == "TECHNICAL_ASSET"


def test_last_reference_is_fallback_only_when_no_ordered_result_exists():
    resolution = resolve_structured_reference("tell me about that one", {
        "ordered_entities": [],
        "last": {"ref": "asset:last", "concept": "TECHNICAL_ASSET"},
    })
    assert resolution["status"] == "RESOLVED"
    assert resolution["refs"] == ["asset:last"]


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


def test_default_work_overview_is_canonical_and_approval_free():
    frame = compile_intent("What am I working on?")
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "WORK"
    assert resolved.action_id == "overview"
    assert resolved.binding_name == "read_work"
    assert resolved.action.approval.value == "none"


def test_current_network_context_is_typed_and_approval_free():
    frame = compile_intent("What network am I currently connected to?")
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "NETWORK"
    assert frame.filters["view"] == "context"
    assert resolved.action_id == "read_network_context"
    assert resolved.action.approval.value == "none"


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


@pytest.mark.parametrize("query", ["Show my contacts", "List my address book"])
def test_contact_reads_resolve_to_existing_communications_binding(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "CONTACT"
    assert resolved.action_id == "contacts"
    assert resolved.binding_name == "read_communications"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize(
    ("binding", "action", "payload"),
    [
        ("read_work", "list_tasks", {"status": "SUCCESS"}),
        ("manage_osint", "list_cases", {"status": "SUCCESS", "cases": "not-a-list"}),
        ("read_communications", "overview", {"status": "SUCCESS", "calendar": {}}),
    ],
)
def test_registered_collection_reads_reject_missing_or_malformed_shapes(binding, action, payload):
    valid, reason = validate_bound_result(binding, action, payload)
    assert valid is False
    assert reason == "INVALID_RESULT"


def test_registered_collection_read_accepts_empty_typed_collection():
    valid, reason = validate_bound_result(
        "read_work", "list_tasks", {"status": "SUCCESS_EMPTY", "tasks": []},
    )
    assert valid is True
    assert reason == "SUCCESS_EMPTY"


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


@pytest.mark.parametrize("query", [
    "Inspect remote host Thanatos over SSH",
    "check the remote server Morpheus via ssh",
    "what is running on remote machine atlas",
])
def test_remote_host_reads_project_to_asset_bound_ssh_action(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "HOMELAB_HOST"
    assert resolved.frame.filters["remote"] is True
    assert resolved.frame.target in {"Thanatos", "Morpheus", "atlas"}
    assert resolved.action_id == "remote_host_inspect"
    assert resolved.binding_name == "manage_homelab"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "Restart nginx service",
    "Recover postgres service",
])
def test_qualified_service_restart_language_resolves_to_safe_canonical_preflight(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "SERVICE"
    assert resolved.frame.operation_class == "EXECUTE"
    assert resolved.action_id == "plan_service_restart"
    assert resolved.binding_name == "manage_homelab"
    assert resolved.action.approval.value == "none"
    assert resolved.action.effects == ("read_private",)


@pytest.mark.parametrize("query", [
    "Restart the registered service",
    "Restart the service",
    "Restart it.",
    "Please recover that!",
])
def test_unqualified_service_restart_requires_target_clarification(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.frame.domain_concept == "SERVICE"
    assert resolved.frame.operation_class == "EXECUTE"
    assert resolved.available is False
    assert resolved.reason == "target_required"


@pytest.mark.parametrize(("query", "constraint"), [
    ("Merge these devices by IP", "strong_identity_required"),
    ("Scan a public range", "public_scope_requires_authorization"),
    ("Approve the changed action", "action_revalidation_required"),
])
def test_security_boundary_constraints_are_framework_resolvable(query, constraint):
    frame = compile_intent(query)
    assert constraint in frame.constraints


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


@pytest.mark.parametrize(
    ("query", "concept", "binding", "action"),
    [
        ("What is the newest NVIDIA driver?", "WEB_EVIDENCE", "web_search", "search"),
        ("Look this up online: example.org", "WEB_EVIDENCE", "web_search", "search"),
        ("Fetch https://example.org/status", "WEB_URL", "web_fetch", "fetch"),
    ],
)
def test_external_evidence_uses_canonical_web_capability_without_manual_mode(
    query, concept, binding, action,
):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == concept
    assert frame.operation_class == "READ"
    assert frame.read_explicit is True
    assert resolved.available is True
    assert resolved.binding_name == binding
    assert resolved.action_id == action


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
    from src.intent_contracts import canonical_read_action

    contract = DOMAIN_CONTRACTS[concept]
    if "READ" not in contract.actions:
        pytest.skip(f"{concept} has no ordinary READ operation")
    assert canonical_read_action(concept) == contract.actions["READ"]


def test_specialized_read_views_use_contract_operations():
    from src.intent_contracts import canonical_read_action

    assert canonical_read_action("WORK", {"view": "attention"}) == DOMAIN_CONTRACTS["WORK"].actions["READ_ATTENTION"]
    assert canonical_read_action("INTEGRATION", {"view": "integrations"}) == DOMAIN_CONTRACTS["INTEGRATION"].actions["READ_INTEGRATIONS"]
