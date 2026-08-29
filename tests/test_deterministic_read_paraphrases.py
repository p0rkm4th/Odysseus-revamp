import pytest

from benchmarks.hades_aci_metamorphic import (
    DETERMINISTIC_READ_MUST_NOT,
    DETERMINISTIC_READ_TRAJECTORY,
    NEGATIVE_NEAR_MISSES,
    READ_PARAPHRASE_SETS,
)
from src.agent_loop import _classify_agent_request
from src.aci import (
    canonical_asset_read_payload,
    canonical_read_fast_path_payload,
    compile_turn_contract,
    minimal_aci_answer_messages,
    matches_resolved_canonical_read,
    prefetched_explicit_memory_result,
    provisional_intent_projection,
)
from src.context_compactor import strip_agent_injected_messages as _strip_agent_injected_messages
from src.deterministic_reads import deterministic_read_concept
from src.intent_contracts import canonical_read_action, compile_intent, inventory_add_item_payload, inventory_consume_stock_payload, recipe_create_draft, recipe_create_payload, recipe_requested_name, resolve_intent
from src.memory_grounding import is_explicit_memory_query
from src.tool_parsing import ToolBlock


def test_asset_detail_followups_resolve_active_referent_and_property():
    context = {
        "ordered_entities": [
            {"ref": "asset-1", "concept": "TECHNICAL_ASSET"},
            {"ref": "asset-2", "concept": "TECHNICAL_ASSET"},
        ],
        "last": {"ref": "asset-1", "concept": "TECHNICAL_ASSET"},
    }
    for query, ref, prop in (
        ("Tell me the specs.", "asset-1", "specs"),
        ("What GPUs does it have?", "asset-1", "gpu"),
        ("What about its RAM?", "asset-1", "ram"),
        ("Tell me about the other one.", "asset-2", None),
    ):
        frame = compile_intent(query, reference_context=context)
        assert frame.domain_concept == "TECHNICAL_ASSET"
        assert frame.entity_reference == ref
        assert frame.operation_class == "READ"
        if prop:
            assert frame.filters["asset_property"] == prop


def test_asset_property_and_model_filter_payloads_are_canonical():
    property_frame = compile_intent("How much RAM do my computers have?")
    assert deterministic_read_concept("How much RAM do my computers have?") == "TECHNICAL_ASSET"
    assert property_frame.read_explicit is True
    assert canonical_read_fast_path_payload("manage_assets", "list", property_frame.as_dict()) == {
        "action": "list", "asset_property": "ram", "result_projection": "property",
    }
    filter_frame = compile_intent("Which of my servers has an RTX 4090?")
    assert canonical_read_fast_path_payload("manage_assets", "list", filter_frame.as_dict()) == {
        "action": "list", "query": "rtx 4090", "result_projection": "filter",
    }


def test_asset_detail_followup_without_context_is_unresolved():
    frame = compile_intent("Tell me the specs.", reference_context=None)
    assert frame.domain_concept == "UNKNOWN"
    assert frame.entity_reference is None
    assert frame.filters == {}


@pytest.mark.parametrize("query", [
    "what do you know about me",
    "tell me about my memory",
    "what's in memory",
    "tell me about my hardware",
])
def test_canonical_memory_questions_are_not_asset_references(query):
    frame = compile_intent(query, reference_context=None)
    assert frame.reference_resolution["status"] == "NOT_REFERENCE"
    assert frame.entity_reference is None


@pytest.mark.parametrize(("query", "concept", "action", "binding"), [
    ("tell me about my hardware", "TECHNICAL_ASSET", "list", "manage_assets"),
    ("Please explore my current hardware", "HOMELAB_HOST", "inspect_host", "manage_homelab"),
    ("i need you to like, scan your hardware", "HOMELAB_HOST", "inspect_host", "manage_homelab"),
])
def test_hardware_language_selects_asset_or_host_from_semantic_scope(query, concept, action, binding):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.frame.domain_concept == concept
    assert resolved.frame.operation_class == "READ"
    assert resolved.action_id == action
    assert resolved.binding_name == binding
    assert resolved.action.approval.value == "none"
    assert resolved.frame.target is None


