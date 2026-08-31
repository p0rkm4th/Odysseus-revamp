from src.field_resolvers import deterministic_action_for_contract, resolve_action_fields


def test_scheduled_fields_resolve_from_contract_without_domain_dispatch():
    contract = {
        "capability_id": "automation.task.manage",
        "action_id": "create",
        "binding": "manage_tasks",
    }
    frame = {"domain_concept": "SCHEDULED_TASK", "operation_class": "CREATE"}
    fields = resolve_action_fields(
        capability_id=contract["capability_id"],
        action_id=contract["action_id"],
        query="Every morning remind me to review my calendar.",
        frame=frame,
    )
    assert fields["prompt"] == "Review my calendar"

    action = deterministic_action_for_contract(
        contract, query="Every morning remind me to review my calendar.",
        frame=frame, disabled_tools=set(),
    )
    assert action and action[0] == "manage_tasks"
    assert action[1]["schedule"] == "daily"


def test_read_query_fields_follow_action_spec_metadata():
    frame = {"domain_concept": "MEMORY", "operation_class": "READ"}
    assert resolve_action_fields(
        capability_id="memory.read", action_id="summarize_owner_memory",
        query="what do you know about my test color", frame=frame,
    ) == {"query": "what do you know about my test color"}


def test_web_fetch_fields_use_url_schema_without_projection_branch():
    assert resolve_action_fields(
        capability_id="web.evidence", action_id="fetch",
        query=" https://example.test/recipe ", frame={"domain_concept": "WEB"},
    ) == {"url": "https://example.test/recipe"}
