import pytest

from scripts.hades_live_fuzz import (
    ACCEPTANCE_USER,
    _is_loopback_url,
    _acceptance_password,
    authenticate,
    bootstrap_acceptance_user,
    compositional_variants,
)
from scripts.hades_live_dogfood import Case, select_cases


def test_bootstrap_is_loopback_only():
    assert _is_loopback_url("http://127.0.0.1:7000")
    assert _is_loopback_url("http://localhost:7000")
    assert not _is_loopback_url("https://hades.example.test")


def test_bootstrap_acceptance_password_can_be_reused_from_test_environment(monkeypatch):
    monkeypatch.setenv("HADES_ACCEPTANCE_PASSWORD", "synthetic-acceptance-password")
    assert _acceptance_password() == "synthetic-acceptance-password"


def test_bootstrap_acceptance_password_rejects_short_configured_secret(monkeypatch):
    monkeypatch.setenv("HADES_ACCEPTANCE_PASSWORD", "too-short")
    with pytest.raises(ValueError, match="at least"):
        _acceptance_password()


def test_compositional_variants_are_test_data_not_duplicate_runtime_cases():
    variants = compositional_variants(123)
    assert len(variants) >= 15
    assert all(case.split == "held_out" for case in variants)
    assert all(case.name.startswith("fuzz_") for case in variants)
    assert {case.prompt for case in variants}
    assert not ({case.name for case in variants} & {"memory_1", "work_1"})
    assert [case.prompt for case in variants] == [
        case.prompt for case in compositional_variants(123)
    ]


class _Response:
    def __init__(self, status=200, body=None, request=None):
        self.status_code = status
        self._body = body or {}
        self.request = request

    def json(self):
        return self._body


class _Session:
    def __init__(self, status_body=None):
        self.calls = []
        self.cookies = {"odysseus_session": "synthetic-session"}
        self.status_body = status_body or {
            "authenticated": True,
            "username": ACCEPTANCE_USER,
        }

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return _Response(body={"ok": True})

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return _Response(body=self.status_body)


def test_bootstrap_uses_configured_admin_for_entrypoint_provisioned_instance(monkeypatch):
    session = _Session({"configured": True})
    monkeypatch.setenv("ODYSSEUS_ADMIN_USER", "admin")
    monkeypatch.setattr("scripts.hades_live_fuzz._acceptance_password", lambda: "synthetic-password")
    user, password, endpoint_id = bootstrap_acceptance_user(
        session, "http://127.0.0.1:7000",
        bootstrap_admin_password="admin-password",
        model_endpoint_url=None,
    )
    assert (user, password, endpoint_id) == (ACCEPTANCE_USER, "synthetic-password", "")
    login_payload = session.calls[1][2]["json"]
    assert login_payload["username"] == "admin"


def test_authenticate_uses_normal_login_and_checks_synthetic_principal():
    session = _Session()
    assert authenticate(
        session,
        "http://127.0.0.1:7000",
        username=ACCEPTANCE_USER,
        password="synthetic-password",
        bootstrap=False,
    )[0] == ACCEPTANCE_USER
    assert [method for method, _, _ in session.calls] == ["POST", "GET"]
    assert session.calls[0][1].endswith("/api/auth/login")


def test_authenticate_rejects_non_acceptance_principal():
    with pytest.raises(RuntimeError, match="principal"):
        authenticate(
            _Session({"authenticated": True, "username": "real-owner"}),
            "http://127.0.0.1:7000",
            username=ACCEPTANCE_USER,
            password="synthetic-password",
            bootstrap=False,
        )


def test_authenticate_rejects_real_owner_username_before_network_call():
    session = _Session()
    with pytest.raises(RuntimeError, match="principal"):
        authenticate(
            session,
            "http://127.0.0.1:7000",
            username="scootz",
            password="not-used",
            bootstrap=False,
        )
    assert session.calls == []


def test_bootstrap_rejects_non_loopback_before_setup():
    with pytest.raises(RuntimeError, match="loopback"):
        authenticate(
            _Session(),
            "https://hades.example.test",
            username=ACCEPTANCE_USER,
            password=None,
            bootstrap=True,
        )


def test_sampled_declared_trajectory_keeps_reference_prerequisite():
    cases = [
        Case("asset_list", "what computers do i have", "continuation", "assets"),
        Case(
            "asset_first", "tell me about the first one", "continuation", "assets",
            expect_reference="TECHNICAL_ASSET",
        ),
        Case("unrelated", "what is a network?"),
    ]

    selected = select_cases(cases, sample=1, seed=1)

    assert [case.name for case in selected] == ["asset_list", "asset_first"]
    assert selected[0].group == selected[1].group == "assets"


def test_sampled_declared_selection_is_reproducible_and_does_not_add_later_turns():
    cases = [
        Case("start", "review work", "continuation", "work"),
        Case("followup", "continue", "continuation", "work"),
        Case("other", "what is dns?"),
    ]

    first = select_cases(cases, sample=1, seed=3)
    second = select_cases(cases, sample=1, seed=3)

    assert [case.name for case in first] == [case.name for case in second]
    if any(case.name == "followup" for case in first):
        assert any(case.name == "start" for case in first)


def test_fresh_sampling_does_not_claim_reference_context_exists():
    cases = [
        Case("asset_list", "what computers do i have", "continuation", "assets"),
        Case(
            "asset_first", "tell me about the first one", "continuation", "assets",
            expect_reference="TECHNICAL_ASSET",
        ),
    ]

    selected = select_cases(cases, sample=2, seed=0, session_mode="fresh")

    assert len(selected) == 1
    assert selected[0].name == "asset_list"
    assert selected[0].mode == "fresh"
    assert selected[0].group is None
