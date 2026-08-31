#!/usr/bin/env python3
"""Measure Hades semantic-control-plane complexity without rewarding moves.

The counted module set is deliberately explicit.  If semantic decision code is
moved, the destination must be added here before comparing checkpoints.
This is a diagnostic/release metric, not a formatter or a code-quality gate by
itself.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
COUNTED_MODULES = (
    "src/agent_loop.py",
    "src/aci.py",
    "src/intent_contracts.py",
    "src/capability_registry.py",
    "src/action_intents.py",
    "src/tool_capabilities.py",
    "src/capability_dependencies.py",
    "src/field_resolvers.py",
    "src/domain_resolvers/reminders.py",
    "src/domain_resolvers/recipe.py",
    "src/domain_resolvers/inventory.py",
    "src/domain_resolvers/memory.py",
    "src/domain_resolvers/work.py",
    "src/result_renderers/work.py",
    "src/result_renderers/memory.py",
    "src/result_renderers/homelab.py",
    "src/result_renderers/scheduled.py",
    "src/result_renderers/calendar.py",
    "src/result_renderers/recipe.py",
    "src/result_renderers/generic.py",
    "src/result_renderers/notes.py",
    "src/result_renderers/assets.py",
    "src/result_renderers/household.py",
    "src/legacy_agent_loop.py",
)


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def python_metrics(path: Path) -> dict[str, Any]:
    text = source(path)
    result: dict[str, Any] = {"loc": len(text.splitlines()), "functions": []}
    if not text:
        return result
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        result["syntax_error"] = str(exc)
        return result
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            result["functions"].append(
                {"name": node.name, "line": node.lineno, "loc": end - node.lineno + 1}
            )
    result["functions"].sort(key=lambda item: item["loc"], reverse=True)
    result["largest_functions"] = result["functions"][:20]
    return result


def count_regex(paths: list[Path], pattern: str) -> int:
    expression = re.compile(pattern, re.MULTILINE)
    return sum(len(expression.findall(source(path))) for path in paths)


def imports_from(paths: list[Path], pattern: str) -> list[str]:
    expression = re.compile(pattern, re.MULTILINE)
    matches: list[str] = []
    for path in paths:
        for line_no, line in enumerate(source(path).splitlines(), 1):
            if expression.search(line):
                matches.append(f"{path.relative_to(ROOT)}:{line_no}:{line.strip()}")
    return matches


def top_level_imports_from(paths: list[Path], pattern: str) -> list[str]:
    """Find eager feature imports, excluding intentionally lazy function imports."""
    expression = re.compile(pattern)
    matches: list[str] = []
    for path in paths:
        text = source(path)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            line = text.splitlines()[node.lineno - 1]
            if expression.search(line):
                matches.append(f"{path.relative_to(ROOT)}:{node.lineno}:{line.strip()}")
    return matches


def frontend_metrics() -> dict[str, Any]:
    css = list((ROOT / "static").glob("**/*.css"))
    js = list((ROOT / "static").glob("**/*.js"))
    return {
        "css_bytes": sum(path.stat().st_size for path in css),
        "css_files": len(css),
        "js_bytes": sum(path.stat().st_size for path in js),
        "js_files": len(js),
        "largest_assets": [
            {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size}
            for path in sorted(css + js, key=lambda item: item.stat().st_size, reverse=True)[:20]
        ],
    }


def modularity_metrics() -> dict[str, Any]:
    """Measure the cheap manifest/runtime boundary without loading features."""
    try:
        from src.module_manager import ModuleManager

        manager = ModuleManager()
        manifests = manager.manifests
        enabled = manager.enabled_module_ids()
        unrelated = ModuleManager(enabled_modules=set(enabled))
        recipe = ModuleManager(enabled_modules=set(enabled))
        recipe.activate_for_capability("recipe.read")
        kernel_paths = [
            ROOT / item
            for item in ("src/aci.py", "src/agent_loop.py", "src/intent_contracts.py")
        ]
        feature_imports = top_level_imports_from(
            kernel_paths,
            r"(?:from|import)\s+src\.(?:domain_resolvers|result_renderers)\.(?:recipe|inventory|memory|work|reminders)",
        )
        dependency_cycles: list[tuple[str, ...]] = []

        def visit(node: str, path: tuple[str, ...]) -> None:
            if node in path:
                dependency_cycles.append(path[path.index(node):] + (node,))
                return
            for dependency in manifests[node].dependencies:
                if dependency in manifests:
                    visit(dependency, path + (node,))

        for module_id in manifests:
            visit(module_id, ())
        return {
            "installed_modules": len(manifests),
            "enabled_modules": len(enabled),
            "enabled_module_ids": sorted(enabled),
            "eagerly_imported_feature_modules": feature_imports,
            "feature_specific_kernel_import_count": len(feature_imports),
            "representative_activation": {
                "unrelated_request": sorted(unrelated.active_module_ids()),
                "recipe_request": sorted(recipe.active_module_ids()),
            },
            "background_worker_start_sites_at_boot": count_regex(
                [ROOT / "src/agent_loop.py"],
                r"\b(?:create_task|Thread|Process|start_background|start_scheduler)\s*\(",
            ),
            "dependency_edges": sum(len(spec.dependencies) for spec in manifests.values()),
            "dependency_cycles": dependency_cycles,
        }
    except Exception as exc:
        return {"error": f"module metrics unavailable: {type(exc).__name__}: {exc}"}


def require_clean_worktree() -> None:
    """Refuse release metrics that cannot be tied to committed source."""
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=ROOT, text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"unable to verify worktree cleanliness: {exc}") from exc
    if status.strip():
        raise SystemExit(
            "architecture metrics require a clean worktree; "
            "commit or discard changes before generating release evidence"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--state",
        type=Path,
        help="Update current_state.json architecture_current from the generated metrics.",
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Fail before measuring unless the repository worktree is clean.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Diagnostic-only override; release evidence requires a clean tree by default.",
    )
    args = parser.parse_args()
    if not args.allow_dirty:
        require_clean_worktree()
    counted_paths = [ROOT / item for item in COUNTED_MODULES]
    semantic_paths = [path for path in counted_paths if path.exists()]
    production_paths = [path for path in (ROOT / "src").glob("**/*.py") if path.name != "__init__.py"]
    tests = list((ROOT / "tests").glob("**/*.py"))
    all_text = "\n".join(source(path) for path in semantic_paths)
    data: dict[str, Any] = {
        "schema": "hades-architecture-metrics.v1",
        "counted_module_set": [str(path.relative_to(ROOT)) for path in semantic_paths],
        "modules": {str(path.relative_to(ROOT)): python_metrics(path) for path in semantic_paths},
        "semantic_control_plane_loc": sum(python_metrics(path)["loc"] for path in semantic_paths),
        "central_domain_conditionals": count_regex(
            [ROOT / "src/aci.py", ROOT / "src/intent_contracts.py"],
            r"\b(?:domain|concept|operation)\s*(?:==|in|\.get\()",
        ),
        "central_canonical_answer_functions": count_regex(
            [ROOT / "src/aci.py", ROOT / "src/intent_contracts.py"],
            r"^(?:async\s+)?def\s+canonical_[A-Za-z0-9_]+_answer\s*\(",
        ),
        "canonical_answer_dispatch_mentions": count_regex(
            [ROOT / "src/aci.py"], r"canonical_[A-Za-z0-9_]+_answer\s*\("
        ),
        "compatibility_aliases": count_regex(
            semantic_paths,
            r"^\s*[A-Za-z][A-Za-z0-9_]*\s*=\s*(?:_?legacy|_?classify|.*compatibility)",
        ),
        "capability_action_map_declarations": count_regex(
            semantic_paths,
            r"^\s*[A-Z][A-Z0-9_]*(?:CAPABILITY|ACTION|TOOL|DOMAIN|BINDING)[A-Z0-9_]*\s*=",
        ),
        "production_legacy_semantic_imports": imports_from(
            production_paths,
            r"(?:from|import)\s+.*(?:legacy_agent_loop|_classify_agent_request)",
        ),
        "product_tests_private_legacy_classifier_imports": imports_from(
            tests, r"(?:from|import)\s+src\.agent_loop.*_classify_agent_request"
        ),
        "product_tests_legacy_tool_map_imports": imports_from(
            tests, r"(?:from|import)\s+src\.agent_loop.*_DOMAIN_TOOL_MAP"
        ),
        "src_to_routes_imports": imports_from(production_paths, r"(?:from|import)\s+routes(?:\.|\s)"),
        "frontend": frontend_metrics(),
        "modularity": modularity_metrics(),
        "source_sha": None,
        "notes": "Code movement does not reduce this metric; update COUNTED_MODULES when semantic ownership moves.",
    }
    try:
        import subprocess

        data["source_sha"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    rendered = json.dumps(data, indent=2, sort_keys=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.state:
        state = json.loads(args.state.read_text(encoding="utf-8"))
        current = state.get("architecture_current")
        if not isinstance(current, dict):
            current = {}
        # Keep measured architecture numbers in one generated artifact.  The
        # state file records where to read them, alongside human evidence that
        # is not derivable from source metrics.
        for key in (
            "semantic_control_plane_loc", "agent_loop_py_loc", "aci_py_loc",
            "intent_contracts_py_loc", "field_resolvers_py_loc",
            "central_domain_conditionals", "central_canonical_answer_functions",
            "canonical_answer_dispatch_mentions",
        ):
            current.pop(key, None)
        current.update({
            "measured_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
            "artifact": str(args.output) if args.output else "generated stdout",
            "metrics_artifact": str(args.output) if args.output else "generated stdout",
        })
        state["architecture_current"] = current
        args.state.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
