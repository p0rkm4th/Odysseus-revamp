import calendar
from datetime import date

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
from src.aci import is_contextual_reference_followup


def test_contract_registry_is_complete_for_registered_contracts():
    assert validate_contracts() == []


@pytest.mark.parametrize(("query", "view", "action"), [
    ("What can I make with what we have?", "available", "recipe_suggest"),
    ("Show me recipes where I am only missing one or two things.", "few_shortages", "recipe_suggest"),
])
def test_recipe_availability_questions_use_canonical_stock_planning(query, view, action):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "RECIPE"
    assert frame.filters["view"] == view
    assert resolved.available is True
    assert resolved.action_id == action


def test_recipe_availability_payload_is_bounded_and_read_only():
    from src.aci import canonical_read_fast_path_payload

    query = "Show me recipes where I am only missing one or two things."
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    payload = canonical_read_fast_path_payload(
        resolved.binding_name, resolved.action_id, frame.as_dict(), query=query,
    )
    assert payload == {"action": "recipe_suggest", "max_shortages": 2, "limit": 20}


@pytest.mark.parametrize(("query", "view", "action"), [
    ("How much have I spent this month?", "spending", "spending"),
    ("How much money for this month specifically did I spend?", "spending", "spending"),
    ("What have I spent on restaurants lately?", "spending", "spending"),
    ("What's my inflow and outflow since the first?", "cash_flow", "cash_flow"),
    ("Show me my recent transactions.", "transactions", "transactions"),
    ("Is my financial data up to date?", "coverage", "coverage"),
])
def test_finance_read_view_is_preserved_by_canonical_resolution(query, view, action):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "FINANCE"
    assert frame.filters.get("view") == view
    assert resolved.available is True
    assert resolved.action_id == action


@pytest.mark.parametrize("query", [
    "Go over my finances for me.",
    "Check the CSV for my finances.",
    "It's in my financial CSV that was uploaded earlier.",
])
def test_finance_file_and_overview_language_enters_canonical_read_path(query):
    frame = compile_intent(query)
    assert frame.domain_concept == "FINANCE"
    assert resolve_intent(frame).available is True


def test_broad_finance_year_request_uses_spending_overview_not_coverage_only():
    frame = compile_intent("Show me all my finances for the year")
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "spending"
    assert frame.filters["start"].endswith("-01-01")


def test_finance_walk_through_uses_bounded_spending_overview():
    frame = compile_intent("Walk me through my finances from the last 3 months")
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "spending"
    today = date.today()
    month_index = today.year * 12 + today.month - 1 - 3
    year, month_zero = divmod(month_index, 12)
    expected_day = min(today.day, calendar.monthrange(year, month_zero + 1)[1])
    assert frame.filters["start"] == date(year, month_zero + 1, expected_day).isoformat()
    assert frame.filters["end"] == today.isoformat()
    assert "merchant" not in frame.filters


def test_finance_insight_question_uses_bounded_spending_overview():
    frame = compile_intent("What stands out in my finances this year?")
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "spending"


def test_finance_walkme_transcription_typo_stays_on_canonical_read_path():
    frame = compile_intent("Walkme through my past 4 months of finances")
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "spending"
    today = date.today()
    month_index = today.year * 12 + today.month - 1 - 4
    year, month_zero = divmod(month_index, 12)
    expected_day = min(today.day, calendar.monthrange(year, month_zero + 1)[1])
    assert frame.filters["start"] == date(year, month_zero + 1, expected_day).isoformat()
    assert frame.filters["end"] == today.isoformat()


def test_paycheck_question_uses_bounded_posted_inflow_transactions():
    from src.aci import canonical_read_fast_path_payload

    query = "Where's my paychecks?"
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "transactions"
    assert frame.filters["category"] == "Paycheck"
    assert frame.filters["direction"] == "inflow"
    assert frame.filters["status"] == "posted"
    payload = canonical_read_fast_path_payload(resolved.binding_name, resolved.action_id, frame.as_dict(), query=query)
    assert payload["category"] == "Paycheck"
    assert payload["direction"] == "inflow"
    assert payload["status"] == "posted"


def test_paid_question_with_transcription_spacing_uses_bounded_paycheck_read():
    query = "Howmuch have i been paid over the past 5 months?"
    frame = compile_intent(query)
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "transactions"
    assert frame.filters["category"] == "Paycheck"
    assert frame.filters["direction"] == "inflow"
    assert frame.filters["status"] == "posted"



def test_finance_merchant_selector_reaches_deterministic_spending_payload():
    from src.aci import canonical_read_fast_path_payload

    frame = compile_intent("How much did I spend this month at Publix?")
    resolved = resolve_intent(frame)
    assert frame.filters["view"] == "spending"
    assert frame.filters["merchant"] == "publix"
    payload = canonical_read_fast_path_payload(
        resolved.binding_name, resolved.action_id, frame.as_dict(),
        query="How much did I spend this month at Publix?",
    )
    assert payload["action"] == "spending"
    assert payload["merchant"] == "publix"
    assert payload["start"].endswith("-09-01")
    assert payload["end"]


