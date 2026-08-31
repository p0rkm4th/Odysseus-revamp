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
from pathlib import Path
from typing import Any

import requests


# Direct execution puts ``scripts/`` on sys.path, while the benchmark package
# lives at the repository root. Establish the same import boundary used by
# the test/in-process runner so live holdout failures reflect the candidate,
# not the invocation form.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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
    expect_reference: str | None = None
    expect_bounded_decisions: int | None = None
    expect_tool_index_lookups: int | None = None
    expect_approvals: int | None = None


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
    Case("assets_reference", "Tell me about the first physical one.", "continuation", "assets_reference", "assets", True, False, None, expect_reference="TECHNICAL_ASSET"),
    Case("assets_list_2", "Show me my hardware.", "continuation", "assets_reference_2", "assets", True, False, None),
    Case("assets_reference_2", "Tell me about the second one.", "continuation", "assets_reference_2", "assets", True, False, None, expect_reference="TECHNICAL_ASSET"),
    Case("assets_list_3", "What computers do I own?", "continuation", "assets_reference_3", "assets", True, False, None),
    Case("assets_reference_3", "Which machine is the first one?", "continuation", "assets_reference_3", "assets", True, False, None, expect_reference="TECHNICAL_ASSET"),
    # A reference without a preceding canonical result must remain a natural
    # clarification/fallback, never a guessed asset identity or tool call.
    Case("assets_reference_without_context", "Tell me about the first physical one.", family="reference", max_tools=0),
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
    Case("infra_healthy", "Is everything healthy?", family="infrastructure", expect_completion=True),
    Case("infra_broken", "Anything broken?", family="infrastructure", expect_completion=True),
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
    # The starter is a completed canonical read, not an active resumable Run;
    # the truthful continuation outcome is the bounded no-active-run fallback.
    Case("continuation_resume", "Continue.", "continuation", "continuation", "continuation", True, True, 0),
    Case("contamination_assets", "What machines do I own?", "continuation", "contamination", "contamination"),
    Case("contamination_general", "Why do cats knock things off tables?", "continuation", "contamination", "contamination"),
    Case("contamination_network", "What network am I on?", "continuation", "contamination_network", "contamination"),
    Case("contamination_network_general", "Explain DNS like I'm technical but rusty.", "continuation", "contamination_network", "contamination", expect_fallback=True, max_tools=0),
]

