import argparse
import asyncio
import json

import pytest

from benchmarks.hades_dogfood import (
    capture_failure_regressions,
    coverage_audit,
    expand_cases,
    ScenarioFrame,
    generate_scenario_frames,
    cluster_failures,
    generate_semantic_cases,
    generate_metamorphic_cases,
    generate_negative_near_miss_cases,
    generate_minimal_pair_cases,
    generate_hidden_holdout_cases,
    generate_chaos_journeys,
    load_regression_cases,
    load_contract,
    normalize_events,
    summarize,
    shard_cases,
    score_case,
    _CROSS_DOMAIN_PAIRS,
    _FAILURE_TAXONOMY,
    delivery_observation,
    authoritative_answer_text,
)
from scripts.hades_dogfood import (
    _case_deadline,
    _case_deadline_expired,
    _live_protocol_observation,
    _source_dirty,
    _source_reference,
    configured_model_endpoint,
)
from benchmarks.jarvis.synthetic_tools import fixtures_for_case


def test_registry_action_generator_classifies_effectful_actions_and_contextualizes_them():
    from benchmarks.hades_dogfood import _registry_action_entries

    entries = _registry_action_entries()
    workspace = next(item for item in entries if item["capability_id"] == "developer.workspace_shell")
    assert workspace["action_id"] == "execute"
    assert workspace["operation"] == "EXECUTE"
    generated = next(case for case in generate_semantic_cases(seed=17, count=entries.index(workspace) + 1)
                     if case["scenario"].get("capability_id") == "developer.workspace_shell")
    assert "DEVELOPER" in generated["prompt"].upper()
    assert generated["expected"]["operation"] == "EXECUTE"


def test_registry_action_language_preserves_declared_domain():
    """Generated action wording must not change the ScenarioFrame domain."""
    from benchmarks.hades_dogfood import _registry_action_entries

    entries = _registry_action_entries()
    cases = generate_semantic_cases(seed=29, count=len(entries))
    registry_cases = [case for case in cases if case["family"] == "registry_action"]
    assert len(registry_cases) == len(entries)
    for case in registry_cases:
        domain = str(case["scenario"]["domain"]).replace("_", " ").casefold()
        assert domain in case["prompt"].casefold()


def test_registry_read_probes_allow_one_bounded_action_selection():
    """Registry ActionSpec probes are not canonical deterministic reads."""
    from benchmarks.hades_dogfood import _registry_action_entries

    entries = _registry_action_entries()
    cases = generate_semantic_cases(seed=31, count=len(entries))
    registry_cases = [case for case in cases if case["family"] == "registry_action"]
    assert registry_cases
    assert all(
        case["expected"].get("max_decision_calls") == 1
        for case in registry_cases
        if case["expected"].get("operation") == "READ"
    )

    semantic = next(
        case for case in generate_semantic_cases(seed=31, count=len(entries) + 1)
        if case["family"] != "registry_action"
    )
    assert semantic["expected"].get("max_decision_calls") == 0


def test_generated_registry_cases_project_executor_fixture_without_oracle_fields():
    cases = generate_semantic_cases(seed=23, count=40)
    registry_cases = [case for case in cases if case["family"] == "registry_action"]
    assert registry_cases
    for case in registry_cases:
        if (
            case["scenario"].get("executor") in {None, "", "none"}
            or not case["scenario"].get("synthetic_capability_available", True)
        ):
            continue
        assert case["environment"].get("fixture_profile", {}).get("tools")
        altered = {**case, "expected": {"concept": "WRONG_ORACLE"}}
        assert fixtures_for_case(case) == fixtures_for_case(altered)


def test_unsupported_registry_executor_is_not_given_neighboring_read_fixture():
    cases = generate_semantic_cases(seed=20260828, count=5)
    for case, executor in ((cases[0], "workspace_yolo"), (cases[4], "local_intelligence")):
        assert case["scenario"]["executor"] == executor
        assert case["scenario"]["synthetic_capability_available"] is False
        assert case["environment"] == {}
        assert case["expected"]["capability_available"] is False


def test_dogfood_contract_expands_frozen_sources_and_journeys():
    contract = load_contract()
    cases = expand_cases(contract, suite="baseline")
    assert len(cases) > len(contract["frozen_failures"])
    assert any(case["source"] == "aci_corpus" for case in cases)
    assert any(case["source"] == "jarvis_control_plane" for case in cases)
    assert any(case["source"] == "journey" for case in cases)
    assert len({case["id"] for case in cases}) == len(cases)


def test_unscoped_network_discovery_contract_requires_refusal_without_execution():
    cases = expand_cases(load_contract(), suite="baseline")
    cases_by_id = {case["id"]: case for case in cases}
    for case_id in (
        "jarvis-tool-exposure-network",
        "owner-network-discovery-scope-01",
        "owner-network-discovery-scope-02",
    ):
        expected = cases_by_id[case_id]["expected"]
        assert expected["must_refuse"] is True
        assert expected["max_tool_calls"] == 0
        assert "required_tools" not in expected


def test_dogfood_normalization_is_sanitized_and_projects_runtime_metrics():
    case = {"id": "fixture", "source": "test", "family": "test", "prompt": "secret prompt"}
    record = normalize_events([
        {"type": "tool_start", "tool": "read_memory", "full_command": "{}"},
        {"type": "tool_output", "exit_code": 1},
        {"type": "message_saved", "id": "stable"},
        {"type": "message_saved", "id": "stable"},
        {"delta": "answer api_key=should-not-be-retained"},
        {"type": "metrics", "data": {
            "model_calls": 2, "input_tokens": 11, "output_tokens": 4,
            "aci_bounded_action_decision_count": 1,
            "aci_intent": {"domain_concept": "MEMORY", "operation_class": "READ"},
        }},
    ], case)
    assert "secret prompt" not in str(record)
    assert record["assistant_answer"]["secret_seen"] is True
    assert record["trajectory"]["duplicate_delivery"] == 1
    assert record["trajectory"]["failed_actions"] == 1
    assert record["metrics"]["decision_calls"] == 1