def test_finance_category_selector_preserves_category_and_year_range():
    from src.aci import canonical_read_fast_path_payload

    query = "How much did I spend on insurance this year?"
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "spending"
    assert frame.filters["category"] == "insurance"
    assert frame.filters["start"].endswith("-01-01")
    payload = canonical_read_fast_path_payload(
        resolved.binding_name, resolved.action_id, frame.as_dict(), query=query,
    )
    assert payload["category"] == "insurance"
    assert payload["start"].endswith("-01-01")


def test_explicit_finance_calendar_year_is_not_reduced_to_current_month():
    query = "What was my spending in 2026?"
    frame = compile_intent(query)
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "spending"
    assert frame.filters["start"] == "2026-01-01"
    assert frame.filters["end"] == "2026-12-31"


def test_ranked_finance_read_is_bounded_to_posted_outflows():
    from src.aci import canonical_read_fast_path_payload

    query = "What was my most expensive purchase this year?"
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    payload = canonical_read_fast_path_payload(resolved.binding_name, resolved.action_id, frame.as_dict(), query=query)
    assert payload["action"] == "transactions"
    assert payload["status"] == "posted"
    assert payload["direction"] == "outflow"
    assert "category" not in payload


def test_concise_merchant_spending_question_is_not_unfiltered():
    from src.aci import canonical_read_fast_path_payload

    frame = compile_intent("How much at Publix?")
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "FINANCE"
    assert frame.filters == {"view": "spending", "merchant": "publix"}
    assert canonical_read_fast_path_payload(
        resolved.binding_name, resolved.action_id, frame.as_dict(),
        query="How much at Publix?",
    ) == {"action": "spending", "merchant": "publix"}


def test_merchant_selector_stops_before_natural_month_phrase():
    frame = compile_intent("How much did I spend at Publix in September?")
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "spending"
    assert frame.filters["merchant"] == "publix"
    assert frame.filters["start"].endswith("-09-01")
    assert frame.filters["end"].endswith("-09-30")


def test_named_month_range_reaches_finance_fast_path_payload():
    from src.aci import canonical_read_fast_path_payload

    query = "How much did I spend at Publix in September?"
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    payload = canonical_read_fast_path_payload(
        resolved.binding_name, resolved.action_id, frame.as_dict(), query=query,
    )
    assert payload["merchant"] == "publix"
    assert payload["start"].endswith("-09-01")
    assert payload["end"].endswith("-09-30")


def test_month_after_spending_for_is_a_date_not_a_category():
    frame = compile_intent("Show my posted spending for September")
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "spending"
    assert "category" not in frame.filters
    assert frame.filters["start"].endswith("-09-01")
    assert frame.filters["end"].endswith("-09-30")


def test_relative_year_range_does_not_default_to_current_month():
    frame = compile_intent("How much did I spend dining out this year?")
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["start"].endswith("-01-01")
    assert frame.filters["end"]


def test_year_phrase_with_for_the_year_reaches_full_year_range():
    frame = compile_intent("Show me all my finances for the year")
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["start"].endswith("-01-01")
    assert frame.filters["end"]


def test_relative_multi_month_range_does_not_default_to_current_month():
    frame = compile_intent("How much did I spend dining out in the past 6 months?")
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["view"] == "spending"
    assert frame.filters["category"] == "dining_out"
    assert frame.filters["start"] != date.today().replace(day=1).isoformat()
    assert frame.filters["end"] == date.today().isoformat()


def test_month_count_correction_reuses_finance_context():
    from src.agent_loop import _classify_agent_request

    messages = [
        {"role": "user", "content": "How much have I spent dining out in the past 6 months?"},
        {"role": "assistant", "content": "Posted spending for September."},
    ]
    projection = _classify_agent_request(messages, "Six months, not September")
    assert projection is not None
    frame = compile_intent(projection["retrieval_query"], continuation=projection["continuation"])
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["start"] != date.today().replace(day=1).isoformat()
    assert frame.filters["category"] == "dining_out"


def test_short_finance_period_correction_reaches_bounded_read():
    from src.agent_loop import _classify_agent_request

    messages = [
        {"role": "user", "content": "How much did I spend dining out this year?"},
        {"role": "assistant", "content": "Posted spending for September."},
    ]
    projection = _classify_agent_request(messages, "This year, not month")
    frame = compile_intent(
        projection["retrieval_query"],
        continuation=projection["continuation"],
    )
    assert projection["continuation"] is False
    assert frame.domain_concept == "FINANCE"
    assert frame.filters["start"].endswith("-01-01")


