from benchmarks.hades_aci_harness_overhead import _local_endpoint, output_accounting, timing_attribution


def test_overhead_report_source_records_model_and_context_attribution():
    from pathlib import Path
    source = Path("benchmarks/hades_aci_harness_overhead.py").read_text(encoding="utf-8")
    for field in (
        "model_calls", "model_wait_seconds", "context_construction_breakdown",
        "prompt_token_delta", "non_prep_overhead_seconds",
        "extra_model_inference_seconds", "framework_overhead_seconds",
        "max_tokens", "num_predict",
        "output_accounting", "consistent", "implausible",
        "--prompt", "args.prompt",
    ):
        assert field in source


def test_timing_attribution_separates_provider_inference_from_framework():
    result = timing_attribution(
        {"completion_seconds": 0.23},
        {"completion_seconds": 5.28, "context_construction_seconds": 1.50, "response_time_seconds": 3.78},
    )
    assert result == {
        "total_harness_overhead_seconds": 5.05,
        "extra_model_inference_seconds": 3.55,
        "framework_overhead_seconds": 0.0,
    }


def test_harness_overhead_benchmark_only_accepts_recognized_local_endpoints():
    assert _local_endpoint("http://127.0.0.1:11434") is True
    assert _local_endpoint("http://172.18.0.1:11434") is True
    assert _local_endpoint("https://example.invalid") is False


def test_output_accounting_rejects_implausible_stream_usage_mismatch():
    result = output_accounting(
        {"output_tokens": 3, "output_chars": 2},
        {"output_tokens": 3, "output_chars": 144},
    )
    assert result == {"consistent": False, "reason": "hades_text_token_ratio implausible"}


def test_output_accounting_separates_framework_fallback_text():
    result = output_accounting(
        {"output_tokens": 3, "output_chars": 2},
        {"output_tokens": 3, "output_chars": 99, "aci_empty_answer_fallback": True},
    )
    assert result == {"consistent": False, "reason": "hades_framework_generated_fallback"}
