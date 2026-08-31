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
