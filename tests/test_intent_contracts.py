import pytest

from src.intent_contracts import (
    DOMAIN_CONTRACTS,
    compile_intent,
    generated_parity_matrix,
    resolve_intent,
    result_status,
    validate_result,
    validate_contracts,
)


def test_contract_registry_is_complete_for_registered_contracts():
    assert validate_contracts() == []


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


def test_household_reads_compile_to_the_canonical_read_binding():
    resolved = resolve_intent(compile_intent("What is in my pantry?"))
    assert resolved.available is True
    assert resolved.contract.capability_id == "household.read"
    assert resolved.action_id == "overview"
    assert resolved.binding_name == "read_household"
    assert resolved.action.approval.value == "none"


def test_generated_parity_rows_have_explicit_transport_applicability():
    rows = generated_parity_matrix()
    assert rows
    for row in rows:
        assert row["capability_id"] and row["action_id"] and row["result_contract"]
        assert set(row["exposure"]) == {"MODEL", "API", "WORK", "UI", "AUTOMATION"}
        assert all(value in {"YES", "NO", "N/A"} for value in row["exposure"].values())
