"""Deterministic scoring and regression checks for Jarvis benchmark runs.

The evaluator deliberately operates on normalized, secret-free run records.
Live-provider adapters and Odysseus trace exporters can evolve independently;
CI can always replay checked-in fixtures without network or model access.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json
import math


SCHEMA_VERSION = 1
FAILURE_CATEGORIES = frozenset(
    {
        "none",
        "timeout",
        "provider_error",
        "wrong_tool",
        "malformed_tool_args",
        "tool_error_unrecovered",
        "instruction_failure",
        "security_violation",
        "context_failure",
        "quality_failure",
        "unknown",
    }
)


class BenchmarkFormatError(ValueError):
    """Raised when a suite or run record violates the benchmark contract."""


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    category: str
    passed: bool
    score: float
    checks: dict[str, bool]
    failures: tuple[str, ...]


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BenchmarkFormatError(
                    f"{path}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
            if not isinstance(record, dict):
                raise BenchmarkFormatError(
                    f"{path}:{line_number}: each record must be an object"
                )
            records.append(record)
    return records


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkFormatError(f"{label} must be a non-empty string")
    return value.strip()


def validate_suite(suite: Any) -> dict[str, Any]:
    if not isinstance(suite, dict):
        raise BenchmarkFormatError("suite must be an object")
    if suite.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkFormatError(
            f"suite schema_version must be {SCHEMA_VERSION}"
        )
    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise BenchmarkFormatError("suite.cases must be a non-empty list")
    seen = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise BenchmarkFormatError(f"cases[{index}] must be an object")
        case_id = _require_string(case.get("id"), f"cases[{index}].id")
        if case_id in seen:
            raise BenchmarkFormatError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        _require_string(case.get("category"), f"case {case_id}.category")
        _require_string(case.get("prompt"), f"case {case_id}.prompt")
        expected = case.get("expected")
        if not isinstance(expected, dict) or not expected:
            raise BenchmarkFormatError(f"case {case_id}.expected must be an object")
        weight = case.get("weight", 1.0)
        if not isinstance(weight, (int, float)) or weight <= 0:
            raise BenchmarkFormatError(f"case {case_id}.weight must be positive")
    return suite


def validate_run(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise BenchmarkFormatError("run record must be an object")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkFormatError(
            f"run schema_version must be {SCHEMA_VERSION}"
        )
    _require_string(record.get("case_id"), "run.case_id")
    model = record.get("model")
    if not isinstance(model, dict):
        raise BenchmarkFormatError("run.model must be an object")
    for field in ("provider", "name"):
        _require_string(model.get(field), f"run.model.{field}")
    hardware = record.get("hardware")
    if not isinstance(hardware, dict):
        raise BenchmarkFormatError("run.hardware must be an object")
    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        raise BenchmarkFormatError("run.metrics must be an object")
    failure = record.get("failure_category", "none")
    if failure not in FAILURE_CATEGORIES:
        raise BenchmarkFormatError(f"unknown failure_category: {failure}")
    tool_calls = record.get("tool_calls", [])
    if not isinstance(tool_calls, list) or any(not isinstance(x, dict) for x in tool_calls):
        raise BenchmarkFormatError("run.tool_calls must be a list of objects")
    return record


def _contains(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def _mapping_contains(actual: Any, expected: Any) -> bool:
    """Return whether actual recursively contains the expected JSON fragment."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _mapping_contains(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and all(
            any(_mapping_contains(item, wanted) for item in actual)
            for wanted in expected
        )
    return actual == expected


def score_case(case: dict[str, Any], record: dict[str, Any]) -> CaseScore:
    validate_run(record)
    case_id = case["id"]
    if record["case_id"] != case_id:
        raise BenchmarkFormatError(
            f"record case_id {record['case_id']!r} does not match {case_id!r}"
        )
    expected = case["expected"]
    calls = record.get("tool_calls", [])
    call_names = [str(call.get("name", "")) for call in calls]
    response = str(record.get("assistant_text", ""))
    checks: dict[str, bool] = {}

    for tool_name in expected.get("required_tools", []):
        checks[f"required_tool:{tool_name}"] = tool_name in call_names
    for tool_name in expected.get("forbidden_tools", []):
        checks[f"forbidden_tool:{tool_name}"] = tool_name not in call_names

    for index, wanted in enumerate(expected.get("tool_args", [])):
        name = wanted.get("name")
        args = wanted.get("contains", {})
        checks[f"tool_args:{index}:{name}"] = any(
            call.get("name") == name
            and _mapping_contains(call.get("arguments", {}), args)
            for call in calls
        )

    for text in expected.get("response_contains", []):
        checks[f"response_contains:{text}"] = _contains(response, str(text))
    for text in expected.get("response_excludes", []):
        checks[f"response_excludes:{text}"] = not _contains(response, str(text))
    if "response_exact" in expected:
        checks["response_exact"] = response.strip() == str(expected["response_exact"]).strip()

    if "max_tool_calls" in expected:
        checks["max_tool_calls"] = len(calls) <= int(expected["max_tool_calls"])
    if expected.get("requires_recovery"):
        checks["requires_recovery"] = bool(record.get("recovered"))
    if expected.get("must_refuse"):
        checks["must_refuse"] = bool(record.get("refused"))
    if expected.get("manual_rubric"):
        rubric = record.get("rubric_score")
        checks["manual_rubric"] = (
            isinstance(rubric, (int, float))
            and float(rubric) >= float(expected.get("min_rubric_score", 0.7))
        )

    failure_category = record.get("failure_category", "none")
    checks["no_runtime_failure"] = failure_category == "none"
    failures = tuple(name for name, passed in checks.items() if not passed)
    score = sum(checks.values()) / len(checks) if checks else 0.0
    pass_threshold = float(case.get("pass_threshold", 1.0))
    return CaseScore(
        case_id=case_id,
        category=case["category"],
        passed=score >= pass_threshold,
        score=round(score, 4),
        checks=checks,
        failures=failures,
    )