def test_owner_technical_asset_language_is_not_a_host_identifier():
    for query in (
        "tell me about my tech",
        "what about mah hardware? what kinda computational assets do i have?",
    ):
        frame = compile_intent(query)
        assert frame.domain_concept == "TECHNICAL_ASSET"
        assert frame.target is None
        assert resolve_intent(frame).action_id == "list"


def test_it_assets_collection_read_does_not_consume_active_asset_referent():
    context = {
        "ordered_entities": [
            {"ref": "asset-1", "concept": "TECHNICAL_ASSET"},
            {"ref": "asset-2", "concept": "TECHNICAL_ASSET"},
        ],
        "last": {"ref": "asset-1", "concept": "TECHNICAL_ASSET"},
    }
    frame = compile_intent("what it assets do we have", reference_context=context)
    resolved = resolve_intent(frame)
    assert frame.reference_resolution["status"] == "NOT_REFERENCE"
    assert frame.entity_reference is None
    assert resolved.action_id == "list"
    assert resolved.binding_name == "manage_assets"


@pytest.mark.parametrize("query", [
    "what's in the kitchen",
    "what's in the freezer",
    "how much milk do we have",
    "how many cans do we have",
    "what is about to expire",
    "what are we low on",
    "what did we run out of",
])
def test_household_inventory_variants_use_canonical_read_owner(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.frame.domain_concept == "HOUSEHOLD_ITEM"
    assert resolved.frame.operation_class == "READ"
    assert resolved.action_id == "overview"
    assert resolved.binding_name == "read_household"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "what is running on Erebus",
    "what services are down",
    "what's running in the homelab",
])
def test_infrastructure_status_variants_use_canonical_service_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.frame.domain_concept == "SERVICE"
    assert resolved.frame.operation_class == "READ"
    assert resolved.action_id == "service_status"
    assert resolved.binding_name == "manage_homelab"