# Fixture metadata, deliberately separate from production routing.  The
# held-out rows are alternate wording/failure classes that are not the stable
# regression core; rotating selection can sample them without changing the
# runtime's semantic vocabulary.
_HELD_OUT_CASES = frozenset({
    "memory_4", "memory_5", "work_3", "network_3", "infra_health",
    "infra_services", "infra_near_miss", "memory_explanation", "work_advice",
    "network_definition", "unknown_action", "contamination_general",
    "assets_list_3", "assets_reference_3", "infra_healthy", "infra_broken",
    "contamination_network", "contamination_network_general",
})
CASES = tuple(
    Case(**{
        **case.__dict__,
        "split": "held_out" if case.name in _HELD_OUT_CASES else case.split,
        "expect_bounded_decisions": (
            0 if (
                case.name.startswith(("memory_", "work_", "network_", "infra_"))
                or case.name.startswith(("assets_list", "assets_reference"))
            ) and case.family not in {"negative_near_miss", "security"}
            else case.expect_bounded_decisions
        ),
        "expect_tool_index_lookups": (
            0 if (
                case.name.startswith(("memory_", "work_", "network_", "infra_"))
                or case.name.startswith(("assets_list", "assets_reference"))
            ) and case.family not in {"negative_near_miss", "security"}
            else case.expect_tool_index_lookups
        ),
        "expect_approvals": (
            0 if (
                case.name.startswith(("memory_", "work_", "network_", "infra_"))
                or case.name.startswith(("assets_list", "assets_reference"))
            ) and case.family not in {"negative_near_miss", "security"}
            else case.expect_approvals
        ),
    })
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
        if session_mode == "declared":
            # Sampling must not select a continuation turn without the
            # earlier turn that establishes its durable reference/objective.
            # Treat preceding members of the same declared group as fixture
            # prerequisites; do not append later turns or silently create a
            # contaminated session.  This keeps the sample reproducible while
            # making every selected continuation trajectory executable.
            selected_names = {case.name for case in selected}
            for index, case in enumerate(cases):
                if not case.group or case.name in selected_names:
                    continue
                if any(
                    chosen.group == case.group
                    and cases.index(chosen) > index
                    for chosen in selected
                ):
                    selected.append(case)
                    selected_names.add(case.name)
            selected.sort(key=lambda item: cases.index(item))
    if session_mode == "fresh":
        # A continuation follow-up is not an independent fresh-session case:
        # converting it to a fresh session would manufacture a missing-context
        # failure and mislabel reference resolution. Keep the first turn that
        # establishes each declared group, and leave the complete trajectory to
        # declared/continuation session modes.
        fresh: list[Case] = []
        seen_groups: set[str] = set()
        for case in selected:
            if case.mode == "continuation" and case.group:
                if case.group in seen_groups:
                    continue
                seen_groups.add(case.group)
            fresh.append(Case(**{**case.__dict__, "mode": "fresh", "group": None}))
        selected = fresh
    return selected


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def cookie_from_file(path: str) -> str:
    """Read one owner session cookie without logging the credential.

    Supports Netscape cookie exports (the format used by the existing local
    browser harness) and a plain token file.  The value is returned only to
    the in-process request caller.
    """
    text = open(path, encoding="utf-8").read()
    for line in text.splitlines():
        if line and not line.startswith("#"):
            fields = line.split("\t")
            if len(fields) >= 7 and fields[5] == "odysseus_session":
                return fields[6].strip()
    token = text.strip()
    if not token or any(ch.isspace() for ch in token):
        raise ValueError("cookie file has no usable owner session cookie")
    return token


def create_session(base: str, cookie: str, name: str, *, model: str, endpoint_id: str) -> str:
    response = requests.post(
        f"{base}/api/session",
        cookies={"odysseus_session": cookie},
        data={"name": name, "endpoint_id": endpoint_id, "model": model, "skip_validation": "true"},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["id"])


def run_case(base: str, cookie: str, session_id: str, case: Case) -> dict[str, Any]:
    from benchmarks.hades_dogfood import delivery_observation

    started = time.monotonic()
    events: list[dict[str, Any]] = []
    done_seen = False
    terminal_event_count = 0
    first_error_event: str | None = None
    delta_digests: list[str] = []
    replacement_digests: list[str] = []
    answer = ""
    event_ids: list[str] = []
    abrupt_eof = False
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
    try:
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            if line == "data: [DONE]":
                done_seen = True
                terminal_event_count += 1
                continue
            try:
                value = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
                event_id = value.get("event_id") or value.get("id")
                if event_id is not None:
                    event_ids.append(str(event_id))
                delta = value.get("delta")
                if delta is not None:
                    delta_digests.append(digest(str(delta)))
                    answer += str(delta)
                if value.get("type") == "response_replace":
                    replacement = str(value.get("content") or "")
                    replacement_digests.append(digest(replacement))
                    # Grounding/tool summaries replace already-streamed prose;
                    # they are not an additional answer delta.
                    answer = replacement
                if value.get("error") and first_error_event is None:
                    first_error_event = digest(str(value.get("error")))
    except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError):
        abrupt_eof = not done_seen
    finally:
        response.close()

    metrics = next((e.get("data", {}) for e in reversed(events) if e.get("type") == "metrics"), {})
    tools = [e for e in events if e.get("type") == "tool_start"]
    approvals = [e for e in events if e.get("type") == "ask_user"]
    terminal_events = [e for e in events if e.get("type") in {"agent_terminal", "chat_terminal"}]
    duplicate_event_id = len(event_ids) != len(set(event_ids)) if event_ids else False
    delivery = delivery_observation(events)
    terminal_digests = [digest(json.dumps(e.get("data") or {}, sort_keys=True, default=str)) for e in terminal_events]
    return {
        "case": case.name,
        "prompt_digest": digest(case.prompt),
        "session_mode": case.mode,
        "session_group": case.group,
        "family": case.family,
        "split": case.split,
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
        "approvals": len(approvals),
        "completion": bool(metrics.get("aci_completion_contract_satisfied")),
        "completion_transition": metrics.get("aci_completion_transition"),
        "fallback": bool(metrics.get("aci_model_fallback")),
        "bounded_action_decisions": int(metrics.get(
            "aci_bounded_action_decision_count",
            ((metrics.get("model_burden") or {}).get("labels") or {})
            .get("model", {}).get("bounded_action_decision", 0),
        ) or 0),
        "model_burden": metrics.get("model_burden"),
        "why_no_action": metrics.get("why_no_action"),
        "reference_resolution": metrics.get("aci_reference_resolution"),
        "latency_seconds": round(time.monotonic() - started, 2),
        "input_tokens": metrics.get("input_tokens"),
        "output_tokens": metrics.get("output_tokens"),
        "error": next((e.get("error") for e in events if e.get("error")), None),
        "done_seen": done_seen,
        "abrupt_eof": abrupt_eof,
        "terminal_event_count": terminal_event_count,
        "first_error_event": first_error_event,
        "stream_duration": round(time.monotonic() - started, 2),
        "delta_count": len(delta_digests),
        "replacement_count": len(replacement_digests),
        "replacement_digest_sequence": replacement_digests,
        "delta_digest_sequence": delta_digests,
        "duplicate_delta_sequence": duplicate_event_id,
        "duplicate_answer": bool(duplicate_event_id or delivery["duplicate_finalization"]),
        "duplicate_finalization": bool(delivery["duplicate_finalization"] or len(terminal_events) > 1),
        "stale_delta_after_replace": bool(delivery["stale_delta_after_replace"]),
        "assistant_message_id": metrics.get("assistant_message_id"),
        "persist_count": metrics.get("persist_count"),
        "finalization_id": metrics.get("finalization_id"),
        "stream_sequence": metrics.get("stream_sequence"),
        "duplicate_event_id": duplicate_event_id,
        "event_id_sequence": event_ids,
    }