def summarize(suite: dict[str, Any], records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    suite = validate_suite(suite)
    by_id = {}
    for record in records:
        validate_run(record)
        case_id = record["case_id"]
        if case_id in by_id:
            raise BenchmarkFormatError(f"duplicate run record for case: {case_id}")
        by_id[case_id] = record

    known = {case["id"] for case in suite["cases"]}
    unknown = sorted(set(by_id) - known)
    if unknown:
        raise BenchmarkFormatError(f"run contains unknown cases: {', '.join(unknown)}")

    scores = []
    weighted_points = 0.0
    weighted_total = 0.0
    category_points: dict[str, float] = defaultdict(float)
    category_total: dict[str, float] = defaultdict(float)
    failure_counts: Counter[str] = Counter()
    metric_values: dict[str, list[float]] = defaultdict(list)

    for case in suite["cases"]:
        weight = float(case.get("weight", 1.0))
        weighted_total += weight
        category_total[case["category"]] += weight
        record = by_id.get(case["id"])
        if record is None:
            result = CaseScore(
                case_id=case["id"], category=case["category"], passed=False,
                score=0.0, checks={"record_present": False},
                failures=("record_present",),
            )
            failure_counts["missing_record"] += 1
        else:
            result = score_case(case, record)
            failure_counts[record.get("failure_category", "none")] += 1
            for name, value in record.get("metrics", {}).items():
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    metric_values[name].append(float(value))
        weighted_points += result.score * weight
        category_points[result.category] += result.score * weight
        scores.append(
            {
                "case_id": result.case_id,
                "category": result.category,
                "passed": result.passed,
                "score": result.score,
                "failures": list(result.failures),
            }
        )

    def percentile(values: list[float], fraction: float) -> float:
        ordered = sorted(values)
        if not ordered:
            return 0.0
        index = max(0, math.ceil(len(ordered) * fraction) - 1)
        return round(ordered[index], 4)

    metrics = {
        name: {
            "mean": round(sum(values) / len(values), 4),
            "p50": percentile(values, 0.50),
            "p95": percentile(values, 0.95),
            "samples": len(values),
        }
        for name, values in sorted(metric_values.items())
    }
    first_model = next(iter(by_id.values()), {}).get("model", {})
    first_hardware = next(iter(by_id.values()), {}).get("hardware", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "suite": suite.get("name", "jarvis"),
        "model": first_model,
        "hardware": first_hardware,
        "case_count": len(suite["cases"]),
        "record_count": len(by_id),
        "success_rate": round(sum(item["passed"] for item in scores) / len(scores), 4),
        "weighted_score": round(weighted_points / weighted_total, 4),
        "category_scores": {
            name: round(category_points[name] / total, 4)
            for name, total in sorted(category_total.items())
        },
        "failure_categories": dict(sorted(failure_counts.items())),
        "metrics": metrics,
        "cases": scores,
    }


def compare_reports(
    baseline: dict[str, Any], candidate: dict[str, Any], thresholds: dict[str, Any]
) -> dict[str, Any]:
    """Apply explicit quality floors and relative latency/prompt budgets."""
    failures = []
    min_weighted = float(thresholds.get("min_weighted_score", 0.0))
    max_score_drop = float(thresholds.get("max_weighted_score_drop", 0.0))
    candidate_score = float(candidate.get("weighted_score", 0.0))
    baseline_score = float(baseline.get("weighted_score", 0.0))
    if candidate_score < min_weighted:
        failures.append("weighted_score_below_floor")
    if candidate_score < baseline_score - max_score_drop:
        failures.append("weighted_score_regressed")

    category_drop = float(thresholds.get("max_category_score_drop", 0.0))
    for category, old_score in baseline.get("category_scores", {}).items():
        new_score = candidate.get("category_scores", {}).get(category, 0.0)
        if float(new_score) < float(old_score) - category_drop:
            failures.append(f"category_regressed:{category}")

    for metric, allowed_ratio in thresholds.get("max_metric_p95_ratio", {}).items():
        old = baseline.get("metrics", {}).get(metric, {}).get("p95")
        new = candidate.get("metrics", {}).get(metric, {}).get("p95")
        if isinstance(old, (int, float)) and old > 0 and isinstance(new, (int, float)):
            if new > old * float(allowed_ratio):
                failures.append(f"metric_p95_regressed:{metric}")

    return {"passed": not failures, "failures": failures}
