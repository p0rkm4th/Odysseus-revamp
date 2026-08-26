import pytest

from scripts.hades_live_fuzz import (
    ACCEPTANCE_USER,
    _is_loopback_url,
    authenticate,
    compositional_variants,
)


def test_bootstrap_is_loopback_only():
    assert _is_loopback_url("http://127.0.0.1:7000")
    assert _is_loopback_url("http://localhost:7000")
    assert not _is_loopback_url("https://hades.example.test")


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