def assert_case(case: Case, result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if result.get("error"):
        failures.append("transport_error")
    # Older fixture-only callers may not carry transport telemetry.  Every
    # real ``run_case`` result does, so live runs fail closed on missing or
    # malformed terminal protocol state without breaking pure assertion tests.
    if "done_seen" in result:
        if not result.get("done_seen"):
            failures.append("transport_completion_failure")
        if result.get("abrupt_eof"):
            failures.append("abrupt_eof")
        if result.get("terminal_event_count") != 1:
            failures.append("invalid_terminal_event_count")
    if result.get("duplicate_answer"):
        failures.append("duplicate_answer")
    if result.get("duplicate_finalization"):
        failures.append("duplicate_finalization")
    if result.get("stale_delta_after_replace"):
        failures.append("stale_delta_after_replace")
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
    if case.expect_reference:
        reference = result.get("reference_resolution") or {}
        if reference.get("status") != "RESOLVED":
            failures.append("reference_not_resolved")
        if reference.get("concept") != case.expect_reference:
            failures.append("reference_concept_mismatch")
    if case.expect_bounded_decisions is not None and result.get("bounded_action_decisions") != case.expect_bounded_decisions:
        failures.append("unexpected_bounded_decisions")
    if case.expect_tool_index_lookups is not None and int(result.get("tool_index_lookup") or 0) != case.expect_tool_index_lookups:
        failures.append("unexpected_tool_index_lookups")
    if case.expect_approvals is not None and int(result.get("approvals") or 0) != case.expect_approvals:
        failures.append("unexpected_approvals")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("HADES_LIVE_BASE_URL", "http://127.0.0.1:7000"))
    parser.add_argument("--cookie", default=os.environ.get("HADES_LIVE_COOKIE"))
    parser.add_argument("--cookie-file", default=os.environ.get("HADES_LIVE_COOKIE_FILE"))
    parser.add_argument("--model", default=os.environ.get("HADES_LIVE_MODEL", "qwen3:8b"))
    parser.add_argument("--endpoint-id", default=os.environ.get("HADES_LIVE_ENDPOINT_ID", "e4e4196b"))
    parser.add_argument("--output", default="/tmp/hades-live-dogfood.json")
    parser.add_argument("--suite", choices=("all", "core", "held_out", "rotating", "security"), default="all")
    parser.add_argument("--sample", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--fresh-sessions", action="store_true")
    parser.add_argument("--continuation-sessions", action="store_true")
    args = parser.parse_args()
    if not args.cookie and args.cookie_file:
        try:
            args.cookie = cookie_from_file(args.cookie_file)
        except (OSError, ValueError) as exc:
            raise SystemExit(f"unable to read --cookie-file: {exc}") from exc
    if not args.cookie:
        raise SystemExit("HADES_LIVE_COOKIE, --cookie, or --cookie-file is required")

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
                session_id = create_session(
                    args.base_url, args.cookie, f"ACI live {case.group}",
                    model=args.model, endpoint_id=args.endpoint_id,
                )
                sessions[case.group] = session_id
        else:
            session_id = create_session(
                args.base_url, args.cookie, f"ACI live {case.name}",
                model=args.model, endpoint_id=args.endpoint_id,
            )
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
        "splits": {
            split: {
                "cases": sum(1 for r in results if r.get("split") == split),
                "answers": sum(bool(r.get("answer_present")) for r in results if r.get("split") == split),
                "trajectory_pass": sum(
                    not r.get("assertion_failures")
                    for r in results if r.get("split") == split
                ),
            }
            for split in sorted({str(r.get("split") or "unknown") for r in results})
        },
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "results": results}, handle, indent=2, sort_keys=True)
    print(json.dumps({"summary": summary, "output": args.output}, sort_keys=True))
    return 0 if summary["trajectory_pass"] == summary["case_count"] else 1


if __name__ == "__main__":
    sys.exit(main())