@pytest.mark.parametrize("query", [
    "what recipes do i have",
    "show my recipes",
    "find recipe chili",
])
def test_recipe_inventory_queries_use_existing_inventory_service_owner(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.frame.domain_concept == "RECIPE"
    assert resolved.frame.operation_class == "READ"
    assert resolved.action_id in {"list", "search"}
    assert resolved.binding_name == "read_recipes"


def test_recipe_search_keeps_only_bounded_query_text():
    frame = compile_intent("find recipe chili")
    assert frame.filters["recipe_query"] == "chili"
    assert resolve_intent(frame).action_id == "search"


def test_explicit_recipe_create_projects_structured_draft_into_canonical_action():
    query = (
        "Add this recipe to my recipes: Acceptance Chicken and Rice. "
        "Ingredients: 2 chicken breasts, 1 cup rice. "
        "Instructions: Bake the chicken and cook the rice."
    )
    draft = recipe_create_payload(query)
    assert draft["action"] == "add"
    assert draft["name"] == "Acceptance Chicken and Rice"
    assert [(row["name"], row["quantity"], row["unit"]) for row in draft["ingredients"]] == [
        ("chicken breasts", 2.0, "each"), ("rice", 1.0, "cup")
    ]
    assert "Bake the chicken" in draft["instructions"]


def test_incomplete_recipe_create_draft_fails_closed():
    assert recipe_create_payload("Add a recipe called Dinner") is None


def test_url_recipe_create_preserves_import_and_explicit_name_metadata():
    query = ('Add this recipe to my recipe book, for the name, use '
             '"Chicken Cordon Bleu with Cheese Sauce": '
             'https://sundaysuppermovement.com/best-chicken-cordon-bleu-recipe/#recipe')
    frame = compile_intent(query)
    assert frame.domain_concept == "RECIPE"
    assert frame.operation_class == "CREATE"
    assert frame.filters["recipe_import"] is True
    assert frame.filters["recipe_requested_name"] == "Chicken Cordon Bleu with Cheese Sauce"
    assert recipe_requested_name(query) == "Chicken Cordon Bleu with Cheese Sauce"
    resolved = resolve_intent(frame)
    assert resolved.action_id == "commit_import"
    assert resolved.binding_name == "manage_recipes"


def test_long_owner_recipe_paste_projects_a_validated_draft_into_add_action():
    query = '''Add the following to my recipes as "Easy Chicken Cordon Bleu w/ Cheese Sauce":

Ingredients:
- 2 chicken breasts
- 1 cup breadcrumbs
- 4 slices ham
- 4 slices Swiss cheese
- 2 tablespoons butter

Instructions:
1. Pound chicken breasts thin.
2. Layer ham and cheese, roll, and secure.
3. Coat with breadcrumbs and bake at 375F for 30 minutes.
4. Make the cheese sauce and serve.'''
    draft = recipe_create_draft(query)
    assert draft is not None
    assert draft.name == "Easy Chicken Cordon Bleu w/ Cheese Sauce"
    assert draft.servings == 1
    assert len(draft.ingredients) == 5
    assert draft.ingredients[1]["unit"] == "cup"
    assert "Make the cheese sauce" in draft.instructions
    assert recipe_create_payload(query)["action"] == "add"


def test_recipe_draft_rejects_missing_or_ambiguous_sections_without_mutation():
    assert recipe_create_draft(
        'Add the following to my recipes as "Dinner": Ingredients: chicken. Instructions: cook it.'
    ) is None
    assert recipe_create_draft(
        'Add this recipe to my recipes: Dinner. Ingredients:\n- chicken\n\nInstructions:\nCook it.'
    ) is None


def test_household_quantity_add_projects_item_and_initial_stock():
    query = "Add 3 synthetic cans of Acceptance Tomatoes to the pantry."
    frame = compile_intent(query)
    assert resolve_intent(frame).action_id == "add_item"
    assert inventory_add_item_payload(query) == {
        "action": "add_item", "name": "Acceptance Tomatoes", "domain": "kitchen",
        "item_kind": "ingredient", "default_unit": "each",
        "initial_quantity": 3.0, "initial_unit": "each", "category": "pantry",
    }


@pytest.mark.parametrize("query", ["Use one Acceptance Tomato.", "consume 1 Acceptance Tomatoes"])
def test_household_consumption_promotes_to_canonical_update_action(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "HOUSEHOLD_ITEM"
    assert frame.operation_class == "EXECUTE"
    assert resolved.action_id == "consume_stock"
    assert resolved.binding_name == "manage_assets"
    assert inventory_consume_stock_payload(query)["quantity"] == 1.0


def test_expiring_recipe_composition_uses_distinct_canonical_action():
    frame = compile_intent("what recipes can i make with ingredients expiring soon")
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "RECIPE"
    assert frame.filters["recipe_expiring"] is True
    assert resolved.action_id == "expiring_candidates"
    assert resolved.binding_name == "read_recipes"


@pytest.mark.parametrize("query", [
    "can I make this recipe with what I have",
    "do I have everything for this meal",
    "check missing ingredients for the chili recipe",
])
def test_recipe_pantry_coverage_has_distinct_canonical_result_contract(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "RECIPE"
    assert frame.filters["recipe_coverage"] is True
    assert resolved.action_id == "can_make"
    assert resolved.binding_name == "read_recipes"


def test_recipe_scale_followup_preserves_recipe_reference_and_serving_target():
    context = {
        "ordered_entities": [{"ref": "recipe-1", "concept": "RECIPE"}],
        "last": {"ref": "recipe-1", "concept": "RECIPE"},
    }
    frame = compile_intent("scale this recipe to six servings", reference_context=context)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "RECIPE"
    assert frame.entity_reference == "recipe-1"
    assert frame.filters == {"recipe_scale": True, "servings": "6"}
    assert resolved.action_id == "scale"


def test_contextual_followup_cue_does_not_demote_substantive_recipe_read():
    messages = [
        {"role": "user", "content": "what recipes do i have"},
        {"role": "assistant", "content": "Which recipe would you like?"},
        {"role": "user", "content": "scale this recipe to six servings"},
    ]
    projection, owned = provisional_intent_projection(
        messages, "scale this recipe to six servings",
    )
    assert owned is True
    assert projection["continuation"] is False
    frame = compile_intent(
        projection["retrieval_query"],
        continuation=projection["continuation"],
        reference_context={
            "ordered_entities": [{"ref": "recipe-1", "concept": "RECIPE"}],
            "last": {"ref": "recipe-1", "concept": "RECIPE"},
        },
    )
    assert frame.operation_class == "READ"
    assert resolve_intent(frame).action_id == "scale"


def test_contextual_cue_does_not_demote_substantive_recipe_create():
    messages = [
        {"role": "user", "content": "what recipes do i have"},
        {"role": "assistant", "content": "No recipes are recorded for this owner. The canonical Result is empty."},
        {"role": "user", "content": "add this recipe to my recipes: Acceptance Chicken and Rice"},
    ]
    projection, owned = provisional_intent_projection(
        messages, messages[-1]["content"],
    )
    assert owned is True
    assert projection["continuation"] is False
    assert projection["retrieval_query"] == messages[-1]["content"]
    frame = compile_intent(projection["retrieval_query"], continuation=False)
    assert frame.operation_class == "CREATE"
    assert frame.domain_concept == "RECIPE"
    assert resolve_intent(frame).action_id == "add"


def test_recipe_detail_followup_uses_session_reference_context_and_get_action():
    context = {
        "ordered_entities": [{"ref": "recipe-1", "concept": "RECIPE"}],
        "last": {"ref": "recipe-1", "concept": "RECIPE"},
    }
    frame = compile_intent("tell me about the first one", reference_context=context)
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "RECIPE"
    assert frame.entity_reference == "recipe-1"
    assert resolved.action_id == "get"
    assert resolved.binding_name == "read_recipes"


def test_turn_contract_accepts_recent_session_reference_context():
    context = {
        "ordered_entities": [{"ref": "recipe-1", "concept": "RECIPE"}],
        "last": {"ref": "recipe-1", "concept": "RECIPE"},
    }
    frame, resolved, _continuation, _domains = compile_turn_contract(
        {}, "tell me about the first one", reference_context=context,
    )
    assert frame.entity_reference == "recipe-1"
    assert resolved.action_id == "get"


def test_recipe_conceptual_question_stays_on_general_answer_floor():
    frame = compile_intent("what is a recipe")
    assert frame.domain_concept == "UNKNOWN"
    assert frame.operation_class == "ANSWER"
    assert deterministic_read_concept("what is a recipe") is None


@pytest.mark.parametrize("query", [
    "What all is on my network? do a discovery dive?",
    "tell me about the network, do a deep dive discovery mission to tell me whats going on",
    "map the devices on our current network",
])
def test_owner_discovery_language_creates_bounded_network_objective(query):
    frame = compile_intent(query)
    assert frame.domain_concept == "NETWORK"
    assert frame.operation_class == "EXECUTE"
    assert frame.target is None
    assert resolve_intent(frame).action_id == "plan_network_discovery"
    assert "network_scope_requires_authorization" in frame.constraints


def test_current_network_figure_it_out_is_context_read_not_discovery():
    frame = compile_intent("the network we're currently on, figure it out")
    resolved = resolve_intent(frame)
    assert frame.domain_concept == "NETWORK"
    assert frame.operation_class == "READ"
    assert frame.read_explicit is True
    assert frame.filters["view"] == "context"
    assert resolved.action_id == "read_network_context"


def test_content_topic_does_not_create_hades_pentest_action_without_target():
    from src.agent_loop import _classify_agent_request, _normalize_operational_intent_evidence
    for query in ("Explain pentesting", "can you help me pentest?"):
        intent = _classify_agent_request([], query)
        intent = _normalize_operational_intent_evidence(intent, query)
        assert "pentest_ops" not in intent["domains"]
    targeted = _classify_agent_request([], "Pentest this host; it is mine")
    assert "pentest_ops" in targeted["domains"]


@pytest.mark.parametrize("query", READ_PARAPHRASE_SETS["MEMORY"])
def test_owner_memory_paraphrases_converge_before_model_selection(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    agent_intent = _classify_agent_request([], query)
    assert is_explicit_memory_query(query)
    assert deterministic_read_concept(query) == "MEMORY"
    assert frame.domain_concept == "MEMORY"
    assert frame.operation_class == "READ"
    assert frame.read_explicit is True
    assert agent_intent["explicit_memory_query"] is True
    assert agent_intent["domains"] == {"memory"}
    assert resolved.available is True
    assert resolved.binding_name == "read_memory"
    assert resolved.action_id == "summarize_owner_memory"
    assert resolved.action.approval.value == "none"
    assert DETERMINISTIC_READ_TRAJECTORY[-3:] == ("RESULT_PROJECTION", "ANSWER", "COMPLETE")
    assert "BOUNDED_ACTION_SELECTION" in DETERMINISTIC_READ_MUST_NOT
    assert "APPROVAL" in DETERMINISTIC_READ_MUST_NOT


@pytest.mark.parametrize("query", READ_PARAPHRASE_SETS["WORK"])
def test_work_paraphrases_converge_on_owner_safe_work_reads(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.binding_name == "read_work"
    assert resolved.action.approval.value == "none"
    assert resolved.frame.operation_class == "READ"
    assert resolved.frame.read_explicit is True


@pytest.mark.parametrize("query", READ_PARAPHRASE_SETS["TECHNICAL_ASSET"])
def test_asset_paraphrases_converge_on_owner_safe_asset_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "TECHNICAL_ASSET"
    assert resolved.binding_name == "manage_assets"
    assert resolved.action_id == "list"
    assert resolved.action.approval.value == "none"
    assert resolved.frame.read_explicit is True


@pytest.mark.parametrize("query", [
    "Tell me about the first physical one.",
    "Tell me about the second machine.",
])
def test_resolved_asset_reference_projects_get_instead_of_relisting(query):
    frame = compile_intent(query, reference_context={
        "ordered_entities": [
            {"ref": "PHYSICAL-001", "concept": "TECHNICAL_ASSET"},
            {"ref": "PHYSICAL-002", "concept": "TECHNICAL_ASSET"},
        ],
    })
    payload = canonical_read_fast_path_payload(
        "manage_assets", "get", frame.as_dict(),
    )
    assert payload["action"] == "get"
    assert payload["asset"] in {"PHYSICAL-001", "PHYSICAL-002"}
    resolved = resolve_intent(frame)
    assert resolved.action_id == "get"
    assert canonical_read_action(
        "TECHNICAL_ASSET", frame.filters,
        entity_reference=frame.entity_reference,
    ) == "get"


def test_resolved_asset_fast_path_preserves_strong_identity():
    frame = compile_intent("Tell me about the first physical one.", reference_context={
        "ordered_entities": [
            {"ref": "PHYSICAL-001", "concept": "TECHNICAL_ASSET"},
        ],
    })
    # The ACI fast path must pass the same canonical payload as the
    # asset-specific repair path; an action-only ``get`` cannot execute.
    payload = canonical_asset_read_payload(frame.as_dict())
    assert payload == {"action": "get", "asset": "PHYSICAL-001"}


def test_recipe_fast_path_preserves_reference_query_and_servings():
    context = {
        "ordered_entities": [{"ref": "RECIPE-001", "concept": "RECIPE"}],
    }
    detail = compile_intent("tell me about the first one", reference_context=context)
    assert canonical_read_fast_path_payload(
        "read_recipes", "get", detail.as_dict(), query="tell me about the first one"
    ) == {"action": "get", "recipe_id": "RECIPE-001"}
    scaled = compile_intent("scale this recipe to six servings", reference_context=context)
    assert canonical_read_fast_path_payload(
        "read_recipes", "scale", scaled.as_dict(), query="scale this recipe to six servings"
    ) == {"action": "scale", "recipe_id": "RECIPE-001", "servings": "6"}


def test_ambiguous_asset_pronoun_does_not_become_lexical_target():
    frame = compile_intent("what about that one", reference_context={
        "ordered_entities": [
            {"ref": "PHYSICAL-001", "concept": "TECHNICAL_ASSET"},
            {"ref": "PHYSICAL-002", "concept": "TECHNICAL_ASSET"},
        ],
    })
    assert frame.reference_resolution["status"] == "AMBIGUOUS"
    assert frame.entity_reference is None


@pytest.mark.parametrize("query", READ_PARAPHRASE_SETS["NETWORK_CONTEXT"])
def test_current_network_paraphrases_converge_on_context_read_not_discovery(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "NETWORK"
    assert resolved.frame.filters["view"] == "context"
    assert resolved.binding_name == "manage_homelab"
    assert resolved.action_id == "read_network_context"
    assert resolved.action.approval.value == "none"
    assert resolved.frame.operation_class == "READ"


@pytest.mark.parametrize("query", [
    "What is my default route?",
    "What interface is carrying traffic?",
    "What is the current network context?",
    "What subnet am I on?",
])
def test_network_context_detail_paraphrases_use_host_context_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "NETWORK"
    assert resolved.frame.filters["view"] == "context"
    assert resolved.action_id == "read_network_context"


@pytest.mark.parametrize("query", [
    "Can you inspect the host?",
    "Check this host.",
    "Show me the current host.",
])
def test_explicit_host_inspection_uses_host_read_not_network_observations(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "HOMELAB_HOST"
    assert resolved.action_id == "inspect_host"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "Remind me what I've got going.",
    "What have I got going on?",
    "What's keeping me busy?",
    "What projects are currently in progress?",
    "alright what am i working on again",
    "okay so what am i working on",
])
def test_work_status_paraphrases_are_canonical_reads(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "WORK"
    assert resolved.action_id == "overview"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "Do a deep dive on my local network.",
    "Investigate my network.",
    "Look into the current LAN.",
])
def test_unscoped_network_deep_dive_requires_explicit_authorized_scope(query):
    frame = compile_intent(query)
    assert frame.domain_concept == "NETWORK"
    assert frame.operation_class == "RESEARCH"
    assert "network_scope_requires_authorization" in frame.constraints
    assert resolve_intent(frame).available is False


def test_explicit_bounded_network_scope_keeps_normal_plan_contract():
    frame = compile_intent("Scan the network 192.168.1.0/24")
    assert frame.domain_concept == "NETWORK"
    assert frame.operation_class == "EXECUTE"
    assert "network_scope_requires_authorization" not in frame.constraints
    assert resolve_intent(frame).action_id == "plan_network_discovery"


@pytest.mark.parametrize("query", ["Where did we leave off?", "Where'd I leave off?"])
def test_work_status_continuity_question_is_a_safe_work_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "WORK"
    assert resolved.action_id == "overview"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", ["Review outstanding work.", "Show my open work."])
def test_outstanding_work_review_is_the_existing_work_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "WORK"
    assert resolved.action_id == "overview"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "What's running in Odysseus?",
    "Anything unhealthy right now?",
    "What services are alive?",
    "Are my services alive?",
    "Is everything healthy?",
    "Anything broken?",
])
def test_infrastructure_status_paraphrases_use_safe_service_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "SERVICE"
    assert resolved.action_id == "service_status"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "whats running",
    "hows Hades doing",
    "anything dead",
    "anything down right now",
    "what the hell is busted",
    "are we good",
    "how is the stack",
])
def test_casual_infrastructure_status_paraphrases_use_safe_service_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "SERVICE"
    assert resolved.action_id == "service_status"
    assert resolved.action.approval.value == "none"


