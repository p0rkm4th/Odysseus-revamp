import json

from src.aci import ContextEnvelope
from src.runtime_profile import (
    CapabilityEvidence,
    RuntimeCapabilityProfile,
    RuntimeProfileCache,
    runtime_profile_key,
    select_evidence,
)


def test_runtime_key_separates_protocol_runtime_and_model_fingerprint():
    a = runtime_profile_key(endpoint_id="local", protocol="openai-chat", runtime="ollama", model_id="qwen3:8b", model_digest="a")
    b = runtime_profile_key(endpoint_id="local", protocol="openai-chat", runtime="llama.cpp", model_id="qwen3:8b", model_digest="a")
    c = runtime_profile_key(endpoint_id="local", protocol="openai-chat", runtime="ollama", model_id="qwen3:8b", model_digest="b")
    assert len(a) == 32
    assert len({a, b, c}) == 3


def test_evidence_precedence_prefers_probe_over_heuristic_and_fresh_tie():
    old = CapabilityEvidence(status="pass", source="heuristic", tested_at=99)
    probe = CapabilityEvidence(status="fail", source="capability_probe", tested_at=1)
    assert select_evidence(old, probe) is probe
    fresh = CapabilityEvidence(status="pass", source="capability_probe", tested_at=2)
    assert select_evidence(probe, fresh) is fresh


def test_profile_cache_round_trip_and_ttl(tmp_path):
    profile = RuntimeCapabilityProfile(
        endpoint_id="local", protocol="openai-chat", runtime="ollama", model_id="qwen3:8b",
        architecture_max_context=40960, runtime_allocated_context=8192,
        capabilities={"structured_json": CapabilityEvidence(status="pass", source="capability_probe", tested_at=10)},
        refreshed_at=100, ttl_seconds=20,
    )
    cache = RuntimeProfileCache(tmp_path / "profiles.json")
    cache.save(profile)
    loaded = cache.load(profile.key)
    assert loaded is not None
    assert loaded.supports("structured_json")
    assert loaded.is_fresh(119)
    assert not loaded.is_fresh(121)
    assert json.loads((tmp_path / "profiles.json").read_text())


def test_context_envelope_uses_runtime_allocation_not_architecture_maximum():
    profile = RuntimeCapabilityProfile(
        endpoint_id="local", protocol="openai-chat", runtime="ollama", model_id="qwen3:8b",
        architecture_max_context=40960, runtime_allocated_context=8192,
    )
    envelope = ContextEnvelope.from_runtime_profile(profile, aci_profile_target=6000, reserved_output_budget=512)
    assert envelope.effective_context == 6512
