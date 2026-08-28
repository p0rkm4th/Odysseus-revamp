from benchmarks.jarvis.collector import SyntheticRunCollector


def test_collector_preserves_sanitized_model_burden_projection():
    case = {"id": "synthetic", "expected": {}}
    collector = SyntheticRunCollector(case, {"name": "qwen3:8b"}, {"os": "test"})
    collector.consume({
        "type": "metrics",
        "data": {
            "model_burden": {
                "framework": 2,
                "model": 1,
                "total": 3,
                "model_ratio": 0.3333,
                "labels": {
                    "framework": {"intent_resolution": 1},
                    "model": {"bounded_action_decision": 1},
                    "secret": {"value": "must not be retained"},
                },
            }
        },
    })
    burden = collector.finish()["metrics"]["model_burden"]
    assert burden["framework"] == 2
    assert burden["model"] == 1
    assert "secret" not in burden["labels"]


def test_collector_marks_provider_fallback_as_recovery():
    collector = SyntheticRunCollector(
        {"id": "continuity", "expected": {"requires_recovery": True}},
        {"name": "qwen3:8b"},
        {"os": "test"},
    )
    collector.consume({"type": "fallback", "answered_by": "qwen3:8b"})
    record = collector.finish()
    assert record["recovered"] is True
    assert record["metrics"]["retries"] == 1
