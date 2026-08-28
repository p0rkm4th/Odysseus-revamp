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
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

# Support both ``python -m scripts.hades_live_fuzz`` and the documented direct
# script invocation.  The latter otherwise puts only ``scripts/`` on
# sys.path, making the existing production-path canary module unimportable.
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.hades_live_dogfood import (
    CASES,
    Case,
    assert_case,
    create_session,
    run_case,
    select_cases,
)


from core.auth import ACCEPTANCE_USERNAME

ACCEPTANCE_USER = ACCEPTANCE_USERNAME
BOOTSTRAP_ADMIN = "hades-acceptance-bootstrap"
MIN_PASSWORD_LENGTH = 12


def _is_loopback_url(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _password() -> str:
    # Kept in memory only.  The generated value is never printed or written to
    # the report; it exists solely for the normal setup/login exchange.
    return secrets.token_urlsafe(24)


def _acceptance_password() -> str:
    """Return a disposable acceptance password without persisting a secret.

    A caller may provide ``HADES_ACCEPTANCE_PASSWORD`` when several suites
    should share one disposable environment.  It is deliberately an
    environment-only test credential; production-owner credentials are never
    accepted by this runner.  The default remains an in-memory random value
    for one-shot bootstrap runs.
    """
    configured = os.environ.get("HADES_ACCEPTANCE_PASSWORD")
    if configured:
        if len(configured) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"HADES_ACCEPTANCE_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters"
            )
        return configured
    return _password()


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


def bootstrap_acceptance_user(
    session: requests.Session,
    base_url: str,
    *,
    bootstrap_admin_password: str | None = None,
    model_endpoint_url: str | None = None,
) -> tuple[str, str, str]:
    """Create an isolated non-admin acceptance user through normal auth APIs.

    A container entrypoint may have already completed first-run setup using a
    supplied admin password.  In that case ``--bootstrap-admin-password``
    authenticates that ordinary bootstrap account; it never reads auth files
    or manufactures a token.
    """
    if not _is_loopback_url(base_url):
        raise RuntimeError("--bootstrap is permitted only for loopback acceptance deployments")
    admin_password = bootstrap_admin_password or _password()
    acceptance_password = _acceptance_password()
    status_response = session.get(f"{base_url}/api/auth/status", timeout=30)
    status = _json(status_response)
    if not status.get("configured"):
        setup = session.post(
            f"{base_url}/api/auth/setup",
            json={"username": BOOTSTRAP_ADMIN, "password": admin_password},
            timeout=30,
        )
        _json(setup)
    elif not bootstrap_admin_password:
        raise RuntimeError(
            "acceptance instance is already configured; provide --bootstrap-admin-password"
        )
    # Setup does not issue a token; authenticate the bootstrap controller using
    # the same public login flow a real operator uses.
    login(session, base_url, BOOTSTRAP_ADMIN, admin_password)
    created = session.post(
        f"{base_url}/api/auth/users",
        json={"username": ACCEPTANCE_USER, "password": acceptance_password, "is_admin": False},
        timeout=30,
    )
    _json(created)
    endpoint_id = ""
    if model_endpoint_url:
        endpoint = session.post(
            f"{base_url}/api/model-endpoints",
            data={
                "name": "Acceptance Ollama",
                "base_url": model_endpoint_url,
                "endpoint_kind": "auto",
                "require_models": "true",
                "shared": "true",
            },
            timeout=60,
        )
        endpoint_body = _json(endpoint, expected=(200, 201))
        endpoint_id = str(endpoint_body.get("id") or "")
        if not endpoint_id:
            raise RuntimeError("acceptance model endpoint was not created")
    # Use only the least-privileged synthetic identity for the actual run.
    session.cookies.clear()
    login(session, base_url, ACCEPTANCE_USER, acceptance_password)
    return ACCEPTANCE_USER, acceptance_password, endpoint_id


