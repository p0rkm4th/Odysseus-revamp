"""Small internal module lifecycle for the Hades capability kernel.

Manifests are deliberately cheap metadata.  They do not import feature
implementations, grant authority, or replace the canonical capability
registry.  A module becomes ACTIVE only when a request explicitly activates
one of its capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import importlib
import os
from types import MappingProxyType
from typing import Any, Mapping

from src.capability_registry import CAPABILITY_REGISTRY, TOOL_CAPABILITY_IDS


class ModuleState(StrEnum):
    AVAILABLE = "AVAILABLE"
    ENABLED = "ENABLED"
    ACTIVE = "ACTIVE"


@dataclass(frozen=True)
class ModuleSpec:
    module_id: str
    capability_ids: tuple[str, ...]
    runtime_entrypoint: str | None = None
    default_enabled: bool = True
    dependencies: tuple[str, ...] = ()
    resource_policy: str = "on_request"


_MODULES: Mapping[str, ModuleSpec] = MappingProxyType({
    "core": ModuleSpec("core", (), default_enabled=True, resource_policy="always"),
    "recipes": ModuleSpec(
        "recipes",
        ("recipe.read", "recipe.manage"),
        runtime_entrypoint="src.domain_resolvers.recipe",
        resource_policy="on_request",
    ),
    "household": ModuleSpec("household", ("household.read", "inventory.manage")),
    "memory": ModuleSpec("memory", ("memory.read", "memory.manage")),
    "work": ModuleSpec(
        "work",
        tuple(capability_id for capability_id in CAPABILITY_REGISTRY if capability_id.startswith("work.")),
    ),
    "automation": ModuleSpec("automation", ("automation.task.manage",)),
    "network": ModuleSpec("network", ("homelab.manage",)),
    "notes": ModuleSpec("notes", ("notes.read", "notes.manage")),
})

# Keep existing capabilities available by default while their vertical owners
# are migrated.  This is a compatibility bucket, not a second registry; each
# capability still has exactly one semantic definition in capability_registry.
_owned_capabilities = {
    capability_id
    for spec in _MODULES.values()
    for capability_id in spec.capability_ids
}
_unowned_capabilities = tuple(
    capability_id for capability_id in CAPABILITY_REGISTRY
    if capability_id not in _owned_capabilities
)
if _unowned_capabilities:
    _MODULES = MappingProxyType({
        **dict(_MODULES),
        "legacy-capabilities": ModuleSpec(
            "legacy-capabilities", _unowned_capabilities,
        ),
    })


class ModuleManager:
    """Resolve enabled capabilities and lazily import selected implementations."""

    def __init__(
        self,
        manifests: Mapping[str, ModuleSpec] | None = None,
        *,
        enabled_modules: set[str] | frozenset[str] | None = None,
    ) -> None:
        self.manifests = MappingProxyType(dict(manifests or _MODULES))
        configured = enabled_modules
        if configured is None:
            disabled = {
                item.strip().casefold()
                for item in os.environ.get("HADES_DISABLED_MODULES", "").split(",")
                if item.strip()
            }
            configured = frozenset(
                module_id for module_id, spec in self.manifests.items()
                if spec.default_enabled and module_id not in disabled
            )
        unknown = set(configured) - set(self.manifests)
        if unknown:
            raise ValueError(f"unknown Hades module(s): {', '.join(sorted(unknown))}")
        self._enabled = frozenset(configured)
        self._active: set[str] = set()
        self._loaded: dict[str, Any] = {}

    def state(self, module_id: str) -> ModuleState:
        if module_id not in self.manifests:
            raise KeyError(module_id)
        if module_id in self._active:
            return ModuleState.ACTIVE
        if module_id in self._enabled:
            return ModuleState.ENABLED
        return ModuleState.AVAILABLE

    def enabled_module_ids(self) -> frozenset[str]:
        return self._enabled

    def active_module_ids(self) -> frozenset[str]:
        return frozenset(self._active)

    def enabled_capability_ids(self) -> frozenset[str]:
        """Return capabilities whose owning module and dependencies are enabled."""
        result: set[str] = set()
        for module_id in self._enabled:
            spec = self.manifests[module_id]
            if all(dependency in self._enabled for dependency in spec.dependencies):
                result.update(spec.capability_ids)
        return frozenset(result)

    def disabled_tool_names(self) -> frozenset[str]:
        enabled = self.enabled_capability_ids()
        return frozenset(
            tool_name for tool_name, capability_id in TOOL_CAPABILITY_IDS.items()
            if capability_id not in enabled
        )

    def owner_for_capability(self, capability_id: str) -> str | None:
        return next(
            (module_id for module_id, spec in self.manifests.items()
             if capability_id in spec.capability_ids),
            None,
        )

    def activate_for_capability(self, capability_id: str) -> Any:
        module_id = self.owner_for_capability(capability_id)
        if module_id is None:
            raise KeyError(f"no module owns capability {capability_id}")
        if module_id not in self._enabled:
            raise RuntimeError(f"module disabled: {module_id}")
        spec = self.manifests[module_id]
        if not all(dependency in self._enabled for dependency in spec.dependencies):
            raise RuntimeError(f"module dependency disabled: {module_id}")
        if module_id not in self._active:
            self._loaded[module_id] = (
                importlib.import_module(spec.runtime_entrypoint)
                if spec.runtime_entrypoint else None
            )
            self._active.add(module_id)
        return self._loaded[module_id]


def default_module_manager() -> ModuleManager:
    """Build a request-scoped manager from owner/runtime module settings."""
    return ModuleManager()


__all__ = ["ModuleManager", "ModuleSpec", "ModuleState", "default_module_manager"]
