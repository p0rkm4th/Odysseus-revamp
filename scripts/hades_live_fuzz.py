#!/usr/bin/env python3
"""Authenticated, sanitized live ACI fuzz runner.

This is deliberately a client of the ordinary authentication and chat APIs.
It never mints a session token, sends an internal-tool header, disables auth,
or calls an Action handler directly.  A disposable acceptance deployment may
be bootstrapped through the normal first-run setup route; the actual fuzz
principal is then created through the normal admin user route and logged in
through the normal login route.

The runner is safe to point at an already configured acceptance deployment by
passing credentials for its synthetic ``hades-acceptance`` user.  Bootstrap is
refused for non-loopback URLs and the authenticated username is checked before
any chat request is sent, so a production owner's account cannot be used by
accident.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import secrets
import sys
import time
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

import requests

from scripts.hades_live_dogfood import (
    CASES,
    Case,
    assert_case,
    create_session,
    run_case,
    select_cases,
)


ACCEPTANCE_USER = "hades-acceptance"
BOOTSTRAP_ADMIN = "hades-acceptance-bootstrap"
MIN_PASSWORD_LENGTH = 12


def _is_loopback_url(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _password() -> str:
    # Kept in memory only.  The generated value is never printed or written to
    # the report; it exists solely for the normal setup/login exchange.
    return secrets.token_urlsafe(24)


def _json(response: requests.Response, expected: tuple[int, ...] = (200,)) -> dict[str, Any]:
    if response.status_code not in expected:
        raise RuntimeError(f"HTTP {response.status_code} from {response.request.method} {response.request.url}")
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError("authentication endpoint returned a non-object response")
    return value


def login(session: requests.Session, base_url: str, username: str, password: str) -> None:
    response = session.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password, "remember": False},
        timeout=30,
    )
    body = _json(response)
    if body.get("ok") is not True:
        raise RuntimeError("normal login did not establish a session")


def bootstrap_acceptance_user(session: requests.Session, base_url: str) -> tuple[str, str]:
    """Create an isolated non-admin acceptance user through normal auth APIs."""
    if not _is_loopback_url(base_url):
        raise RuntimeError("--bootstrap is permitted only for loopback acceptance deployments")
    admin_password = _password()
    acceptance_password = _password()
    setup = session.post(
        f"{base_url}/api/auth/setup",
        json={"username": BOOTSTRAP_ADMIN, "password": admin_password},
        timeout=30,
    )
    _json(setup)
    # Setup does not issue a token; authenticate the bootstrap controller using
    # the same public login flow a real operator uses.
    login(session, base_url, BOOTSTRAP_ADMIN, admin_password)
    created = session.post(
        f"{base_url}/api/auth/users",
        json={"username": ACCEPTANCE_USER, "password": acceptance_password, "is_admin": False},
        timeout=30,
    )
    _json(created)
    # Use only the least-privileged synthetic identity for the actual run.
    session.cookies.clear()
    login(session, base_url, ACCEPTANCE_USER, acceptance_password)
    return ACCEPTANCE_USER, acceptance_password


def authenticate(
    session: requests.Session,
    base_url: str,
    *,
    username: str,
    password: str | None,
    bootstrap: bool,
) -> str:
    if username != ACCEPTANCE_USER:
        raise RuntimeError(f"live fuzz principal must be {ACCEPTANCE_USER!r}")
    if bootstrap:
        username, _ = bootstrap_acceptance_user(session, base_url)
    else:
        if not password:
            raise RuntimeError("--password or HADES_ACCEPTANCE_PASSWORD is required without --bootstrap")
        login(session, base_url, username, password)
    status = _json(session.get(f"{base_url}/api/auth/status", timeout=30))
    if status.get("authenticated") is not True or status.get("username") != ACCEPTANCE_USER:
        raise RuntimeError("authenticated principal is not the isolated acceptance user")
    return username


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def compositional_variants(seed: int = 0) -> tuple[Case, ...]:
    """Create held-out language variants from semantic families, not rules.

    These are test inputs only.  No generated phrase is imported by runtime
    intent routing.  Each variant retains the oracle of its unambiguous source
    case, while near-misses remain represented by the existing negative cases.
    """
    rng = random.Random(seed)
    dimensions = {
        "memory_1": [
            "okay so what do you know about me",
            "whatcha know about me",
            "what do you remember ab me",
            "give me a rundown on me",
        ],
        "work_1": [
            "whats on my plate rn",
            "alright what am i working on again",
            "what projects have i got going",
        ],
        "assets_list": [
            "what machines do i actually own",
            "show me my computer stuff",
            "what boxes have i got",
        ],
        "network_1": [
            "where am i connected",
            "what wifi am i on right now",
            "whats the current network context",
        ],
        "infra_running": [
            "whats running",
            "hows the stack doing",
            "what services are up right now",
        ],
        "fallback_1": [
            "why isn't RAID a backup, exactly",
            "explain containers versus virtual machines",
            "what makes a useful personal AI",
        ],
    }
    by_name = {case.name: case for case in CASES}
    generated: list[Case] = []
    for source_name, prompts in dimensions.items():
        source = by_name[source_name]
        for index, prompt in enumerate(prompts, 1):
            generated.append(replace(
                source,
                name=f"fuzz_{source_name}_{index}",
                prompt=prompt,
                split="held_out",
                mode="fresh",
                group=None,
            ))
    rng.shuffle(generated)
    return tuple(generated)


def _cookie(session: requests.Session) -> str:
    value = session.cookies.get("odysseus_session")
    if not value:
        raise RuntimeError("normal login returned no session cookie")
    return value


def run(
    *,
    base_url: str,
    model: str,
    endpoint_id: str,
    username: str,
    password: str | None,
    bootstrap: bool,
    suite: str,
    sample: int | None,
    seed: int,
    output: str,
) -> int:
    base_url = base_url.rstrip("/")
    http = requests.Session()
    authenticate(http, base_url, username=username, password=password, bootstrap=bootstrap)
    cookie = _cookie(http)
    cases = list(CASES) + list(compositional_variants(seed))
    selected = select_cases(cases, suite=suite, sample=sample, seed=seed)
    results: list[dict[str, Any]] = []
    sessions: dict[str, str] = {}
    for case in selected:
        if case.mode == "continuation" and case.group:
            session_id = sessions.get(case.group)
            if session_id is None:
                session_id = create_session(base_url, cookie, f"ACI fuzz {case.group}", model=model, endpoint_id=endpoint_id)
                sessions[case.group] = session_id
        else:
            session_id = create_session(base_url, cookie, f"ACI fuzz {case.name}", model=model, endpoint_id=endpoint_id)
        try:
            result = run_case(base_url, cookie, session_id, case)
            result["assertion_failures"] = assert_case(case, result)
        except Exception as exc:  # sanitized failure; continue the matrix
            result = {
                "case": case.name,
                "prompt_digest": _digest(case.prompt),
                "session_mode": case.mode,
                "session_group": case.group,
                "family": case.family,
                "split": case.split,
                "session_digest": _digest(session_id),
                "answer_present": False,
                "assertion_failures": ["transport_error"],
                "error": type(exc).__name__,
            }
        results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)
    summary = {
        "acceptance_principal": ACCEPTANCE_USER,
        "suite": suite,
        "seed": seed,
        "case_count": len(results),
        "trajectory_pass": sum(not item.get("assertion_failures") for item in results),
        "answers": sum(bool(item.get("answer_present")) for item in results),
        "internal_leaks": sum(bool(item.get("internal_leak")) for item in results),
        "model_calls": sum(int(item.get("model_calls") or 0) for item in results),
        "tool_index_lookups": sum(int(item.get("tool_index_lookup") or 0) for item in results),
        "generated_variant_count": len(compositional_variants(seed)),
    }
    with open(output, "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "results": results}, handle, indent=2, sort_keys=True)
    print(json.dumps({"summary": summary, "output": output}, sort_keys=True))
    return 0 if summary["trajectory_pass"] == summary["case_count"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("HADES_LIVE_BASE_URL", "http://127.0.0.1:7000"))
    parser.add_argument("--model", default=os.environ.get("HADES_LIVE_MODEL", "qwen3:8b"))
    parser.add_argument("--endpoint-id", default=os.environ.get("HADES_LIVE_ENDPOINT_ID", "e4e4196b"))
    parser.add_argument("--username", default=ACCEPTANCE_USER)
    parser.add_argument("--password", default=os.environ.get("HADES_ACCEPTANCE_PASSWORD"))
    parser.add_argument("--bootstrap", action="store_true", help="use normal first-run setup on an isolated unconfigured loopback instance")
    parser.add_argument("--suite", choices=("all", "core", "held_out", "rotating", "security"), default="all")
    parser.add_argument("--sample", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", default="/tmp/hades-live-fuzz.json")
    args = parser.parse_args()
    try:
        return run(
            base_url=args.base_url,
            model=args.model,
            endpoint_id=args.endpoint_id,
            username=args.username,
            password=args.password,
            bootstrap=args.bootstrap,
            suite=args.suite,
            sample=args.sample,
            seed=args.seed,
            output=args.output,
        )
    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
        print(f"hades-live-fuzz: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