def authenticate(
    session: requests.Session,
    base_url: str,
    *,
    username: str,
    password: str | None,
    bootstrap: bool,
    bootstrap_admin_password: str | None = None,
    model_endpoint_url: str | None = None,
) -> tuple[str, str | None]:
    endpoint_id: str | None = None
    if username != ACCEPTANCE_USER:
        raise RuntimeError(f"live fuzz principal must be {ACCEPTANCE_USER!r}")
    if bootstrap:
        username, _, endpoint_id = bootstrap_acceptance_user(
            session, base_url,
            bootstrap_admin_password=bootstrap_admin_password,
            model_endpoint_url=model_endpoint_url,
        )
    else:
        if not password:
            raise RuntimeError("--password or HADES_ACCEPTANCE_PASSWORD is required without --bootstrap")
        login(session, base_url, username, password)
    status = _json(session.get(f"{base_url}/api/auth/status", timeout=30))
    if status.get("authenticated") is not True or status.get("username") != ACCEPTANCE_USER:
        raise RuntimeError("authenticated principal is not the isolated acceptance user")
    return username, endpoint_id


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def seed_acceptance_state(
    session: requests.Session,
    base_url: str,
    *,
    canonical_asset_db: str | None = None,
) -> dict[str, int]:
    """Seed synthetic state through owner-scoped product APIs."""
    counts = {"memory": 0, "projects": 0, "assets": 0}
    for text, category in (
        ("The acceptance operator prefers concise technical explanations.", "preference"),
        ("The acceptance operator previously used the dev branch for the project.", "history"),
        ("The acceptance operator currently tests Hades ACI on hades-aci-v1.", "current"),
    ):
        response = session.post(
            f"{base_url}/api/memory/add",
            json={"text": text, "category": category, "source": "acceptance-fixture"},
            timeout=30,
        )
        _json(response, expected=(200, 201))
        counts["memory"] += 1
    for title, status in (
        ("Hades ACI acceptance", "active"),
        ("Synthetic infrastructure review", "active"),
        ("Archived acceptance fixture", "completed"),
    ):
        response = session.post(
            f"{base_url}/api/work/projects",
            json={"title": title, "description": "Synthetic acceptance state", "status": status, "domain": "software"},
            timeout=30,
        )
        _json(response, expected=(200, 201))
        counts["projects"] += 1
    for name, model, gpu in (
        ("Acceptance workstation", "Fixture Pro", "RTX Fixture 4090"),
        ("Acceptance server", "Fixture Rack 2U", "None"),
        ("Acceptance laptop", "Fixture Air", "Integrated"),
        ("Acceptance backup host", "Fixture Mini", "None"),
    ):
        response = session.post(
            f"{base_url}/api/inventory/items",
            json={"name": name, "domain": "it", "item_kind": "asset", "default_unit": "each",
                  "description": "Synthetic Hades acceptance asset", "manufacturer": "Acceptance Labs", "model": model},
            timeout=30,
        )
        body = _json(response, expected=(200, 201))
        item = body.get("item") if isinstance(body.get("item"), dict) else body
        item_id = str((item or {}).get("id") or "")
        if not item_id:
            raise RuntimeError("acceptance asset creation returned no item ID")
        detail = session.put(
            f"{base_url}/api/inventory/assets/{item_id}",
            json={"status": "deployed", "condition": "good", "hostname": name.lower().replace(" ", "-"),
                  "specs": {"gpu": gpu, "fixture": True}},
            timeout=30,
        )
        _json(detail, expected=(200, 201))
        counts["assets"] += 1
    if canonical_asset_db:
        # The live manage_assets binding reads the owner-scoped canonical CMDB
        # (src.asset_inventory), not the newer SQL inventory application API.
        # Seed that exact store only when the disposable acceptance provisioner
        # supplies an explicit path; never guess a production database path.
        db_path = Path(canonical_asset_db).expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        for index, (name, model, gpu) in enumerate((
            ("Acceptance workstation", "Fixture Pro", "RTX Fixture 4090"),
            ("Acceptance server", "Fixture Rack 2U", "None"),
            ("Acceptance laptop", "Fixture Air", "Integrated"),
            ("Acceptance backup host", "Fixture Mini", "None"),
        ), 1):
            completed = subprocess.run(
                [
                    sys.executable, "-m", "src.asset_inventory", "add",
                    "--id", f"acceptance-asset-{index}", "--name", name,
                    "--type", "computer", "--status", "deployed",
                    "--manufacturer", "Acceptance Labs", "--model", model,
                    "--hostname", name.lower().replace(" ", "-"),
                    "--source", "acceptance-fixture", "--owner", ACCEPTANCE_USER,
                    "--attributes", json.dumps({"gpu": gpu, "fixture": True}, sort_keys=True),
                ],
                env={**os.environ, "ODY_ASSET_DB": str(db_path)},
                capture_output=True, text=True, timeout=30, check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError("canonical acceptance CMDB seed failed")
        counts["canonical_assets"] = 4
    return counts


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
    bootstrap_admin_password: str | None,
    model_endpoint_url: str | None,
    canonical_asset_db: str | None,
    seed_state: bool,
    suite: str,
    sample: int | None,
    seed: int,
    output: str,
) -> int:
    base_url = base_url.rstrip("/")
    http = requests.Session()
    _, provisioned_endpoint_id = authenticate(
        http, base_url, username=username, password=password, bootstrap=bootstrap,
        bootstrap_admin_password=bootstrap_admin_password,
        model_endpoint_url=model_endpoint_url,
    )
    endpoint_id = provisioned_endpoint_id or endpoint_id
    cookie = _cookie(http)
    if bootstrap and seed_state:
        seeded = seed_acceptance_state(http, base_url, canonical_asset_db=canonical_asset_db)
        print(json.dumps({"acceptance_state_seeded": seeded}, sort_keys=True), flush=True)
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
    parser.add_argument("--model-endpoint-url", default=os.environ.get("HADES_ACCEPTANCE_MODEL_ENDPOINT", "http://host.docker.internal:11434"), help=argparse.SUPPRESS)
    parser.add_argument("--username", default=ACCEPTANCE_USER)
    parser.add_argument("--password", default=os.environ.get("HADES_ACCEPTANCE_PASSWORD"))
    parser.add_argument("--bootstrap", action="store_true", help="use normal first-run setup on an isolated unconfigured loopback instance")
    parser.add_argument("--bootstrap-admin-password", default=os.environ.get("HADES_ACCEPTANCE_BOOTSTRAP_PASSWORD"), help=argparse.SUPPRESS)
    parser.add_argument("--no-seed-state", action="store_true", help="skip synthetic state setup during --bootstrap")
    parser.add_argument("--canonical-asset-db", default=os.environ.get("HADES_ACCEPTANCE_ASSET_DB"), help="explicit disposable CMDB path used only for acceptance seeding")
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
            bootstrap_admin_password=args.bootstrap_admin_password,
            model_endpoint_url=args.model_endpoint_url,
            canonical_asset_db=args.canonical_asset_db,
            seed_state=not args.no_seed_state,
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
