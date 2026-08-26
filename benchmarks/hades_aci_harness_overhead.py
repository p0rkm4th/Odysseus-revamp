"""Measure local-backend versus Hades ACI overhead on a harmless prompt.

This benchmark uses only the configured local model endpoint and a synthetic
prompt. It never executes Actions, scans hosts, or persists application state.
The raw request and Hades request use the same model and endpoint so the
reported delta isolates context construction/orchestration as far as the
provider timings permit.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

# Allow the documented ``python benchmarks/...`` invocation from the repository
# root to resolve the application package without requiring a shell-specific
# PYTHONPATH export.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.agent_loop import stream_agent_loop
from src.model_context import estimate_tokens


def _local_endpoint(endpoint: str) -> bool:
    host = (urlparse(endpoint).hostname or "").casefold()
    return host in {"127.0.0.1", "localhost", "::1", "172.18.0.1"}


async def raw_chat(
    endpoint: str,
    model: str,
    prompt: str,
    *,
    timeout: float,
    max_tokens: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    first_token: float | None = None
    output = []
    usage: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            endpoint.rstrip("/") + "/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "think": False,
                "options": {"temperature": 0.0, "num_predict": max_tokens},
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                event = json.loads(line)
                message = event.get("message") or {}
                content = str(message.get("content") or "")
                if content and first_token is None:
                    first_token = time.perf_counter()
                output.append(content)
                if event.get("done"):
                    usage = event
    finished = time.perf_counter()
    return {
        "path": "raw_backend",
        "ttft_seconds": round((first_token or finished) - started, 4),
        "completion_seconds": round(finished - started, 4),
        "output_tokens": usage.get("eval_count"),
        "prompt_tokens": usage.get("prompt_eval_count"),
        "output_chars": len("".join(output)),
    }


async def hades_chat(
    endpoint: str,
    model: str,
    prompt: str,
    *,
    timeout: float,
    max_tokens: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    first_token: float | None = None
    output_chars = 0
    metrics: dict[str, Any] = {}
    async with asyncio.timeout(timeout):
        async for chunk in stream_agent_loop(
            endpoint_url=endpoint,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            owner="__hades_aci_overhead_benchmark__",
            session_id="hades-aci-overhead-benchmark",
            aci_mode="aci",
            max_tokens=max_tokens,
            max_rounds=1,
            max_tool_calls=0,
            context_length=8192,
        ):
            for line in str(chunk).splitlines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                if raw == "[DONE]":
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(event.get("delta"), str) and event["delta"]:
                    if first_token is None:
                        first_token = time.perf_counter()
                    output_chars += len(event["delta"])
                if event.get("type") == "metrics" and isinstance(event.get("data"), dict):
                    metrics = dict(event["data"])
    finished = time.perf_counter()
    return {
        "path": "hades_aci",
        "ttft_seconds": round((first_token or finished) - started, 4),
        "completion_seconds": round(finished - started, 4),
        "output_tokens": metrics.get("output_tokens"),
        "prompt_tokens": metrics.get("request_context_tokens") or metrics.get("input_tokens"),
        "context_construction_seconds": metrics.get("agent_prep_time"),
        "context_construction_breakdown": metrics.get("agent_prep_breakdown") or {},
        "model_wait_seconds": metrics.get("agent_model_wait_time"),
        "model_calls": metrics.get("model_calls"),
        "model_burden": metrics.get("model_burden"),
        "tool_calls": metrics.get("tool_calls", 0),
        "response_time_seconds": metrics.get("response_time"),
        "reported_ttft_seconds": metrics.get("time_to_first_token"),
        "tokens_per_second": metrics.get("tokens_per_second"),
        "tps_source": metrics.get("tps_source"),
        "prefill_tps": metrics.get("prefill_tps"),
        "usage_source": metrics.get("usage_source"),
        "context_envelope": metrics.get("aci_context_envelope"),
        "aci_model_fallback": bool(metrics.get("aci_model_fallback")),
        "aci_empty_answer_fallback": bool(metrics.get("aci_empty_answer_fallback")),
        "output_chars": output_chars,
    }


def timing_attribution(raw: dict[str, Any], hades: dict[str, Any]) -> dict[str, float | None]:
    """Separate framework work from additional provider inference.

    ``completion_seconds`` includes all Hades work.  The internal
    ``response_time_seconds`` is the provider/round span after Hades prep;
    therefore subtracting prep from the total alone is not framework overhead
    and was previously mislabeled as such.
    """
    raw_total = float(raw.get("completion_seconds") or 0)
    hades_total = float(hades.get("completion_seconds") or 0)
    prep = float(hades.get("context_construction_seconds") or 0)
    provider = hades.get("response_time_seconds")
    if provider is None:
        provider = max(hades_total - prep, 0)
    provider = float(provider)
    return {
        "total_harness_overhead_seconds": round(hades_total - raw_total, 4),
        "extra_model_inference_seconds": round(provider - raw_total, 4),
        # Small negative values are clock/stream-event ordering noise.
        "framework_overhead_seconds": round(max(hades_total - prep - provider, 0), 4),
    }


def output_accounting(raw: dict[str, Any], hades: dict[str, Any]) -> dict[str, Any]:
    """Flag provider-usage versus streamed-text inconsistencies.

    Usage counts are provider metadata, while streamed character counts are
    observed at the Hades boundary.  A large ratio is evidence that a report
    is not suitable for equivalent-deliverable comparison; it is not silently
    converted into a fabricated token count.
    """
    result: dict[str, Any] = {"consistent": True, "reason": None}
    if hades.get("aci_empty_answer_fallback"):
        return {"consistent": False, "reason": "hades_framework_generated_fallback"}
    for label, item in (("raw", raw), ("hades", hades)):
        tokens = item.get("output_tokens")
        chars = item.get("output_chars")
        if not isinstance(tokens, int) or not isinstance(chars, int):
            result.update(consistent=False, reason=f"{label}_usage_missing")
            return result
        if tokens == 0 and chars > 0:
            result.update(consistent=False, reason=f"{label}_tokens_zero_with_text")
            return result
        if tokens > 0 and chars > tokens * 16:
            result.update(consistent=False, reason=f"{label}_text_token_ratio implausible")
            return result
    return result


async def run(args: argparse.Namespace) -> dict[str, Any]:
    prompt = "Answer with exactly one short sentence: what is 2 plus 2?"
    raw = await raw_chat(
        args.endpoint, args.model, prompt,
        timeout=args.timeout, max_tokens=args.max_tokens,
    )
    hades = await hades_chat(
        args.endpoint, args.model, prompt,
        timeout=args.timeout, max_tokens=args.max_tokens,
    )
    attribution = timing_attribution(raw, hades)
    return {
        "schema_version": 1,
        "synthetic": True,
        "side_effects": False,
        "endpoint": urlparse(args.endpoint)._replace(path="", query="", fragment="").geturl(),
        "model": args.model,
        "prompt_tokens_baseline": estimate_tokens([{"role": "user", "content": prompt}]),
        "raw": raw,
        "hades": hades,
        "output_accounting": output_accounting(raw, hades),
        "harness_overhead_seconds": round(hades["completion_seconds"] - raw["completion_seconds"], 4),
        **attribution,
        "ttft_overhead_seconds": round(hades["ttft_seconds"] - raw["ttft_seconds"], 4),
        "prompt_token_delta": (
            hades["prompt_tokens"] - raw["prompt_tokens"]
            if isinstance(hades.get("prompt_tokens"), int) and isinstance(raw.get("prompt_tokens"), int)
            else None
        ),
        "non_prep_overhead_seconds": round(
            hades["completion_seconds"]
            - raw["completion_seconds"]
            - float(hades.get("context_construction_seconds") or 0),
            4,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()
    if not _local_endpoint(args.endpoint):
        parser.error("this benchmark only permits explicitly recognized local endpoints")
    report = asyncio.run(run(args))
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