@pytest.mark.parametrize("query", [
    "tell me abotu me",
    "give me my lore",
    "what's my background",
    "what's my deal",
    "what do you actually have saved",
])
def test_messy_owner_self_knowledge_stays_on_memory_read_family(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "MEMORY"
    assert resolved.action_id == "summarize_owner_memory"
    assert resolved.action.approval.value == "none"


def test_physical_host_inventory_is_not_shadowed_by_network_host_language():
    resolved = resolve_intent(compile_intent("What physical hosts do I own?"))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "TECHNICAL_ASSET"
    assert resolved.action_id == "list"


def test_current_network_context_is_not_filtered_as_a_definition():
    resolved = resolve_intent(compile_intent("What is the current network context?"))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "NETWORK"
    assert resolved.action_id == "read_network_context"


@pytest.mark.parametrize("query", [
    "tell me about my network",
    "tell me about our network",
    "what network am i on",
    "what's my network like",
    "show me my network",
    "what do we know about our network",
    "yo what network am i on",
    "what about the network i'm on",
    "give me the network context",
    "what's the current connection",
])
def test_owner_network_paraphrases_use_bounded_canonical_read(query):
    resolved = resolve_intent(compile_intent(query))
    assert resolved.available is True
    assert resolved.frame.domain_concept == "NETWORK"
    assert resolved.frame.operation_class == "READ"
    assert resolved.binding_name == "manage_homelab"
    assert resolved.action_id in {"read_network_context", "read_network_observations"}


@pytest.mark.parametrize("query", [
    "what is a network",
    "tell me about networking",
    "how does subnetting work",
    "explain a default route",
])
def test_network_concept_questions_stay_on_general_answer_floor(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert frame.operation_class == "ANSWER"
    assert not (resolved.available and frame.operation_class in {"READ", "EXECUTE"})


@pytest.mark.parametrize("query", [
    "What is a network?",
    "Tell me about networking.",
    "What is RAID 10?",
    "What is a GPU?",
    "How does Docker work?",
    "What is DNS?",
])
def test_conceptual_minimal_pair_variants_have_no_canonical_action(query):
    frame = compile_intent(query)
    assert frame.operation_class == "ANSWER"
    assert frame.domain_concept == "UNKNOWN"
    assert resolve_intent(frame).available is False


def test_unknown_selfstate_capability_question_does_not_become_work_read():
    frame = compile_intent("What capabilities are working?")
    assert frame.domain_concept == "UNKNOWN"
    assert resolve_intent(frame).available is False


@pytest.mark.parametrize("query", ["go on", "please go on", "keep going"])
def test_natural_resume_language_is_classified_as_continuation(query):
    assert compile_intent(query).operation_class == "CONTINUE"


@pytest.mark.parametrize("query", [
    "What's the difference between a VM and a container?",
    "Explain containers versus virtual machines.",
])
def test_general_container_explanations_do_not_become_host_inspection(query):
    frame = compile_intent(query)
    assert frame.domain_concept == "UNKNOWN"
    assert resolve_intent(frame).available is False


@pytest.mark.parametrize("query", [
    *NEGATIVE_NEAR_MISSES["MEMORY"],
    *NEGATIVE_NEAR_MISSES["WORK"],
    *NEGATIVE_NEAR_MISSES["TECHNICAL_ASSET"],
    *NEGATIVE_NEAR_MISSES["NETWORK"],
])
def test_negative_near_misses_do_not_become_owner_state_reads(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert not (resolved.available and frame.operation_class == "READ")


def test_answer_only_projection_has_no_tool_prompt_or_binding_identity():
    messages = [
        {"role": "system", "content": "Use manage_memory and read_memory schemas."},
        {
            "role": "user",
            "content": "CANONICAL MEMORY RESULT\nSTATUS: OK\n- REMEMBERED: owner fact",
            "_protected": True,
            "metadata": {
                "trusted": False,
                "context_kind": "explicit_memory_result",
                "memory_result_status": "ok",
            },
        },
        {"role": "user", "content": "Tell me about me."},
    ]
    assert prefetched_explicit_memory_result(messages)
    projected = minimal_aci_answer_messages(messages)
    serialized = "\n".join(str(message.get("content") or "") for message in projected)
    assert "manage_memory" not in serialized
    assert "read_memory" not in serialized
    assert "owner fact" in serialized
    assert projected[-1]["content"] == "Tell me about me."


def test_answer_only_projection_discards_unrelated_session_residue():
    messages = [
        {"role": "user", "content": "What do you remember about me?"},
        {"role": "assistant", "content": "Old work answer mentioning a stale project."},
        {"role": "user", "content": "What's on my plate right now?"},
        {
            "role": "tool",
            "content": '{"status":"SUCCESS_WITH_DATA","output":"current work items"}',
            "metadata": {"assistant_tool_result": True},
        },
    ]
    projected = minimal_aci_answer_messages(messages)
    serialized = "\n".join(str(message.get("content") or "") for message in projected)
    assert "stale project" not in serialized
    assert "current work items" in serialized
    assert projected[-1]["content"] == "What's on my plate right now?"


def test_protected_aci_state_survives_provider_route_rebuild():
    packet = {
        "role": "system",
        "content": "HADES ACI MACHINE DECISION MODE",
        "_agent_injected": "hades_aci_packet",
        "_protected": True,
    }
    assert packet in _strip_agent_injected_messages([
        {"role": "system", "content": "old", "_agent_injected": "prompt"},
        packet,
        {"role": "user", "content": "request"},
    ])


@pytest.mark.parametrize(
    "query",
    (
        *READ_PARAPHRASE_SETS["MEMORY"],
        *READ_PARAPHRASE_SETS["WORK"],
        *READ_PARAPHRASE_SETS["TECHNICAL_ASSET"],
        *READ_PARAPHRASE_SETS["NETWORK_CONTEXT"],
    ),
)
def test_exact_resolved_read_result_is_answer_terminal(query):
    frame = compile_intent(query)
    resolved = resolve_intent(frame)
    assert resolved.available is True
    block = ToolBlock(resolved.binding_name, '{"action":"' + resolved.action_id + '"}')
    assert matches_resolved_canonical_read(block, frame.as_dict(), resolved.as_dict())
