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
    assert {"OWNER-ASSET-RAM-001", "OWNER-NETWORK-001", "OWNER-ASSET-FILTER-NO-MATCH-001", "OWNER-RECIPE-EMPTY-001", "OWNER-RECIPE-MUTATION-READBACK-001", "OWNER-HOUSEHOLD-MUTATION-READBACK-001"} <= set(scenarios)
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