def test_dining_out_and_restaurant_filters_are_explicit():
    dining = compile_intent("How much did I spend dining out this year?")
    restaurants = compile_intent("What have I spent on restaurants lately?")
    assert dining.filters["category"] == "dining_out"
    assert restaurants.filters["category"] == "Restaurants"


def test_grocery_removal_resolves_to_owner_scoped_unqueue_action():
    frame = compile_intent("Remove rice from my grocery list.")
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "HOUSEHOLD_ITEM"
    assert frame.operation_class == "DELETE"
    assert resolved.available is True
    assert resolved.action_id == "remove_from_grocery"


@pytest.mark.parametrize("query", [
    "Clear my grocery list.",
    "Empty the shopping list.",
    "Delete everything on the grocery list.",
])
def test_grocery_clear_is_a_bounded_set_unqueue_action(query):
    from src.aci import canonical_inventory_mutation_payload

    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    payload = canonical_inventory_mutation_payload(resolved.action_id, query)
    assert frame.domain_concept == "HOUSEHOLD_ITEM"
    assert frame.operation_class == "DELETE"
    assert resolved.action_id == "remove_from_grocery"
    assert payload == {
        "action": "remove_from_grocery",
        "clear": True,
        "list_name": "grocery",
        "domain": "kitchen",
        "idempotency_key": payload["idempotency_key"],
    }


@pytest.mark.parametrize("query", [
    "What recipes do I have?",
    "Show my saved recipes.",
    "What cooking recipes do we have?",
])
def test_saved_recipe_questions_use_the_canonical_recipe_collection(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "RECIPE"
    assert frame.read_explicit is True
    assert resolved.binding_name == "manage_assets"
    assert resolved.action_id == "recipe_list"


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


def test_port_scan_language_resolves_to_bounded_service_enumeration():
    frame = compile_intent("Check my network for open ports on the responding devices")
    resolved = resolve_intent(frame)
    assert frame.operation_class == "EXECUTE"
    assert frame.filters["view"] == "service_enumeration"
    assert resolved.action_id == "plan_network_service_enumeration"
    assert resolved.binding_name == "manage_homelab"


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


@pytest.mark.parametrize(("query", "operation", "action"), [
    ("Add rice to my grocery list.", "CREATE", "add_item"),
    ("I bought two 1-kilogram bags of rice; put them in the pantry.", "UPDATE", "add_stock"),
    ("Use 500 grams of rice.", "EXECUTE", "consume_stock"),
])
def test_natural_grocery_and_pantry_stock_language_uses_inventory_actions(query, operation, action):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "HOUSEHOLD_ITEM"
    assert frame.operation_class == operation
    assert resolved.available is True
    assert resolved.contract.capability_id == "inventory.manage"
    assert resolved.binding_name == "manage_assets"
    assert resolved.action_id == action


def test_explicit_multi_item_grocery_request_is_grounded_as_individual_items():
    from src.aci import canonical_inventory_mutation_payload

    payload = canonical_inventory_mutation_payload(
        "add_item", "add rice, milk, and eggs to my shopping list"
    )
    assert payload is not None
    assert payload["items"] == ["rice", "milk", "eggs"]
    assert "name" not in payload

    named_item = canonical_inventory_mutation_payload(
        "add_item", "add macaroni and cheese to my shopping list"
    )
    assert named_item["name"] == "macaroni and cheese"


def test_singular_grocery_read_uses_the_canonical_household_path():
    frame = compile_intent("Show my grocery list.")
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "HOUSEHOLD_ITEM"
    assert frame.operation_class == "READ"
    assert resolved.available is True
    assert resolved.contract.capability_id == "household.read"
    assert resolved.binding_name == "read_household"


def test_natural_shared_fridge_question_reaches_canonical_inventory_read():
    frame = compile_intent("What do we have in the shared fridge right now?")
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "HOUSEHOLD_ITEM"
    assert frame.filters["list_name"] == "fridge"
    assert resolved.available is True
    assert resolved.binding_name == "read_household"


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
    "What's on the house grocery list?",
    "Dude, check my grocery list and don't fail me now",
    "Add angel hair pasta to my kitchen inventory.",
])
def test_household_owner_turn_enters_bounded_aci_capability_path(query):
    from src.intent_contracts import is_bounded_owner_capability_turn

    assert is_bounded_owner_capability_turn(compile_intent(query)) is True


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


def test_pantry_stock_addition_requires_a_bounded_quantity():
    missing = compile_intent("Add shared dogfood salt to the pantry.")
    supplied = compile_intent("Add 500 g of shared dogfood salt to the pantry.")
    assert "inventory_quantity_required" in missing.constraints
    assert "inventory_quantity_required" not in supplied.constraints


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
