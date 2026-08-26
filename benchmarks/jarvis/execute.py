#!/usr/bin/env python3
"""Execute Jarvis cases against an Odysseus model route with synthetic tools."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

from benchmarks.jarvis.collector import SyntheticRunCollector, parse_sse
from benchmarks.jarvis.core import load_json, validate_run, validate_suite
from benchmarks.jarvis.fixtures import build_case_messages
from benchmarks.jarvis.synthetic_tools import SyntheticToolExecutor, fixtures_for_case

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def endpoint_is_local(endpoint: str) -> bool:
    return (urlparse(endpoint).hostname or "").casefold() in _LOOPBACK_HOSTS


async def execute_case(args, case, model_metadata, hardware, headers):
    # Keep metadata validation and --help usable in lightweight environments.
    # The application stack is required only when a model run actually starts.
    from src.agent_loop import stream_agent_loop

    collector = SyntheticRunCollector(case, model_metadata, hardware)
    executor = SyntheticToolExecutor(fixtures_for_case(case))
    messages = build_case_messages(case)
    # Continuity cases must exercise the provider-replacement path. The first
    # endpoint is deliberately loopback-invalid; the configured endpoint is
    # the only fallback. This is synthetic harness fault injection and never
    # touches an owner or work/VPN network.
    primary_endpoint = args.endpoint
    fallbacks = None
    fallback_statuses = None
    if case.get("expected", {}).get("requires_recovery"):
        primary_endpoint = "http://127.0.0.1:1/v1"
        fallbacks = [(args.endpoint, args.model, headers or {})]
        fallback_statuses = {502, 503, 504}
    try:
        async with asyncio.timeout(args.case_timeout):
            async for chunk in stream_agent_loop(
                endpoint_url=primary_endpoint,
                model=args.model,
                messages=messages,
                headers=headers,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                context_length=args.context_length,
                max_rounds=args.max_rounds,
                max_tool_calls=args.max_tool_calls,
                owner="__jarvis_synthetic_benchmark__",
                workload="benchmark",
                fallbacks=fallbacks,
                fallback_statuses=fallback_statuses,
                external_untrusted_context_seen=bool(
                    case.get("external_untrusted_context", False)
                ),
                tool_executor=executor,
                aci_mode=args.aci_mode,
            ):
                for event in parse_sse([chunk]):
                    collector.consume(event)
    except TimeoutError:
        collector.consume({"error": "synthetic case timeout"})
        record = collector.finish()
        record["failure_category"] = "timeout"
        return record
    return collector.finish()


async def execute_suite(args) -> list[dict]:
    suite = validate_suite(load_json(args.suite))
    selected = set(args.case or [])
    unknown = selected - {case["id"] for case in suite["cases"]}
    if unknown:
        raise SystemExit(f"Unknown case id(s): {', '.join(sorted(unknown))}")
    cases = [case for case in suite["cases"] if not selected or case["id"] in selected]
    model_metadata = load_json(args.model_metadata)
    hardware = load_json(args.hardware)
    headers = load_json(args.headers) if args.headers else None
    # Fail before the first provider request when metadata cannot produce a
    # scoreable record. This matters especially for explicitly approved paid
    # routes, where discovering the mistake after execution wastes money.
    validate_run({
        "schema_version": 1,
        "case_id": "preflight",
        "model": model_metadata,
        "hardware": hardware,
        "metrics": {},
        "tool_calls": [],
        "failure_category": "none",
    })
    if headers is not None and not isinstance(headers, dict):
        raise SystemExit("Headers metadata must be a JSON object")
    records = []
    for case in cases:
        records.append(await execute_case(args, case, model_metadata, hardware, headers))
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="benchmarks/jarvis/core-v1.json")
    parser.add_argument("--case", action="append", help="case id; repeat to select several")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-metadata", required=True)
    parser.add_argument("--hardware", required=True)
    parser.add_argument("--headers", help="optional JSON headers file; never copied to reports")
    parser.add_argument("--output", required=True)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--context-length", type=int, default=8192)
    parser.add_argument("--max-rounds", type=int, default=6)
    parser.add_argument("--max-tool-calls", type=int, default=6)
    parser.add_argument("--case-timeout", type=float, default=180.0)
    parser.add_argument(
        "--capability-profile",
        choices=("standard", "local_balanced", "local_small", "auto"),
        default="standard",
    )
    parser.add_argument(
        "--aci-mode",
        choices=("legacy", "shadow", "aci"),
        default="legacy",
        help="agent interface protocol for the run; legacy preserves H0",
    )
    parser.add_argument(
        "--acknowledge-provider-costs",
        action="store_true",
        help="required for non-loopback endpoints",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not endpoint_is_local(args.endpoint) and not args.acknowledge_provider_costs:
        parser.error(
            "non-loopback endpoints may incur charges; rerun with "
            "--acknowledge-provider-costs after obtaining approval"
        )
    records = asyncio.run(execute_suite(args))
    rendered = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    Path(args.output).write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
