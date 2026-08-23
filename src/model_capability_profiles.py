"""Deterministic agent policies for models with different capabilities.

Profiles are opt-in. The default preserves existing behavior; ``auto`` uses
only clear local-model size markers and never downgrades a hosted route based
on a guessed product name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import urlparse


@dataclass(frozen=True)
class ModelCapabilityProfile:
    name: str
    compact_prompt: bool = False
    max_output_tokens: int | None = None
    max_agent_rounds: int | None = None
    max_tool_calls: int | None = None
    max_selected_tools: int | None = None


_PROFILES = {
    "standard": ModelCapabilityProfile("standard"),
    "local_balanced": ModelCapabilityProfile(
        "local_balanced", compact_prompt=True, max_output_tokens=3072,
        max_agent_rounds=10, max_tool_calls=12, max_selected_tools=12,
    ),
    "local_small": ModelCapabilityProfile(
        "local_small", compact_prompt=True, max_output_tokens=2048,
        max_agent_rounds=6, max_tool_calls=6, max_selected_tools=8,
    ),
}
PROFILES = MappingProxyType(_PROFILES)

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"})
_SIZE_RE = re.compile(r"(?:^|[-_:./])([0-9]+(?:\.[0-9]+)?)b(?:$|[-_:./])", re.IGNORECASE)


def endpoint_is_local(endpoint_url: str) -> bool:
    try:
        host = (urlparse(endpoint_url or "").hostname or "").casefold()
    except ValueError:
        return False
    if host in _LOCAL_HOSTS or host.startswith("192.168.") or host.startswith("10."):
        return True
    if host.startswith("172."):
        try:
            return 16 <= int(host.split(".")[1]) <= 31
        except (IndexError, ValueError):
            return False
    return False


def infer_profile(endpoint_url: str, model: str) -> ModelCapabilityProfile:
    """Conservatively infer a profile for a clearly sized local model."""
    if not endpoint_is_local(endpoint_url):
        return PROFILES["standard"]
    sizes = [float(match) for match in _SIZE_RE.findall(model or "")]
    if not sizes:
        return PROFILES["standard"]
    parameter_billions = sizes[-1]
    if parameter_billions <= 9:
        return PROFILES["local_small"]
    if parameter_billions <= 34:
        return PROFILES["local_balanced"]
    return PROFILES["standard"]


def resolve_profile(requested: str | None, endpoint_url: str, model: str) -> ModelCapabilityProfile:
    name = (requested or "standard").strip().casefold().replace("-", "_")
    if name == "auto":
        return infer_profile(endpoint_url, model)
    try:
        return PROFILES[name]
    except KeyError as exc:
        choices = ", ".join(["auto", *PROFILES])
        raise ValueError(f"unknown model capability profile {requested!r}; choose {choices}") from exc


def clamp_budget(value: int, ceiling: int | None, *, zero_means_unlimited: bool = False) -> int:
    if ceiling is None:
        return value
    if zero_means_unlimited and value <= 0:
        return ceiling
    return min(value, ceiling)


def narrow_tools(tool_names: set[str] | None, profile: ModelCapabilityProfile, protected=()) -> set[str] | None:
    """Deterministically cap optional tools while retaining protected tools."""
    if tool_names is None or profile.max_selected_tools is None:
        return tool_names
    selected = set(tool_names)
    keep = selected & set(protected)
    remaining_slots = max(profile.max_selected_tools - len(keep), 0)
    keep.update(sorted(selected - keep)[:remaining_slots])
    return keep
