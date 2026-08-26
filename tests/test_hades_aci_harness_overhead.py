from benchmarks.hades_aci_harness_overhead import _local_endpoint


def test_overhead_report_source_records_model_and_context_attribution():
    from pathlib import Path
    source = Path("benchmarks/hades_aci_harness_overhead.py").read_text(encoding="utf-8")
    for field in (
        "model_calls", "model_wait_seconds", "context_construction_breakdown",
        "prompt_token_delta", "non_prep_overhead_seconds",
    ):
        assert field in source


def test_harness_overhead_benchmark_only_accepts_recognized_local_endpoints():
    assert _local_endpoint("http://127.0.0.1:11434") is True
    assert _local_endpoint("http://172.18.0.1:11434") is True
    assert _local_endpoint("https://example.invalid") is False