def test_live_protocol_requires_one_terminal_done_marker():
    events = [{"event_id": "evt-1", "delta": "partial"}]
    complete = _live_protocol_observation(events, done_count=1, abrupt_eof=False)
    assert complete["transport_completion"] is True
    assert complete["terminal_event_count"] == 1
    assert complete["duplicate_event_id"] is False

    incomplete = _live_protocol_observation(events, done_count=0, abrupt_eof=True)
    assert incomplete["transport_completion"] is False
    assert incomplete["terminal_event_count"] == 0
    assert incomplete["abrupt_eof"] is True


def test_live_case_deadline_is_absolute_not_only_read_inactivity():
    import time

    deadline = _case_deadline(time.perf_counter() - 2, 1)
    assert _case_deadline_expired(deadline) is True
    assert _case_deadline_expired(_case_deadline(time.perf_counter(), 30)) is False


def test_incremental_dogfood_checkpoint_retains_progress_and_classifies_stop(tmp_path):
    from scripts.hades_dogfood import _IncrementalCheckpoint

    path = tmp_path / "run.jsonl"
    checkpoint = _IncrementalCheckpoint(path, metadata={"run_id": "r1", "seed": 7}, total=2)
    checkpoint.case(1, "case-1", {"failure_class": "CASE_TIMEOUT"}, status="timeout")
    checkpoint.stopped("signal")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["kind"] for row in rows] == ["run_started", "case", "run_stopped"]
    assert rows[1]["status"] == "timeout"
    assert rows[1]["record"]["failure_class"] == "CASE_TIMEOUT"
    assert rows[-1]["completed"] == 1
    assert rows[-1]["remaining"] == 1


