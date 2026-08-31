#!/usr/bin/env python3
"""Select the cheapest validation lane that can disprove a Git diff.

This is intentionally a conservative classifier, not a second test registry.
It reports impact evidence for humans/CI; candidate and release gates remain
authoritative.  Source ownership is read from the canonical module manifests
where possible, while shared authority files escalate broadly by contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import PurePosixPath
import sys


SHARED_ESCALATION = {
    "src/aci.py": "kernel_runtime",
    "src/agent_loop.py": "kernel_runtime",
    "src/intent_contracts.py": "semantic_contract",
    "src/action_intents.py": "semantic_contract",
    "src/capability_registry.py": "capability_registry",
    "src/module_manager.py": "module_lifecycle",
    "src/capability_dependencies.py": "dependencies",
    "src/tool_execution.py": "execution",
    "src/policy.py": "policy",
    "src/approval.py": "approval",
    "src/completion.py": "completion",
}

IMPACT_RULES = (
    ("persistence", ("core/", "src/database", "src/persistence", "migrations/")),
    ("browser_transport", ("static/js/chat", "scripts/browser_", "routes/chat")),
    ("frontend", ("static/", "templates/")),
    ("semantic_retrieval", ("src/action_retriever.py", "src/semantic/")),
    ("evaluation", ("benchmarks/", ".github/scripts/")),
    ("tooling", ("scripts/",)),
)


def classify_path(path: str) -> set[str]:
    """Return stable impact labels for one repository-relative path."""
    normalized = PurePosixPath(path).as_posix()
    labels = set()
    if normalized in SHARED_ESCALATION:
        labels.add(SHARED_ESCALATION[normalized])
    for label, prefixes in IMPACT_RULES:
        if any(normalized == prefix or normalized.startswith(prefix) for prefix in prefixes):
            labels.add(label)
    if normalized.startswith("src/domain_resolvers/") or normalized.startswith("src/field_resolvers"):
        labels.add("module_semantics")
    if normalized.startswith("src/result_renderers/"):
        labels.add("rendering")
    if normalized.startswith("tests/"):
        labels.add("tests")
    if normalized.endswith((".md", ".json", ".jsonl")) and not normalized.startswith("benchmarks/"):
        labels.add("non_executable")
    return labels or {"unknown"}


def recommend_lane(labels: set[str]) -> str:
    """Choose a conservative lane from impact, with shared authority winning."""
    if labels & {"policy", "approval", "execution", "dependencies", "persistence", "completion", "kernel_runtime"}:
        return "C"
    if labels & {"semantic_contract", "capability_registry", "module_lifecycle", "semantic_retrieval", "module_semantics", "browser_transport", "rendering", "frontend"}:
        return "B"
    return "A"


def analyze(paths: list[str]) -> dict[str, object]:
    labels_by_path = {path: sorted(classify_path(path)) for path in sorted(set(paths))}
    labels = {label for values in labels_by_path.values() for label in values}
    lane = recommend_lane(labels)
    return {
        "schema": "hades-test-impact.v1",
        "paths": labels_by_path,
        "impact_labels": sorted(labels),
        "recommended_lane": lane,
        "escalations": {
            "semantic": bool(labels & {"semantic_contract", "capability_registry", "semantic_retrieval", "module_semantics"}),
            "broad_authority": bool(labels & {"policy", "approval", "execution", "dependencies", "persistence", "completion", "kernel_runtime"}),
            "browser": "browser_transport" in labels or "frontend" in labels,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Changed repository-relative paths; stdin is used when omitted.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)
    paths = args.paths or [line.strip() for line in sys.stdin if line.strip()]
    result = analyze(paths)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"recommended_lane={result['recommended_lane']}")
        print("impact=" + ",".join(result["impact_labels"]))
        for path, labels in result["paths"].items():
            print(f"{path}: {','.join(labels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
