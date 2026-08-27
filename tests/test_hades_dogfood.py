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
    generate_chaos_journeys,
    load_regression_cases,
    load_contract,
    normalize_events,
    summarize,
    shard_cases,
    score_case,
    _CROSS_DOMAIN_PAIRS,
    _FAILURE_TAXONOMY,
)


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
    cases = generate_semantic_cases(seed=31, count=180)
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


def test_chaos_journey_generator_is_reproducible_and_multiturn():
    first = generate_chaos_journeys(seed=14, count=12)
    second = generate_chaos_journeys(seed=14, count=12)
    assert [(case["journey"], case["prompt"]) for case in first] == [(case["journey"], case["prompt"]) for case in second]
    assert len({case["journey"] for case in first}) == 12
    assert max(case["scenario"]["journey_length"] for case in first) >= 4
    assert any(case["scenario"]["reference_type"] == "pronoun" for case in first)


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