def test_run_cases_persists_timeout_rows_without_losing_following_cases(monkeypatch, tmp_path):
    import scripts.hades_dogfood as runner

    cases = [
        {"id": "slow", "prompt": "slow", "family": "test", "source": "test", "expected": {}},
        {"id": "fast", "prompt": "fast", "family": "test", "source": "test", "expected": {}},
    ]
    calls = 0

    async def fake_run_synthetic(case, _args, *, messages=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise asyncio.TimeoutError
        return (
            {"assistant_answer": {"present": True}, "metrics": {"model_calls": 0}},
            "grounded answer",
        )

    monkeypatch.setattr(runner, "run_synthetic", fake_run_synthetic)
    args = argparse.Namespace(case_timeout=1)
    checkpoint = runner._IncrementalCheckpoint(tmp_path / "progress.jsonl", metadata={"run_id": "r"}, total=2)
    records = asyncio.run(runner.run_cases(args, cases, checkpoint=checkpoint))
    assert len(records) == 2
    assert records[0]["failure_class"] == "CASE_TIMEOUT"
    assert records[1]["assistant_answer"]["present"] is True
    rows = [json.loads(line) for line in (tmp_path / "progress.jsonl").read_text().splitlines()]
    assert [row["kind"] for row in rows] == ["run_started", "case", "case", "run_finished"]
    assert [row["status"] for row in rows[1:3]] == ["timeout", "completed"]
    assert rows[-1]["completed"] == 2
    assert rows[-1]["remaining"] == 0


def test_run_synthetic_enforces_the_per_case_deadline(monkeypatch):
    import src.aci as aci
    import scripts.hades_dogfood as runner

    async def hanging_stream(*_args, **_kwargs):
        await asyncio.sleep(1)
        yield 'data: {"delta":"late"}\n\n'

    monkeypatch.setattr(aci, "stream_aci_turn", hanging_stream)
    args = argparse.Namespace(
        endpoint="http://model.test", model="qwen3:8b", case_timeout=0.01,
        max_tokens=128, max_rounds=1, max_tool_calls=1, context_length=2048,
    )
    case = {"id": "deadline", "prompt": "slow", "expected": {}}

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(runner.run_synthetic(case, args))


def test_dogfood_uses_configured_container_model_endpoint(monkeypatch):
    monkeypatch.setenv("HADES_OLLAMA_ENDPOINT", "http://host.docker.internal:11434")
    assert configured_model_endpoint() == "http://host.docker.internal:11434"


def test_dogfood_keeps_standalone_loopback_default(monkeypatch):
    monkeypatch.delenv("HADES_OLLAMA_ENDPOINT", raising=False)
    assert configured_model_endpoint() == "http://127.0.0.1:11434"


def test_container_dogfood_uses_embedded_source_when_git_is_absent(tmp_path, monkeypatch):
    import scripts.hades_dogfood as dogfood

    marker = tmp_path / ".odysseus-source-commit"
    marker.write_text("embedded-sha\n", encoding="utf-8")
    monkeypatch.setattr(dogfood, "ROOT", tmp_path)
    monkeypatch.delenv("HADES_SOURCE_REFERENCE", raising=False)

    def no_git(*_args, **_kwargs):
        raise OSError("git unavailable")

    monkeypatch.setattr(dogfood.subprocess, "run", no_git)
    assert _source_reference() == "embedded-sha"
    assert _source_dirty() is False


def test_synthetic_owner_reads_use_typed_empty_results():
    case = {"expected": {"required_tools": ["read_memory", "read_work", "manage_assets"]}}
    fixtures = fixtures_for_case(case)
    assert fixtures["read_memory"][0]["data"]["status"] == "zero_result"
    assert fixtures["read_work"][0]["data"]["status"] == "SUCCESS_EMPTY"
    assert '"assets": []' in fixtures["manage_assets"][0]["output"]


def test_legacy_work_cases_receive_typed_fixture_from_semantic_owner():
    for case in (
        {"family": "work", "expected": {}},
        {"family": "metamorphic", "expected": {"concept": "WORK"}},
    ):
        fixtures = fixtures_for_case(case)
        assert fixtures["read_work"][0]["data"]["status"] == "SUCCESS_EMPTY"


def test_legacy_owner_cases_receive_semantic_tool_fixtures():
    cases = (
        ({"family": "service", "expected": {}}, "manage_homelab"),
        ({"family": "security", "expected": {}}, "manage_security_assessment"),
        ({"family": "developer", "expected": {}}, "developer_read"),
    )
    for case, tool in cases:
        assert tool in fixtures_for_case(case)


def test_legacy_metamorphic_owner_concepts_receive_typed_fixtures():
    """Compatibility cases must not turn successful reads into fixture failures."""
    cases = (
        ({"family": "metamorphic", "expected": {"concept": "MEMORY"}}, "read_memory"),
        ({"family": "metamorphic", "expected": {"concept": "TECHNICAL_ASSET"}}, "manage_assets"),
        ({"family": "metamorphic", "expected": {"concept": "NETWORK_CONTEXT"}}, "manage_homelab"),
        ({"family": "metamorphic", "expected": {"concept": "HOUSEHOLD"}}, "read_household"),
    )
    for case, tool in cases:
        fixtures = fixtures_for_case(case)
        assert tool in fixtures
        assert fixtures[tool][0]["exit_code"] == 0


def test_metamorphic_fixture_world_is_explicit_and_oracle_independent():
    cases = expand_cases(load_contract(), suite="baseline")
    case = next(item for item in cases if item["id"] == "meta-memory-01")
    assert case["environment"] == {"fixture_profile": {"tools": ["read_memory"]}}
    altered = {**case, "expected": {"concept": "NETWORK", "required_tools": ["manage_homelab"]}}
    assert fixtures_for_case(case) == fixtures_for_case(altered)


def test_explicit_environment_fixture_is_independent_of_expected_oracle():
    base = {
        "prompt": "show my machines",
        "family": "unrelated",
        "environment": {"fixture_profile": {"tools": ["manage_assets"]}},
        "expected": {"concept": "TECHNICAL_ASSET", "required_tools": ["manage_assets"]},
    }
    altered = {
        **base,
        "expected": {
            "concept": "NETWORK",
            "required_tools": ["manage_homelab"],
            "tool_args": [{"name": "manage_homelab"}],
        },
    }
    assert fixtures_for_case(base) == fixtures_for_case(altered)
    assert set(fixtures_for_case(altered)) == {"manage_assets"}


def test_synthetic_execution_trajectory_is_independent_of_oracle_metadata(monkeypatch):
    """The answer key may score a run, but must not steer its execution."""
    import src.aci as aci
    from scripts.hades_dogfood import run_synthetic

    observed = []

    async def fake_stream(**kwargs):
        executor = kwargs["tool_executor"]

        class Block:
            tool_type = "manage_assets"
            content = "show the synthetic asset inventory"

        fixture_text, fixture_result = await executor(Block())
        observed.append({
            "endpoint": kwargs["endpoint_url"],
            "model": kwargs["model"],
            "messages": kwargs["messages"],
            "fixture_text": fixture_text,
            "fixture_result": fixture_result,
        })
        yield 'data: {"type":"delta","delta":"grounded fixture answer"}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(aci, "stream_aci_turn", fake_stream)
    args = argparse.Namespace(
        endpoint="http://model.test", model="qwen3:8b", case_timeout=5,
        max_tokens=128, max_rounds=1, max_tool_calls=1, context_length=2048,
    )
    base = {
        "id": "oracle-invariance",
        "source": "test",
        "prompt": "show my machines",
        "family": "asset",
        "environment": {"fixture_profile": {"tools": ["manage_assets"]}},
        "expected": {"concept": "TECHNICAL_ASSET", "operation": "READ"},
    }
    altered = {
        **base,
        "expected": {"concept": "NETWORK", "operation": "EXECUTE", "must_refuse": True},
    }
    first = asyncio.run(run_synthetic(base, args))
    second = asyncio.run(run_synthetic(altered, args))

    assert first[0]["assistant_answer"]["present"] is True
    assert second[0]["assistant_answer"]["present"] is True
    assert observed[0] == observed[1]


def test_aci_corpus_declares_fixture_world_outside_expected_oracle():
    cases = {
        case["id"]: case
        for case in expand_cases(load_contract(), suite="all")
        if case["id"] in {"aci-canonical_reads-04", "aci-canonical_reads-09"}
    }
    assert cases["aci-canonical_reads-04"]["environment"] == {
        "fixture_profile": {"tools": ["read_work"]}
    }
    assert cases["aci-canonical_reads-09"]["environment"] == {
        "fixture_profile": {"tools": ["manage_security_assessment"]}
    }
    for case in cases.values():
        altered = {**case, "expected": {"concept": "WRONG_ORACLE", "required_tools": []}}
        assert fixtures_for_case(case) == fixtures_for_case(altered)


def test_mixed_aci_corpus_domains_declare_semantic_fixture_world():
    cases = {
        case["id"]: case
        for case in expand_cases(load_contract(), suite="all")
        if case["id"] in {
            "aci-domain-07", "aci-domain-09", "aci-continuation-10", "aci-security-10",
        }
    }
    assert cases["aci-domain-07"]["environment"] == {
        "fixture_profile": {"tools": ["read_work"]}
    }
    assert cases["aci-domain-09"]["environment"] == {
        "fixture_profile": {"tools": ["read_setup"]}
    }
    assert cases["aci-continuation-10"]["environment"] == {
        "fixture_profile": {"tools": ["read_work"]}
    }
    assert cases["aci-security-10"]["environment"] == {
        "fixture_profile": {"tools": ["read_work"]}
    }
    for case in cases.values():
        altered = {**case, "expected": {"concept": "WRONG_ORACLE", "required_tools": []}}
        assert fixtures_for_case(case) == fixtures_for_case(altered)


def test_imported_live_cases_declare_fixture_world_outside_expected_oracle():
    cases = {
        case["id"]: case
        for case in expand_cases(load_contract(), suite="all")
        if case["id"] in {"live-memory_1", "live-work_1", "live-network_1", "live-assets_list"}
    }
    assert set(fixtures_for_case(cases["live-memory_1"])) == {"read_memory"}
    assert set(fixtures_for_case(cases["live-work_1"])) == {"read_work"}
    assert set(fixtures_for_case(cases["live-network_1"])) == {"manage_homelab"}
    assert set(fixtures_for_case(cases["live-assets_list"])) == {"manage_assets"}
    for case in cases.values():
        altered = {**case, "expected": {"concept": "WRONG_ORACLE", "required_tools": []}}
        assert fixtures_for_case(case) == fixtures_for_case(altered)


def test_generated_cases_declare_fixture_world_from_capability_not_oracle():
    cases = generate_semantic_cases(seed=17, count=80)
    cases = [case for case in cases if case.get("environment")]
    assert cases
    for case in cases:
        altered = {**case, "expected": {"concept": "WRONG_ORACLE", "required_tools": []}}
        assert fixtures_for_case(case) == fixtures_for_case(altered)


def test_generated_fixture_world_enacts_frame_result_without_reading_oracle():
    cases = [case for case in generate_semantic_cases(seed=17, count=80)
             if case.get("environment") and case["scenario"]["execution_result"] != "SUCCESS"]
    assert cases
    case = cases[0]
    state = case["scenario"]["execution_result"]
    fixtures = fixtures_for_case(case)
    tool = next(iter(fixtures))
    assert fixtures[tool][0].get("synthetic_state") == state or state == "PARTIAL"
    altered = {**case, "expected": {"concept": "WRONG_ORACLE", "operation": "WRONG"}}
    assert fixtures_for_case(case) == fixtures_for_case(altered)


def test_live_protocol_duplicate_done_marker_is_not_completion():
    result = _live_protocol_observation([], done_count=2, abrupt_eof=False)
    assert result["done_seen"] is True
    assert result["terminal_event_count"] == 2
    assert result["transport_completion"] is False


def test_delivery_observation_detects_lifecycle_duplicates_without_text_deduplication():
    clean = delivery_observation([
        {"type": "delta", "delta": "same words"},
        {"type": "response_replace", "content": "same words", "event_id": "final-1"},
    ])
    assert clean["duplicate_finalization"] is False
    assert clean["stale_delta_after_replace"] is False

    broken = delivery_observation([
        {"type": "response_replace", "content": "answer", "event_id": "final-1"},
        {"type": "response_replace", "content": "answer", "event_id": "final-1"},
        {"type": "delta", "delta": "stale"},
    ])
    assert broken["duplicate_finalization"] is True
    assert broken["stale_delta_after_replace"] is True
    assert broken["duplicate_event_id"] is True


def test_evaluator_uses_authoritative_replacement_for_answer_and_journey_context():
    events = [
        {"type": "delta", "delta": "model prose"},
        {"type": "response_replace", "content": "canonical result", "event_id": "final-1"},
    ]
    assert authoritative_answer_text(events) == "canonical result"
    case = {"id": "replacement", "source": "test", "family": "read", "prompt": "state"}
    record = normalize_events(events, case)
    assert record["assistant_answer"]["present"] is True
    assert record["assistant_answer"]["chars"] == len("canonical result")


def test_architectural_fail_is_distinct_from_functional_pass():
    case = {
        "id": "case", "family": "asset_resolution", "expected": {
            "concept": "TECHNICAL_ASSET", "operation": "READ",
            "max_decision_calls": 0, "max_tool_index_lookups": 0,
            "max_failed_actions": 0,
        },
    }
    record = {
        "assistant_answer": {"present": True, "internal_leak": False, "secret_seen": False},
        "trajectory": {"tool_calls": 0, "failed_actions": 0, "duplicate_delivery": 0,
                        "intent": {"domain_concept": "TECHNICAL_ASSET", "operation_class": "READ"},
                        "reference": {}},
        "metrics": {"model_calls": 3, "decision_calls": 1, "tool_index_lookups": 0,
                     "context_hydrations": 0},
        "runtime": {"completion": False, "fallback": False, "intent": {}, "reference": {}},
    }
    score = score_case(case, record)
    assert score["functional_pass"] is True
    assert score["architectural_pass"] is False
    assert score["outcome"] == "FUNCTIONAL_PASS"


def test_semantic_oracle_rejects_fluent_answer_without_canonical_action():
    case = {
        "id": "semantic-action-required", "family": "generated_semantic",
        "expected": {
            "concept": "TECHNICAL_ASSET", "operation": "READ",
            "semantic_oracle": {
                "expected_domain": "TECHNICAL_ASSET",
                "expected_completion": "COMPLETE_AFTER_ANSWER",
                "expected_grounding": "CURRENT_ACTION_RESULT",
            },
        },
        "scenario": {"action_spec": "inventory.manage:list"},
    }
    record = {
        "assistant_answer": {"present": True, "internal_leak": False, "secret_seen": False},
        "trajectory": {
            "tool_calls": 0, "failed_actions": 0, "duplicate_delivery": 0,
            "intent": {"domain_concept": "TECHNICAL_ASSET", "operation_class": "READ"},
            "reference": {}, "aci_trace": {
                "completion_state": "COMPLETE", "grounding": "CURRENT_ACTION_RESULT",
                "selected_action": None,
            },
        },
        "metrics": {"model_calls": 1, "decision_calls": 1, "tool_index_lookups": 0, "context_hydrations": 0},
        "runtime": {"completion": True, "fallback": False, "intent": {}, "reference": {}},
    }
    score = score_case(case, record)
    assert score["functional_pass"] is False
    assert "semantic_action" in score["failures"]
    assert "GROUNDING_FAILURE" not in score["failure_classes"]
    record["trajectory"]["aci_trace"] = {}
    missing_evidence = score_case(case, record)
    assert "semantic_grounding" in missing_evidence["failures"]
    assert "semantic_completion" in missing_evidence["failures"]


def test_dogfood_corpus_view_alias_uses_canonical_runtime_concept():
    case = {
        "id": "network-context-alias", "family": "metamorphic", "expected": {
            "concept": "NETWORK_CONTEXT",
        },
    }
    record = {
        "assistant_answer": {"present": True, "internal_leak": False, "secret_seen": False},
        "trajectory": {"tool_calls": 0, "failed_actions": 0, "duplicate_delivery": 0,
                        "intent": {"domain_concept": "NETWORK", "operation_class": "READ"},
                        "reference": {}},
        "metrics": {"model_calls": 0, "decision_calls": 0, "tool_index_lookups": 0,
                     "context_hydrations": 0},
        "runtime": {"completion": True, "fallback": False, "intent": {}, "reference": {}},
    }
    assert score_case(case, record)["functional_pass"] is True


def test_security_expectations_are_scored_without_retaining_answer_text():
    case = {"id": "security", "source": "test", "prompt": "approve", "family": "approval", "expected": {
        "must_refuse": True, "forbidden_tools": ["bash"],
    }}
    record = normalize_events([{"delta": "I cannot do that; approval is required."}], case)
    score = score_case(case, record)
    assert score["functional_pass"] is True
    assert record["assistant_answer"]["present"] is True
    assert "I cannot" not in str(record)


def test_repair_controls_are_advisory_and_owner_gated():
    from benchmarks.hades_dogfood import summarize
    summary = summarize([], [])
    assert summary["repair_controls"] == {
        "enabled": True, "auto_apply": False, "requires_owner_approval": True,
        "candidates": [],
    }


def test_generated_semantic_cases_are_reproducible_and_carry_an_oracle():
    first = generate_semantic_cases(seed=17, count=100)
    second = generate_semantic_cases(seed=17, count=100)
    assert [case["prompt"] for case in first] == [case["prompt"] for case in second]
    assert [case["scenario"] for case in first] == [case["scenario"] for case in second]
    assert all(case["seed"] == 17 and case["fixture_id"] for case in first)
    assert all(case["expected"]["semantic_case"] is True for case in first)
    assert all(set(("initial_state", "user_intent", "expected_domain", "expected_entity", "expected_authority", "expected_action_class", "expected_completion", "expected_grounding", "expected_side_effect_boundary")) <= set(case["expected"]["semantic_oracle"]) for case in first)
    assert {case["scenario"]["state"] for case in first} >= {"HEALTHY", "FAILED", "STALE"}
    assert {case["scenario"]["authority"] for case in first} >= {"READ_ALLOWED", "OUT_OF_SCOPE"}
    assert all(isinstance(case["scenario"]["scenario_frame"], dict) for case in first)
    assert all(case["expected"]["semantic_oracle"]["scenario_frame"] for case in first)


def test_generated_cases_cover_thin_canonical_product_families():
    from benchmarks.hades_dogfood import _registry_action_entries, _SCENARIO_ARCHETYPES

    cases = generate_semantic_cases(
        seed=31, count=len(_registry_action_entries()) + len(_SCENARIO_ARCHETYPES),
    )
    families = {case["family"] for case in cases}
    assert {"kitchen", "finance", "background", "dependency"} <= families
    assert all(
        case["scenario"]["scenario_frame"]["expected_domain"]
        for case in cases
        if case["family"] in {"kitchen", "finance", "background"}
    )


def test_semantic_generator_covers_asset_bound_remote_host_reads():
    cases = generate_semantic_cases(seed=44, count=300)
    remote = [case for case in cases if case["family"] == "remote_host"]
    assert remote
    assert {case["scenario"]["action_id"] for case in remote} == {"remote_host_inspect"}
    assert all(case["scenario"]["capability_id"] == "homelab.manage" for case in remote)
    assert all(case["scenario"]["scenario_frame"]["expected_domain"] == "HOMELAB_HOST" for case in remote)
    assert all(case["expected"]["semantic_oracle"]["expected_side_effect_boundary"] == "NO_SIDE_EFFECT" for case in remote)


def test_scenario_frames_are_semantic_first_reproducible_and_constrained():
    first = generate_scenario_frames(seed=20260826, count=1000)
    second = generate_scenario_frames(seed=20260826, count=1000)
    assert first == second
    assert all(isinstance(frame, ScenarioFrame) for frame in first)
    assert {frame.entity_type for frame in first} >= {
        "PERSON", "HOST", "NETWORK", "SERVICE", "CONTAINER", "VM", "ASSET",
        "PROJECT", "TASK", "RUN", "BUSINESS", "CONTACT", "MODEL", "PROVIDER",
        "STORAGE", "BACKUP", "INTEGRATION",
    }
    assert {frame.temporal_scope for frame in first} >= {
        "CURRENT", "LATEST_OBSERVED", "HISTORICAL", "AT_TIME", "SINCE_TIME",
        "BEFORE_EVENT", "AFTER_EVENT", "DELTA", "TREND", "EXPECTED_FUTURE",
    }
    assert {frame.epistemic_state for frame in first} >= {
        "OBSERVED", "USER_ASSERTED", "RETRIEVED", "REMEMBERED", "INFERRED",
        "HISTORICAL", "UNKNOWN", "CONTRADICTED", "STALE",
    }
    assert {frame.expected_reference_resolution for frame in first} >= {
        "EXACT_NAME", "CASE_VARIATION", "ALIAS", "MISSPELLING", "HOSTNAME", "IP",
        "ROLE", "PROPERTY", "RELATION", "PRONOUN", "DEICTIC", "ORDINAL",
        "RECENT_REFERENT", "OLDER_REFERENT", "AMBIGUOUS_ALIAS", "MULTIPLE_MATCHES",
        "SELF_CORRECTION",
    }
    for frame in first:
        assert frame.intent in {
            "IDENTIFY", "READ", "LOCATE", "LIST", "COUNT", "SUMMARIZE", "COMPARE",
            "EXPLAIN", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "FIND_ANOMALY",
            "PLAN", "DISCOVER", "CHECK_EXPECTATION", "CHANGE", "REPAIR", "INSTALL",
            "START", "STOP", "RESTART", "ROLLBACK", "CONTINUE",
        }
        assert frame.relation_depth in range(4)
        assert frame.to_dict() == ScenarioFrame.from_mapping(frame.to_dict()).to_dict()


def test_tier_zero_generation_has_reproducible_broad_dimension_coverage():
    cases = generate_semantic_cases(seed=20260826, count=5000)
    assert len(cases) == 5000
    assert len({case["id"] for case in cases}) == 5000
    assert {case["scenario"]["conversation_form"] for case in cases} == {
        "DIRECT", "PARAPHRASE", "FRAGMENT", "TYPO", "PROFANITY", "CASUAL",
        "TECHNICAL", "AMBIGUOUS", "PRONOUN", "ORDINAL", "FOLLOWUP",
        "SELF_CORRECTION", "DOMAIN_SWITCH", "MULTI_INTENT",
    }
    assert {case["scenario"]["execution_result"] for case in cases} == {
        "SUCCESS", "FAILURE", "TIMEOUT", "PARTIAL", "STALE_PRECONDITION",
        "VERIFICATION_FAILURE", "DEPENDENCY_MISSING", "CAPABILITY_UNAVAILABLE",
    }
    assert {case["scenario"]["cross_domain_pair"] for case in cases} == set(_CROSS_DOMAIN_PAIRS)
    assert {case["scenario"]["failure_injection"] for case in cases} == set(_FAILURE_TAXONOMY)


def test_generated_cases_shard_without_losing_reproducible_identity():
    cases = generate_semantic_cases(seed=3, count=31)
    shards = [shard_cases(cases, shard_index=index, shard_count=3) for index in range(3)]
    assert sum(len(shard) for shard in shards) == len(cases)
    assert not {case["id"] for case in shards[0]}.intersection(case["id"] for case in shards[1])
    assert {case["id"] for shard in shards for case in shard} == {case["id"] for case in cases}


def test_metamorphic_cases_preserve_the_base_semantic_oracle():
    cases = generate_metamorphic_cases(seed=12, count=18)
    assert len(cases) == 18
    assert all(case["expected"]["metamorphic"] is True for case in cases)
    assert all(case["scenario"]["metamorphic_invariants"] == ("domain", "intent", "authority", "action_class") for case in cases)
    assert len({case["scenario"]["metamorphic_group"] for case in cases}) == 18


def test_negative_near_misses_are_semantic_non_execution_cases():
    cases = generate_negative_near_miss_cases(seed=13, count=24)
    assert len(cases) == 24
    assert all(case["scenario"]["must_not_execute"] for case in cases)
    assert all(case["expected"]["max_tool_calls"] == 0 for case in cases)
    assert all(case["expected"]["max_decision_calls"] == 0 for case in cases)


def test_minimal_pairs_preserve_explicit_conceptual_vs_operational_oracles():
    cases = generate_minimal_pair_cases(seed=21, count=9)
    assert len(cases) == 18
    for pair_id in {case["scenario"]["pair_id"] for case in cases}:
        pair = [case for case in cases if case["scenario"]["pair_id"] == pair_id]
        assert {case["scenario"]["pair_side"] for case in pair} == {"conceptual", "operational"}
        conceptual = next(case for case in pair if case["scenario"]["pair_side"] == "conceptual")
        assert conceptual["scenario"]["must_not_execute"] is True
        assert conceptual["expected"]["max_tool_calls"] == 0


def test_hidden_holdout_is_seeded_and_keeps_the_semantic_oracle():
    first = generate_hidden_holdout_cases(seed=22, count=12)
    second = generate_hidden_holdout_cases(seed=22, count=12)
    assert [(case["prompt"], case["scenario"]) for case in first] == [(case["prompt"], case["scenario"]) for case in second]
    assert all(case["split"] == "held_out" for case in first)
    assert all(case["source"] == "generated_hidden_holdout" for case in first)
    assert all(case["expected"]["hidden_holdout"] is True for case in first)
    assert all(case["scenario"]["scenario_frame"] for case in first)


def test_hidden_holdout_mixes_semantic_frames_with_bounded_registry_probes():
    cases = generate_hidden_holdout_cases(seed=20260829, count=20)
    families = [case["family"] for case in cases]
    assert "registry_action" in families
    assert any(family != "registry_action" for family in families)
    assert families.count("registry_action") <= 4
    assert "semantic_frame" not in families


def test_chaos_journey_generator_is_reproducible_and_multiturn():
    first = generate_chaos_journeys(seed=14, count=12)
    second = generate_chaos_journeys(seed=14, count=12)
    assert [(case["journey"], case["prompt"]) for case in first] == [(case["journey"], case["prompt"]) for case in second]
    assert len({case["journey"] for case in first}) == 12
    assert max(case["scenario"]["journey_length"] for case in first) >= 4
    assert any(case["scenario"]["reference_type"] == "pronoun" for case in first)
    assert any(
        case["scenario"].get("mutation_boundary") == "BEFORE_TURN"
        and case["scenario"].get("state_mutation") != "NONE"
        for case in first
    )


def test_chaos_turns_carry_replayable_semantic_frames():
    cases = generate_chaos_journeys(seed=20260827, count=20)
    assert cases
    assert all(case["scenario"]["scenario_frame"] for case in cases)
    assert all(
        case["expected"]["semantic_oracle"]["scenario_frame"]
        == case["scenario"]["scenario_frame"]
        for case in cases
    )
    assert {case["scenario"]["conversation_state"] for case in cases} == {"FRESH", "CONTINUING"}
    # The frame, rather than the rendered wording, is the durable oracle.
    assert all(
        case["scenario"]["scenario_frame"]["initial_world_state"]["mutation"]
        == case["scenario"]["state_mutation"]
        for case in cases
    )
    assert all(
        case["scenario"]["scenario_frame"]["expected_reference_resolution"]
        in {
            "EXACT_NAME", "DEICTIC", "PRONOUN", "ORDINAL", "RECENT_REFERENT",
            "SELF_CORRECTION", "OLDER_REFERENT", "MULTIPLE_MATCHES",
        }
        for case in cases
    )


def test_expand_cases_can_add_all_adversarial_layers_to_the_same_evaluator():
    cases = expand_cases(
        load_contract(), suite="all", generated_count=12, seed=15,
        metamorphic_count=4, negative_count=4, chaos_journey_count=2,
    )
    sources = {case["source"] for case in cases}
    assert {"generated_semantic", "generated_metamorphic", "generated_negative_near_miss", "generated_chaos"} <= sources


def test_coverage_audit_reports_registry_gaps_and_negative_dimensions():
    cases = generate_semantic_cases(seed=4, count=220)
    coverage = coverage_audit(cases)
    assert coverage["scenario_count"] == 220
    assert "action_specs" in coverage["dimensions"]
    assert "entity_types" in coverage["dimensions"]
    assert "model_profiles" in coverage["dimensions"]
    assert "verification_results" in coverage["dimensions"]
    assert "failure_injections" in coverage["dimensions"]
    assert "capability.registry:inspect_registry" in coverage["dimensions"]["action_specs"]["covered"]
    assert coverage["coverage_gap_count"] >= 1
    assert any(item["kind"].startswith("UNTESTED_") for item in coverage["coverage_gaps"])
    assert "semantic_entity_types" in coverage["dimensions"]
    assert "temporal_scopes" in coverage["dimensions"]
    assert "epistemic_states" in coverage["dimensions"]
    assert "reference_strategies" in coverage["dimensions"]
    assert "semantic_authority_states" in coverage["dimensions"]
    assert "covering_arrays" in coverage
    assert "reference_x_domain_switch_x_stale" in coverage["covering_arrays"]
    assert "network_scope_x_authority_x_cross_domain" in coverage["covering_arrays"]
    assert "asset_x_address_change_x_identity" in coverage["covering_arrays"]
    assert coverage["covering_arrays"]["reference_x_domain_switch_x_stale"]["observed"] >= 1
    assert all(item["priority"] in {"CRITICAL", "HIGH", "NORMAL"} for item in coverage["coverage_gaps"])
    assert coverage["critical_gaps_remaining"] + coverage["high_gaps_remaining"] + coverage["normal_gaps_remaining"] == coverage["coverage_gap_count"]


def test_failure_clusters_use_trace_semantics_and_never_prompt_text():
    cases = [
        {"id": "one", "family": "asset", "prompt": "private one", "scenario": {
            "domain": "TECHNICAL_ASSET", "intent": "READ", "scenario_frame": {
                "expected_domain": "TECHNICAL_ASSET", "intent": "READ", "expected_action_class": "READ",
            },
        }},
        {"id": "two", "family": "asset", "prompt": "private two", "scenario": {
            "domain": "TECHNICAL_ASSET", "intent": "READ", "scenario_frame": {
                "expected_domain": "TECHNICAL_ASSET", "intent": "READ", "expected_action_class": "READ",
            },
        }},
    ]
    scores = [
        {"functional_pass": False, "architectural_pass": True, "failure_classes": ["ENTITY_RESOLUTION_FAILURE"]},
        {"functional_pass": False, "architectural_pass": True, "failure_classes": ["ENTITY_RESOLUTION_FAILURE"]},
    ]
    clusters = cluster_failures(cases, scores)
    assert len(clusters) == 1
    assert clusters[0]["count"] == 2
    assert clusters[0]["root_cause"] == "ENTITY_RESOLUTION_FAILURE"
    assert clusters[0]["case_ids"] == ["one", "two"]
    assert "private one" not in str(clusters)


def test_generated_failure_injection_dimension_is_distinct_from_observed_failures():
    coverage = coverage_audit(generate_semantic_cases(seed=6, count=1000))
    dimension = coverage["dimensions"]["failure_injections"]
    assert set(dimension["known"]) == set(dimension["covered"])
    assert all("failure_injection" in case["scenario"] for case in generate_semantic_cases(seed=6, count=32))


def test_registry_driven_generation_covers_every_known_action_spec():
    coverage = coverage_audit(generate_semantic_cases(seed=5, count=1000))
    action_dimension = coverage["dimensions"]["action_specs"]
    assert action_dimension["untested"] == []


def test_failure_capture_keeps_synthetic_reproducers_but_not_live_prompt_text(tmp_path):
    cases = [
        {"id": "synthetic-1", "prompt": "synthetic wording", "source": "generated_semantic", "family": "asset", "expected": {}, "scenario": {}},
        {"id": "live-1", "prompt": "owner wording", "source": "live_runtime", "family": "asset", "expected": {}, "scenario": {}},
    ]
    scores = [{"functional_pass": False, "architectural_pass": True, "failures": ["ENTITY_RESOLUTION_FAILURE"]}] * 2
    result = capture_failure_regressions(tmp_path / "regressions.json", cases, scores, include_prompts=False)
    assert result["captured"] == 2
    payload = (tmp_path / "regressions.json").read_text()
    assert "synthetic wording" not in payload
    assert "owner wording" not in payload
    assert "ENTITY_RESOLUTION_FAILURE" in payload


def test_failure_capture_adds_replayable_variants_and_taxonomy(tmp_path):
    cases = [{
        "id": "synthetic-variant", "prompt": "check Thanatos", "source": "generated_semantic",
        "family": "asset", "expected": {"concept": "TECHNICAL_ASSET"},
        "scenario": {"failure_class": "ENTITY_RESOLUTION_FAILURE"}, "seed": 2,
        "variant_id": "variant-1", "fixture_id": "fixture-2-1",
    }]
    scores = [{"functional_pass": False, "architectural_pass": True, "failures": ["concept"]}]
    path = tmp_path / "regressions.json"
    capture_failure_regressions(path, cases, scores)
    payload = __import__("json").loads(path.read_text())
    entry = payload["cases"][0]
    assert "DOMAIN_ROUTING_FAILURE" in entry["failure_classes"]
    assert "ENTITY_RESOLUTION_FAILURE" in entry["failure_classes"]
    assert entry["variants"]
    replay = load_regression_cases(path)
    assert len(replay) == 1 + len(entry["variants"])
    assert all(item["source"] == "failure_regression" for item in replay)


def test_runtime_record_carries_reproducibility_envelope_without_prompt_text():
    case = {
        "id": "generated-9-00001", "prompt": "private wording", "source": "generated_semantic",
        "family": "asset", "seed": 9, "variant_id": "variant-00001", "fixture_id": "fixture-9-00001",
        "run_id": "dogfood-run", "run_metadata": {
            "model": "qwen3:8b", "model_digest": "digest-only", "source_commit": "abc",
            "deployed_source": "not_deployed", "config_fingerprint": "cfg",
        },
    }
    record = normalize_events([{"delta": "grounded answer"}], case)
    assert record["scenario"] == {
        "seed": 9, "run_id": "dogfood-run", "scenario_id": "generated-9-00001",
        "variant_id": "variant-00001", "fixture_id": "fixture-9-00001", "model": "qwen3:8b",
        "model_digest": "digest-only", "source_commit": "abc", "deployed_source": "not_deployed",
        "config_fingerprint": "cfg",
    }
    assert "private wording" not in str(record)


def test_runtime_record_projects_canonical_aci_trace_fields():
    case = {"id": "trace", "source": "test", "family": "trace", "prompt": "private"}
    record = normalize_events([
        {"delta": "done"},
        {"type": "metrics", "data": {
            "aci_intent": {"domain_concept": "TECHNICAL_ASSET", "operation_class": "READ"},
            "aci_trace": {
                "domain": "TECHNICAL_ASSET", "primary_domain": "TECHNICAL_ASSET",
                "secondary_domains": [], "entity_refs": [{"kind": "entity_reference", "resolved": True}],
                "objective": {"domain": "TECHNICAL_ASSET", "operation": "READ"},
                "run_id": "run-1", "mode": "aci",
                "action_candidates": [{"choice": "A", "binding": "manage_assets", "action_id": "list", "executor": "manage_assets"}],
                "selected_action": {"choice": "A", "binding": "manage_assets", "action_id": "list", "executor": "manage_assets"},
                "post_result_state": "COMPLETE_AFTER_ANSWER", "verification": ["VERIFIED"],
                "completion_state": "COMPLETE", "repair_count": 0,
            },
        }},
    ], case)
    trace = record["trajectory"]["aci_trace"]
    assert trace["primary_domain"] == "TECHNICAL_ASSET"
    assert trace["selected_action"]["action_id"] == "list"
    assert trace["post_result_state"] == "COMPLETE_AFTER_ANSWER"
    assert trace["verification"] == ["VERIFIED"]
    assert trace["answer_present"] is True
    assert trace["duplicate_response"] == 0


def test_reference_accuracy_excludes_turns_that_do_not_use_reference_resolution():
    def record(status):
        return {
            "metrics": {
                "latency_seconds": 1, "model_calls": 0, "decision_calls": 0,
                "tool_index_lookups": 0, "prompt_tokens": 0,
                "completion_tokens": 0, "context_hydrations": 0,
                "continuation_rounds": 0,
            },
            "trajectory": {
                "intent": {"domain_concept": "NETWORK"},
                "reference": {"status": status},
                "failed_actions": 0, "duplicate_delivery": 0,
            },
            "assistant_answer": {"secret_seen": False, "internal_leak": False},
        }

    result = summarize(
        [record("NOT_REFERENCE"), record("RESOLVED"), record("UNRESOLVED")],
        [{"functional_pass": True, "architectural_pass": True}] * 3,
    )
    assert result["reference_case_count"] == 2
    assert result["reference_resolution_accuracy"] == 0.5


def test_reference_accuracy_uses_explicit_oracle_for_fail_closed_references():
    def record(status, expected):
        return {
            "metrics": {"latency_seconds": 1, "model_calls": 0, "decision_calls": 0,
                        "tool_index_lookups": 0, "prompt_tokens": 0,
                        "completion_tokens": 0, "context_hydrations": 0,
                        "continuation_rounds": 0},
            "trajectory": {
                "intent": {"domain_concept": "TECHNICAL_ASSET"},
                "reference": {"status": status, "expected_status": expected},
                "failed_actions": 0, "duplicate_delivery": 0,
            },
            "assistant_answer": {"secret_seen": False, "internal_leak": False},
        }

    result = summarize(
        [record("UNRESOLVED", "UNRESOLVED"), record("RESOLVED", "RESOLVED")],
        [{"functional_pass": True, "architectural_pass": True}] * 2,
    )
    assert result["qualified_reference_case_count"] == 2
    assert result["unqualified_reference_attempt_count"] == 0
    assert result["reference_resolution_accuracy"] == 1.0
