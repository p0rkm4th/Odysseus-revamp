import json
from pathlib import Path


JOURNEY_FILE = Path(__file__).parents[1] / "benchmarks" / "hades_owner_journeys.json"


def test_owner_journey_corpus_has_required_black_box_scenarios():
    payload = json.loads(JOURNEY_FILE.read_text())
    assert payload["schema_version"] == 1
    assert set(payload["environments"]) == {
        "deterministic_synthetic", "realistic_messy_synthetic", "actual_owner_read_only",
    }
    scenarios = {case["id"]: case for case in payload["scenarios"]}
    assert {"OWNER-ASSET-RAM-001", "OWNER-NETWORK-001", "OWNER-ASSET-FILTER-NO-MATCH-001", "OWNER-RECIPE-EMPTY-001", "OWNER-RECIPE-MUTATION-READBACK-001", "OWNER-HOUSEHOLD-MUTATION-READBACK-001", "OWNER-MEMORY-EMPTY-001", "OWNER-WORK-EMPTY-001"} <= set(scenarios)
    for case in scenarios.values():
        assert case["turns"]
        assert case["fixture_profile"]
        for turn in case["turns"]:
            expected = turn["expected"]
            assert expected["domain"] and expected["operation"] and expected["answer_source"]
        assert case["expected"]["terminal"]["done"] == len(case["turns"])


def test_mutation_cases_require_effect_evidence_and_readback():
    payload = json.loads(JOURNEY_FILE.read_text())
    for case in payload["scenarios"]:
        if any(turn["expected"].get("requires_effect") for turn in case["turns"]):
            assert case["expected"].get("after", {}).get("readback") is True


def test_turn_expectations_pin_each_action_and_binding_without_inheriting_wrong_defaults():
    payload = json.loads(JOURNEY_FILE.read_text())
    from src.capability_registry import capability_for_tool

    for case in payload["scenarios"]:
        for turn in case["turns"]:
            expected = turn["expected"]
            if expected["operation"] in {"READ", "CREATE", "UPDATE", "DELETE", "EXECUTE"}:
                assert expected.get("action"), f"{case['id']} turn lacks action"
                assert expected.get("tool_binding"), f"{case['id']} turn lacks tool binding"
                capability = capability_for_tool(expected["tool_binding"])
                assert capability is not None, f"{case['id']} names unknown tool binding"
                assert expected["action"] in capability.actions, (
                    f"{case['id']} expects tool name/action mismatch: "
                    f"{expected['tool_binding']}.{expected['action']}"
                )


def test_semantic_oracle_can_require_all_canonical_facts():
    payload = json.loads(JOURNEY_FILE.read_text())
    ram = next(case for case in payload["scenarios"] if case["id"] == "OWNER-ASSET-RAM-001")
    expected = ram["turns"][0]["expected"]
    assert set(expected["must_include_all"]) >= {"Atlas", "64", "Erebus", "128"}


def test_synthetic_scenarios_are_explicitly_distinct_from_owner_read_only():
    payload = json.loads(JOURNEY_FILE.read_text())
    for case in payload["scenarios"]:
        if case["environment"] != "actual_owner_read_only":
            assert case["environment"] in {"deterministic_synthetic", "realistic_messy_synthetic"}
            assert payload["environments"][case["environment"]]["fixture_profile"]
