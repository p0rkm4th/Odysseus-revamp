#!/usr/bin/env python3
"""Run the authoritative declarative Hades dogfood contract."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.hades_dogfood import (
    append_history,
    capture_failure_regressions,
    coverage_audit,
    expand_cases,
    load_contract,
    normalize_events,
    report,
)
from benchmarks.jarvis.synthetic_tools import SyntheticToolExecutor, fixtures_for_case


def _event(value: str) -> dict[str, Any] | None:
    if not value.startswith("data:"):
        return None
    payload = value[5:].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _live_protocol_observation(
    events: list[dict[str, Any]],
    *,
    done_count: int,
    abrupt_eof: bool,
) -> dict[str, Any]:
    """Return transport-level evidence for an authenticated SSE run.

    The semantic scorer must not treat a partial answer as a completed live
    turn.  ``[DONE]`` is the protocol terminal marker; message/event identity
    is retained as digests or IDs so this remains safe for owner data.
    """
    event_ids = [str(item.get("event_id") or item.get("id")) for item in events
                 if item.get("event_id") is not None or item.get("id") is not None]
    terminal_events = [item for item in events
                       if item.get("type") in {"agent_terminal", "chat_terminal"}]
    duplicate_event_id = bool(event_ids and len(event_ids) != len(set(event_ids)))
    return {
        "done_seen": done_count > 0,
        "terminal_event_count": int(done_count),
        "abrupt_eof": bool(abrupt_eof),
        "first_error_event": next(
            (str(item.get("error"))[:160] for item in events if item.get("error")),
            None,
        ),
        "delta_count": sum("delta" in item for item in events),
        "event_id_count": len(event_ids),
        "duplicate_event_id": duplicate_event_id,
        "terminal_payload_count": len(terminal_events),
        "transport_completion": done_count == 1 and not abrupt_eof,
    }


def _source_reference() -> str:
    configured = os.environ.get("HADES_SOURCE_REFERENCE")
    if configured:
        return configured
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip() or "working-tree"
    except (OSError, subprocess.SubprocessError):
        return "working-tree"


def _source_dirty() -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=ROOT, check=True, capture_output=True, text=True, timeout=5,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return True


def _run_metadata(args: argparse.Namespace) -> dict[str, Any]:
    config = {
        "contract": args.contract, "suite": args.suite, "tier": args.tier,
        "mode": args.mode, "model": args.model, "seed": args.seed,
        "generated_count": args.generated_count, "shard_index": args.shard_index,
        "shard_count": args.shard_count, "context_length": args.context_length,
        "max_tokens": args.max_tokens, "max_rounds": args.max_rounds,
        "max_tool_calls": args.max_tool_calls,
        "minimal_pair_count": args.minimal_pair_count,
    }
    return {
        "run_id": f"dogfood-{uuid.uuid4().hex}",
        "model": args.model,
        "model_digest": os.environ.get("HADES_MODEL_DIGEST", "unknown"),
        "source_commit": _source_reference(),
        "source_dirty": _source_dirty(),
        "deployed_source": os.environ.get("HADES_DEPLOYED_SOURCE", "not_deployed"),
        "config_fingerprint": hashlib.sha256(
            json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16],
    }


async def run_synthetic(
    case: dict[str, Any],
    args: argparse.Namespace,
    *,
    messages: list[dict[str, str]] | None = None,
) -> tuple[dict[str, Any], str]:
    # Exercise the same canonical production entrypoint used by chat,
    # scheduling, skills, background continuation, and teacher escalation.
    # The ACI seam binds aci_mode itself; passing it here remains explicit in
    # the evaluator metadata and protects against accidental compatibility
    # fallback if the call shape changes.
    from src.aci import stream_aci_turn
    events: list[dict[str, Any]] = []
    started = time.perf_counter()
    request_messages = list(messages or [])
    request_messages.append({"role": "user", "content": case["prompt"]})
    endpoint = args.endpoint
    fallbacks = None
    fallback_statuses = None
    # Continuation contracts explicitly request provider fault injection. The
    # fallback remains the configured local endpoint and carries no extra
    # authority; this exercises the same provider-replacement seam used by
    # the existing Jarvis harness.
    if (case.get("expected") or {}).get("requires_recovery"):
        endpoint = "http://127.0.0.1:1/v1"
        fallbacks = [(args.endpoint, args.model, {})]
        fallback_statuses = {502, 503, 504}
    async with asyncio.timeout(args.case_timeout):
        async for chunk in stream_aci_turn(
            endpoint_url=endpoint, model=args.model,
            messages=request_messages,
            owner="__hades_dogfood_synthetic__", session_id="hades-dogfood",
            workload="benchmark", aci_mode="aci", max_tokens=args.max_tokens,
            max_rounds=args.max_rounds, max_tool_calls=args.max_tool_calls,
            context_length=args.context_length,
            fallbacks=fallbacks,
            fallback_statuses=fallback_statuses,
            # Every contract run uses the non-persistent synthetic tool seam.
            # Unknown tools fail closed; no owner store or real Action is
            # touched by the evaluator.
            tool_executor=SyntheticToolExecutor(fixtures_for_case(case)),
        ):
            for line in str(chunk).splitlines():
                item = _event(line)
                if item is not None:
                    events.append(item)
    record = normalize_events(events, case, elapsed=time.perf_counter() - started)
    # The report intentionally retains only sanitized answer metadata.  The
    # answer text is kept transiently here so synthetic journey turns can
    # exercise real conversational continuity without making the evaluator a
    # second persistence store or leaking owner data into artifacts.
    assistant_text = "".join(str(event.get("delta") or "") for event in events)
    return record, assistant_text


async def run_cases(args: argparse.Namespace, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    journey_context: dict[str, list[dict[str, str]]] = {}
    for case in cases:
        journey = str(case.get("journey") or "")
        prior_messages = journey_context.get(journey) if journey else None
        try:
            record, assistant_text = await run_synthetic(
                case, args, messages=prior_messages
            )
        except asyncio.TimeoutError:
            record = normalize_events([{"error": "timeout"}], case, elapsed=args.case_timeout)
            record["failure"] = "timeout"
            assistant_text = ""
        except Exception as exc:  # sanitized failure artifact
            record = normalize_events([{"error": type(exc).__name__}], case, elapsed=0)
            record["failure"] = type(exc).__name__
            assistant_text = ""
        records.append(record)
        if journey:
            context = journey_context.setdefault(journey, [])
            context.extend([
                {"role": "user", "content": case["prompt"]},
                {"role": "assistant", "content": assistant_text[-12000:]},
            ])
        print(json.dumps({"case_id": case["id"], "functional": records[-1]["assistant_answer"]["present"],
                          "model_calls": records[-1]["metrics"]["model_calls"]}, sort_keys=True), flush=True)
    return records


def run_live_cases(args: argparse.Namespace, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use the existing authenticated SSE route with the shared scorer."""
    from scripts.hades_live_dogfood import cookie_from_file, create_session

    cookie = args.cookie
    if not cookie and args.cookie_file:
        cookie = cookie_from_file(args.cookie_file)
    if not cookie:
        raise SystemExit("live mode requires --cookie or --cookie-file")
    base = args.base_url.rstrip("/")
    sessions: dict[str, str] = {}
    records: list[dict[str, Any]] = []
    for case in cases:
        group = case.get("journey")
        session_id = sessions.get(str(group)) if group else None
        if session_id is None:
            session_id = create_session(base, cookie, f"Hades dogfood {case['id']}",
                                        model=args.model, endpoint_id=args.endpoint_id)
            if group:
                sessions[str(group)] = session_id
        events: list[dict[str, Any]] = []
        done_count = 0
        abrupt_eof = False
        started = time.perf_counter()
        try:
            response = requests.post(
                f"{base}/api/chat_stream", cookies={"odysseus_session": cookie},
                data={"session": session_id, "message": case["prompt"],
                      "mode": "agent", "allow_web_search": "false"},
                stream=True, timeout=(15, args.case_timeout),
            )
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if line and line.strip() == "data: [DONE]":
                    done_count += 1
                    continue
                item = _event(line) if line else None
                if item is not None:
                    events.append(item)
            record = normalize_events(events, case, elapsed=time.perf_counter() - started)
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError) as exc:
            abrupt_eof = True
            record = normalize_events(events, case, elapsed=time.perf_counter() - started)
            record["failure"] = type(exc).__name__
        except Exception as exc:  # retain only an exception class in artifacts
            record = normalize_events([{"error": type(exc).__name__}], case,
                                      elapsed=time.perf_counter() - started)
            record["failure"] = type(exc).__name__
        record["transport"] = _live_protocol_observation(
            events, done_count=done_count, abrupt_eof=abrupt_eof,
        )
        record["trajectory"]["transport"] = dict(record["transport"])
        records.append(record)
        print(json.dumps({"case_id": case["id"], "functional": record["assistant_answer"]["present"],
                          "model_calls": record["metrics"]["model_calls"]}, sort_keys=True), flush=True)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", default="benchmarks/hades_dogfood_contract.json")
    parser.add_argument("--suite", choices=("baseline", "all", "security", "held_out"), default="baseline")
    parser.add_argument("--tier", choices=("quick", "core", "full", "rc", "soak"), help="named tier over the same evaluator")
    parser.add_argument("--mode", choices=("synthetic", "live"), default="synthetic")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--base-url", default="http://127.0.0.1:7000")
    parser.add_argument("--cookie")
    parser.add_argument("--cookie-file")
    parser.add_argument("--endpoint-id", default="e4e4196b")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--output", default="/tmp/hades-dogfood-baseline.json")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--generated-count", type=int, default=None, help="add this many reproducible semantic scenarios")
    parser.add_argument("--metamorphic-count", type=int, default=None, help="add equivalent-phrasing semantic variants")
    parser.add_argument("--negative-count", type=int, default=None, help="add informational near-misses that must not execute")
    parser.add_argument("--minimal-pair-count", type=int, default=None, help="add semantic conceptual/operational minimal pairs")
    parser.add_argument("--chaos-journeys", type=int, default=None, help="add generated multi-turn journeys")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--generate-only", action="store_true", help="emit semantic cases and coverage without invoking a model")
    parser.add_argument("--coverage-only", action="store_true", help="emit coverage gaps without invoking a model")
    parser.add_argument("--capture-failures", help="append synthetic failures to a reproducible regression corpus")
    parser.add_argument("--regressions", help="include a previously captured synthetic regression corpus")
    parser.add_argument("--history", help="append sanitized summary/trend data to a JSON history file")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--context-length", type=int, default=8192)
    parser.add_argument("--max-rounds", type=int, default=4)
    parser.add_argument("--max-tool-calls", type=int, default=6)
    parser.add_argument("--case-timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    tier_defaults = {
        "quick": ("baseline", 0, 0, 0, 0, 0),
        "core": ("all", 1000, 100, 100, 50, 50),
        "full": ("all", 5000, 400, 400, 100, 200),
        "rc": ("all", 1000, 250, 250, 100, 100),
        "soak": ("all", 250, 50, 50, 25, 25),
    }
    if args.tier:
        args.suite, tier_count, tier_metamorphic, tier_negative, tier_chaos, tier_pairs = tier_defaults[args.tier]
        if args.generated_count is None:
            args.generated_count = tier_count
        if args.metamorphic_count is None:
            args.metamorphic_count = tier_metamorphic
        if args.negative_count is None:
            args.negative_count = tier_negative
        if args.chaos_journeys is None:
            args.chaos_journeys = tier_chaos
        if args.minimal_pair_count is None:
            args.minimal_pair_count = tier_pairs
    if args.generated_count is None:
        args.generated_count = 0
    if args.metamorphic_count is None:
        args.metamorphic_count = 0
    if args.negative_count is None:
        args.negative_count = 0
    if args.chaos_journeys is None:
        args.chaos_journeys = 0
    if args.minimal_pair_count is None:
        args.minimal_pair_count = 0
    contract = load_contract(args.contract)
    cases = expand_cases(
        contract, suite=args.suite, generated_count=args.generated_count,
        seed=args.seed, shard_index=args.shard_index, shard_count=args.shard_count,
        regressions_path=args.regressions, metamorphic_count=args.metamorphic_count,
        negative_count=args.negative_count, chaos_journey_count=args.chaos_journeys,
        minimal_pair_count=args.minimal_pair_count,
    )
    run_metadata = _run_metadata(args)
    for case in cases:
        case["run_id"] = run_metadata["run_id"]
        case["run_metadata"] = run_metadata
    if args.generate_only or args.coverage_only:
        result = {
            "schema_version": 1, "contract": contract["name"], "model": args.model,
            "mode": "coverage", "seed": args.seed, "run_metadata": run_metadata,
            "contract_summary": {"scenario_count": len(cases), "shard_index": args.shard_index, "shard_count": args.shard_count},
            "coverage": coverage_audit(cases), "cases": [
                {
                    **{key: case.get(key) for key in ("id", "family", "source", "split", "expected", "scenario", "fixture_id", "seed", "variant_id", "run_id")},
                    "run_metadata": dict(case.get("run_metadata") or {}),
                }
                for case in cases
            ] if args.generate_only else [],
        }
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"DOGFOOD_COVERAGE": args.output, "scenario_count": len(cases), "coverage_gap_count": result["coverage"]["coverage_gap_count"]}, sort_keys=True))
        return 0
    records = (run_live_cases(args, cases) if args.mode == "live"
               else asyncio.run(run_cases(args, cases)))
    result = report(contract, cases, records, model=args.model, mode=f"{args.mode}_runtime", seed=args.seed)
    result["run_metadata"] = run_metadata
    if args.capture_failures:
        result["failure_capture"] = capture_failure_regressions(
            args.capture_failures, cases, result["scores"],
            include_prompts=args.mode != "live",
        )
    if args.history:
        result["history_entry"] = append_history(args.history, result)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"DOGFOOD_REPORT": args.output, "tier": args.tier, **result["summary"]}, sort_keys=True))
    return 0 if result["summary"]["functional_success"] == result["summary"]["scenario_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
