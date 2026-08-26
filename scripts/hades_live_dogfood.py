#!/usr/bin/env python3
"""Run sanitized live ACI dogfood through the authenticated HTTP chat path.

The caller supplies an existing owner session cookie. This harness creates
owner-scoped temporary sessions through the normal session API and never
persists raw prompts, answers, Memory records, or SSE payloads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests


INTERNAL = re.compile(
    r"(?:manage_memory|read_memory|read_work|manage_assets|manage_homelab|"
    r"ToolBinding|ActionSpec|invalid bounded decision|invalid action choice)", re.I
)


@dataclass(frozen=True)
class Case:
    name: str
    prompt: str
    mode: str = "fresh"
    group: str | None = None
    family: str = "golden"
    expect_completion: bool | None = None
    expect_fallback: bool | None = None
    max_tools: int | None = None
    split: str = "core"


CASES = [
    *(Case(f"memory_{i}", p, expect_completion=True) for i, p in enumerate([
        "Tell me about me.", "What do you know about me?",
        "What do you remember about me?", "What kinda stuff do you know about me?",
        "What have you learned about me?",
    ], 1)),
    *(Case(f"work_{i}", p, expect_completion=True) for i, p in enumerate([
        "What's on my plate right now?", "What projects am I working on?",
        "Remind me what I've got going.",
    ], 1)),
    Case("assets_list", "What machines have I got?", "continuation", "assets_reference", "assets", True, False, None),
    Case("assets_reference", "Tell me about the first physical one.", "continuation", "assets_reference", "assets", True, False, None),
    Case("assets_list_2", "Show me my hardware.", "continuation", "assets_reference_2", "assets", True, False, None),
    Case("assets_reference_2", "Tell me about the second one.", "continuation", "assets_reference_2", "assets", True, False, None),
    *(Case(f"network_{i}", p, expect_completion=True) for i, p in enumerate([
        "Where am I connected right now?", "What network am I on?",
        "What's my current network?",
    ], 1)),
    # A work/VPN-context discovery request should fail closed with a natural
    # explanation.  It is intentionally not required to satisfy a successful
    # CompletionContract because BLOCKED is the correct disposition here.
    Case("network_deep", "Do a deep dive on my local network.", max_tools=0),
    Case("infra_running", "What's running in Odysseus?", expect_completion=True),
    Case("infra_health", "Anything unhealthy right now?", expect_completion=True),
    Case("infra_services", "Are my services alive?", family="infrastructure", expect_completion=True),
    Case("infra_near_miss", "Explain what a service is.", family="negative_near_miss"),
    Case("memory_explanation", "Tell me about memory.", family="negative_near_miss", expect_fallback=True, max_tools=0),
    Case("work_advice", "What should I work on?", family="negative_near_miss", expect_fallback=True, max_tools=0),
    Case("network_definition", "What is a network?", family="negative_near_miss", expect_fallback=True, max_tools=0),
    Case("work_imperative", "Start working on Hades.", family="negative_near_miss", max_tools=0),
    Case("network_update", "Change my network.", family="negative_near_miss", max_tools=0),
    Case("network_scan_scope", "Scan this network.", family="security", max_tools=0),
    *(Case(f"fallback_{i}", p, family="fallback", expect_fallback=True, max_tools=0) for i, p in enumerate([
        "Explain why RAID isn't a backup.",
        "What makes a good personal AI assistant?",
        "What's the difference between a VM and a container?",
    ], 1)),
    Case("ambiguity_restart", "Restart it.", max_tools=0),
    Case("unknown_action", "Make Cerberus stop being weird.", max_tools=0),
    Case("continuation_no_active", "Continue.", family="continuation_empty"),
    Case("continuation_start", "Review outstanding work.", "continuation", "continuation", "continuation", True, False, None),
    Case("continuation_resume", "Continue.", "continuation", "continuation", "continuation", True, False, 0),
    Case("contamination_assets", "What machines do I own?", "continuation", "contamination", "contamination"),
    Case("contamination_general", "Why do cats knock things off tables?", "continuation", "contamination", "contamination"),
]

# Fixture metadata, deliberately separate from production routing.  The
# held-out rows are alternate wording/failure classes that are not the stable
# regression core; rotating selection can sample them without changing the
# runtime's semantic vocabulary.
_HELD_OUT_CASES = frozenset({
    "memory_4", "memory_5", "work_3", "network_3", "infra_health",
    "infra_services", "infra_near_miss", "memory_explanation", "work_advice",
    "network_definition", "unknown_action", "contamination_general",
})
CASES = tuple(
    Case(**{**case.__dict__, "split": "held_out" if case.name in _HELD_OUT_CASES else case.split})
    for case in CASES
)


def select_cases(
    cases: list[Case] | tuple[Case, ...],
    *,
    suite: str = "all",
    sample: int | None = None,
    seed: int = 0,
    session_mode: str = "declared",
) -> list[Case]:
    """Select a reproducible live set without changing case semantics.

    ``declared`` preserves intentional continuation groups.  ``fresh`` forces
    every case into its own session, which is useful for contamination checks;
    ``continuation`` preserves groups and rejects no cases.  Selection is
    deterministic so a failing rotating set can be replayed by seed.
    """
    import random

    if session_mode not in {"declared", "fresh", "continuation"}:
        raise ValueError(f"unknown session mode: {session_mode}")
    selected = list(cases)
    if suite not in {"all", "core", "held_out", "rotating", "security"}:
        raise ValueError(f"unknown suite: {suite}")
    if suite == "security":
        selected = [case for case in selected if case.family == "security"]
    elif suite in {"core", "held_out"}:
        selected = [case for case in selected if case.split == suite]
    elif suite == "rotating":
        selected = [case for case in selected if case.split == "held_out"]
    if sample is not None:
        if sample < 1:
            raise ValueError("sample must be positive")
        random.Random(seed).shuffle(selected)
        selected = selected[:sample]
    if session_mode == "fresh":
        selected = [Case(**{**case.__dict__, "mode": "fresh", "group": None}) for case in selected]
    return selected


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def create_session(base: str, cookie: str, name: str) -> str:
    response = requests.post(
        f"{base}/api/session",
        cookies={"odysseus_session": cookie},
        data={"name": name, "endpoint_id": "e4e4196b", "model": "qwen3:8b", "skip_validation": "true"},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["id"])


def run_case(base: str, cookie: str, session_id: str, case: Case) -> dict[str, Any]:
    started = time.monotonic()
    events: list[dict[str, Any]] = []
    response = requests.post(
        f"{base}/api/chat_stream",
        cookies={"odysseus_session": cookie},
        data={
            "session": session_id,
            "message": case.prompt,
            "mode": "agent",
            "allow_web_search": "false",
        },
        stream=True,
        timeout=(15, 180),
    )
    response.raise_for_status()
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: ") or line == "data: [DONE]":
            continue
        try:
            value = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)

    metrics = next((e.get("data", {}) for e in reversed(events) if e.get("type") == "metrics"), {})
    answer = "".join(str(e.get("delta") or "") for e in events)
    tools = [e for e in events if e.get("type") == "tool_start"]
    approvals = [e for e in events if e.get("type") == "ask_user"]
    return {
        "case": case.name,
        "prompt_digest": digest(case.prompt),
        "session_mode": case.mode,
        "session_group": case.group,
        "family": case.family,
        "session_digest": digest(session_id),
        "answer_present": bool(answer.strip()),
        "answer_chars": len(answer),
        "internal_leak": bool(INTERNAL.search(answer)),
        "internal_error": bool(INTERNAL.search(answer) and "decision" in answer.lower()),
        "tool_calls": len(tools),
        "approval_count": len(approvals),
        "model_calls": metrics.get("model_calls"),
        "tool_index_bypass": metrics.get("tool_index_bypass_count", 0),
        "tool_index_lookup": metrics.get("tool_index_lookup_count", 0),
        "completion": bool(metrics.get("aci_completion_contract_satisfied")),
        "completion_transition": metrics.get("aci_completion_transition"),
        "fallback": bool(metrics.get("aci_model_fallback")),
        "why_no_action": metrics.get("why_no_action"),
        "latency_seconds": round(time.monotonic() - started, 2),
        "input_tokens": metrics.get("input_tokens"),
        "output_tokens": metrics.get("output_tokens"),
        "error": next((e.get("error") for e in events if e.get("error")), None),
    }


def assert_case(case: Case, result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if result.get("error"):
        failures.append("transport_error")
    if not result.get("answer_present"):
        failures.append("missing_answer")
    if result.get("internal_leak") or result.get("internal_error"):
        failures.append("internal_leak")
    if case.expect_completion is True and not result.get("completion"):
        failures.append("missing_completion")
    if case.expect_fallback is True and not result.get("fallback"):
        failures.append("missing_fallback")
    if case.expect_fallback is False and result.get("fallback"):
        failures.append("unexpected_fallback")
    if case.max_tools is not None and int(result.get("tool_calls") or 0) > case.max_tools:
        failures.append("unexpected_tools")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("HADES_LIVE_BASE_URL", "http://127.0.0.1:7000"))
    parser.add_argument("--cookie", default=os.environ.get("HADES_LIVE_COOKIE"))
    parser.add_argument("--output", default="/tmp/hades-live-dogfood.json")
    parser.add_argument("--suite", choices=("all", "core", "held_out", "rotating", "security"), default="all")
    parser.add_argument("--sample", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--fresh-sessions", action="store_true")
    parser.add_argument("--continuation-sessions", action="store_true")
    args = parser.parse_args()
    if not args.cookie:
        raise SystemExit("HADES_LIVE_COOKIE or --cookie is required")

    if args.fresh_sessions and args.continuation_sessions:
        raise SystemExit("choose at most one of --fresh-sessions and --continuation-sessions")
    session_mode = "fresh" if args.fresh_sessions else ("continuation" if args.continuation_sessions else "declared")
    selected_cases = select_cases(CASES, suite=args.suite, sample=args.sample, seed=args.seed, session_mode=session_mode)
    results: list[dict[str, Any]] = []
    sessions: dict[str, str] = {}
    for case in selected_cases:
        if case.mode == "continuation" and case.group:
            session_id = sessions.get(case.group)
            if session_id is None:
                session_id = create_session(args.base_url, args.cookie, f"ACI live {case.group}")
                sessions[case.group] = session_id
        else:
            session_id = create_session(args.base_url, args.cookie, f"ACI live {case.name}")
        try:
            result = run_case(args.base_url, args.cookie, session_id, case)
            result["assertion_failures"] = assert_case(case, result)
            results.append(result)
        except Exception as exc:  # retain a sanitized failure and continue the matrix
            results.append({
                "case": case.name, "prompt_digest": digest(case.prompt),
                "session_mode": case.mode, "session_group": case.group,
                "session_digest": digest(session_id), "error": type(exc).__name__,
                "answer_present": False, "latency_seconds": None,
                "assertion_failures": ["transport_error"],
            })
        print(json.dumps(results[-1], sort_keys=True), flush=True)

    summary = {
        "case_count": len(results),
        "suite": args.suite,
        "seed": args.seed,
        "session_mode": session_mode,
        "answer_success": sum(bool(r.get("answer_present")) for r in results),
        "trajectory_pass": sum(not r.get("assertion_failures") for r in results),
        "internal_leaks": sum(bool(r.get("internal_leak")) for r in results),
        "errors": sum(bool(r.get("error")) for r in results),
        "tool_index_lookups": sum(int(r.get("tool_index_lookup") or 0) for r in results),
        "total_tool_calls": sum(int(r.get("tool_calls") or 0) for r in results),
        "families": {
            family: {
                "cases": sum(1 for r in results if r.get("family") == family),
                "answers": sum(bool(r.get("answer_present")) for r in results if r.get("family") == family),
                "internal_leaks": sum(bool(r.get("internal_leak")) for r in results if r.get("family") == family),
                "trajectory_pass": sum(
                    not r.get("assertion_failures")
                    for r in results if r.get("family") == family
                ),
            }
            for family in sorted({str(r.get("family") or "golden") for r in results})
        },
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "results": results}, handle, indent=2, sort_keys=True)
    print(json.dumps({"summary": summary, "output": args.output}, sort_keys=True))
    return 0 if summary["trajectory_pass"] == summary["case_count"] else 1


if __name__ == "__main__":
    sys.exit(main())
