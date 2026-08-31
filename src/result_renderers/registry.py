"""Declarative, lazy Result renderer projection.

The registry contains only provenance and import metadata. Feature renderer
modules are loaded when a Result actually needs one, never while the kernel is
imported. It is a projection registry, not an authority or persistence layer.
"""

from __future__ import annotations

import importlib
import json
from typing import Any, Mapping, Sequence


RENDERER_SPECS: tuple[tuple[str, str, str], ...] = (
    ("recipe mutation Result", "src.result_renderers.recipe", "canonical_recipe_mutation_answer"),
    ("inventory mutation Result", "src.result_renderers.household", "canonical_inventory_mutation_answer"),
    ("Work mutation Result", "src.result_renderers.work", "canonical_work_mutation_answer"),
    ("Memory mutation Result", "src.result_renderers.memory", "canonical_memory_mutation_answer"),
    ("canonical Notes Result", "src.result_renderers.notes", "canonical_notes_read_answer"),
    ("canonical scheduled task Result", "src.result_renderers.scheduled", "canonical_scheduled_task_read_answer"),
    ("notes mutation Result", "src.result_renderers.notes", "canonical_notes_mutation_answer"),
    ("scheduled task Result", "src.result_renderers.scheduled", "canonical_scheduled_task_mutation_answer"),
    ("canonical Memory Result", "src.result_renderers.memory", "canonical_memory_read_answer"),
    ("canonical Work Result", "src.result_renderers.work", "canonical_work_read_answer"),
    ("canonical Calendar Result", "src.result_renderers.calendar", "canonical_communications_read_answer"),
    ("canonical bounded Network plan", "src.result_renderers.homelab", "canonical_network_plan_answer"),
    ("canonical Network Result", "src.result_renderers.homelab", "canonical_network_read_answer"),
    ("canonical Homelab Result", "src.result_renderers.homelab", "canonical_homelab_read_answer"),
    ("canonical Service Result", "src.result_renderers.homelab", "canonical_service_read_answer"),
    ("canonical Asset Result", "src.result_renderers.assets", "canonical_asset_read_answer"),
    ("canonical Household Result", "src.result_renderers.household", "canonical_household_read_answer"),
    ("canonical Recipe Result", "src.result_renderers.recipe", "canonical_recipe_read_answer"),
    ("canonical structured empty Result", "src.result_renderers.generic", "canonical_structured_empty_read_answer"),
)

# Result projection is deliberately kept beside the feature renderers.  The
# kernel only needs to ask for a bounded projection; it must not know which
# feature owns the payload shape.
PROJECTION_SPECS: dict[str, tuple[str, str, str]] = {
    "manage_memory": ("src.result_renderers.memory", "project_memory_result", "result"),
    "read_household": ("src.result_renderers.household", "project_household_result", "nested"),
    "read_recipes": ("src.result_renderers.recipe", "project_recipe_result", "recipe"),
    "manage_recipes": ("src.result_renderers.recipe", "project_recipe_result", "recipe"),
    "manage_assets": ("src.result_renderers.assets", "project_asset_result", "payload"),
    "read_work": ("src.result_renderers.work", "project_work_result", "payload"),
    "manage_homelab": ("src.result_renderers.homelab", "project_homelab_result", "payload"),
}


def project_result(tool_name: str, result: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return the bounded feature-owned projection for a canonical Result."""
    spec = PROJECTION_SPECS.get(str(tool_name or "").strip())
    if spec is None or not isinstance(result, Mapping):
        return None
    module_name, function_name, mode = spec
    projector = getattr(importlib.import_module(module_name), function_name)
    if mode == "result":
        return projector(result)

    if mode == "nested":
        raw = result.get("data") if isinstance(result.get("data"), Mapping) else result.get("output")
    else:
        raw = result.get("output")

    # A structured plan Result has no subprocess output and must retain its
    # exact bounded scope for the owner-facing renderer.
    if mode == "payload" and isinstance(result, Mapping):
        action = str(result.get("action") or "").strip()
        if action == "plan_network_discovery" and str(result.get("kind") or "").strip().lower() == "plan":
            return projector(result)
    payload = raw if isinstance(raw, Mapping) else None
    if payload is None:
        try:
            payload = json.loads(str(raw or ""))
        except (TypeError, ValueError):
            return None
    if not isinstance(payload, Mapping):
        return None
    if mode == "recipe":
        return projector(str(tool_name).strip(), result)
    return projector(payload)


def render_result(
    tool_events: Sequence[Mapping[str, Any]],
    *,
    enabled_module_ids: frozenset[str] | None = None,
) -> tuple[str, str] | None:
    """Return the first grounded renderer output and its provenance."""
    for provenance, module_name, function_name in RENDERER_SPECS:
        module_id = {
            "recipe": "recipes",
            "household": "household",
            "work": "work",
            "memory": "memory",
            "notes": "notes",
            "scheduled": "automation",
            "homelab": "network",
        }.get(module_name.rsplit(".", 1)[-1])
        if enabled_module_ids is not None and module_id and module_id not in enabled_module_ids:
            continue
        renderer = getattr(importlib.import_module(module_name), function_name)
        content = renderer(tool_events)
        if content:
            return provenance, content
    return None


__all__ = ["RENDERER_SPECS", "render_result"]
