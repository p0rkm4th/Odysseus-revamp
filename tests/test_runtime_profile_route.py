from pathlib import Path


def test_runtime_profile_route_is_owner_scoped_and_sanitized():
    source = Path("routes/intelligence_routes.py").read_text(encoding="utf-8")
    assert '@router.get("/api/hades/runtime-profile")' in source
    assert "value = owner(request)" in source
    assert '"authority_unchanged": True' in source
    assert "RuntimeProfileCache().all()" in source
    assert '"negotiated_decision_protocol"' in source
