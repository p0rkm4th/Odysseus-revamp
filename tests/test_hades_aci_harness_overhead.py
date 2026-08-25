from benchmarks.hades_aci_harness_overhead import _local_endpoint


def test_harness_overhead_benchmark_only_accepts_recognized_local_endpoints():
    assert _local_endpoint("http://127.0.0.1:11434") is True
    assert _local_endpoint("http://172.18.0.1:11434") is True
    assert _local_endpoint("https://example.invalid") is False
