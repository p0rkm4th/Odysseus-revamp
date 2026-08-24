"""Bounded prerequisite resolution for first-class Hades capabilities.

This is intentionally a small registry, not a general package-manager oracle.
Capabilities select prerequisites; the registry resolves only the packages
needed by those supported capabilities on a known platform.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import shutil
from hashlib import sha256
import json
from typing import Iterable


@dataclass(frozen=True)
class CapabilityPrerequisite:
    capability: str
    executables: tuple[str, ...]
    packages: dict[str, str]


REGISTRY: dict[str, CapabilityPrerequisite] = {
    "network_discovery": CapabilityPrerequisite(
        "network_discovery", ("nmap",), {"arch": "nmap", "debian": "nmap", "ubuntu": "nmap"}
    ),
    "network_interface_inspection": CapabilityPrerequisite(
        "network_interface_inspection", ("ip", "ss"), {"arch": "iproute2", "debian": "iproute2", "ubuntu": "iproute2"}
    ),
    "dns_diagnostics": CapabilityPrerequisite(
        "dns_diagnostics", ("dig", "host", "nslookup"), {"arch": "bind", "debian": "bind9", "ubuntu": "bind9"}
    ),
    "route_diagnostics": CapabilityPrerequisite(
        "route_diagnostics", ("traceroute",), {"arch": "traceroute", "debian": "traceroute", "ubuntu": "traceroute"}
    ),
}


def supported_capabilities() -> tuple[str, ...]:
    return tuple(sorted(REGISTRY))


def host_platform() -> str:
    """Return a deliberately small platform key from os-release."""
    configured = os.environ.get("HADES_HOST_PLATFORM", "").strip().lower()
    if configured in {"arch", "debian", "ubuntu"}:
        return configured
    values: dict[str, str] = {}
    try:
        for line in open("/etc/os-release", encoding="utf-8"):
            key, _, value = line.rstrip().partition("=")
            values[key] = value.strip('"')
    except OSError:
        pass
    ident = (values.get("ID") or "").lower()
    if ident in {"arch", "garuda", "manjaro", "endeavouros"}:
        return "arch"
    if ident in {"debian", "linuxmint", "pop"}:
        return "debian"
    if ident == "ubuntu":
        return "ubuntu"
    return ident or platform.system().lower()


def package_manager(platform_key: str | None = None) -> str | None:
    """Return the expected manager for the host platform.

    Hades itself may run in a container without the host package manager. The
    privileged broker performs the live manager check; planning must still be
    deterministic from the host-platform key.
    """
    key = platform_key or host_platform()
    return "pacman" if key == "arch" else "apt-get" if key in {"debian", "ubuntu"} else None


def package_manager_available(platform_key: str | None = None) -> bool:
    key = platform_key or host_platform()
    expected = package_manager(key)
    return bool(expected and shutil.which(expected))


def resolve(capability: str, *, available: Iterable[str] | None = None, platform_key: str | None = None) -> dict:
    """Resolve missing executables to exact allowlisted package names."""
    spec = REGISTRY.get(str(capability or ""))
    if spec is None:
        return {"capability": capability, "status": "unavailable", "reason": "unsupported_capability", "remediation_available": False, "packages": []}
    present = set(available) if available is not None else {name for name in spec.executables if shutil.which(name)}
    missing = [name for name in spec.executables if name not in present]
    key = platform_key or host_platform()
    manager = package_manager(key)
    package = spec.packages.get(key)
    if not missing:
        status = "available"
    elif package and manager and package in _allowlisted_packages():
        status = "remediation_available"
    else:
        status = "unavailable"
    result = {
        "capability": spec.capability,
        "executables": list(spec.executables),
        "missing_executables": missing,
        "platform": key,
        "package_manager": manager,
        "package_manager_available": package_manager_available(key),
        "packages": [package] if package else [],
        "status": status,
        "remediation_available": status == "remediation_available",
    }
    return result


def _allowlisted_packages() -> frozenset[str]:
    # Import lazily to keep this registry usable by startup/read-only health.
    from src.privileged_broker import ALLOWED_PACKAGES
    return frozenset(ALLOWED_PACKAGES)


def capability_health(capability: str, *, available: Iterable[str] | None = None, platform_key: str | None = None) -> dict:
    return resolve(capability, available=available, platform_key=platform_key)


def remediation_handoff(capability: str, *, run_id: str, action_id: str,
                        approval_reference: str | None = None,
                        platform_key: str | None = None) -> dict:
    """Create a durable, identity-preserving prerequisite handoff.

    This is metadata for the existing Work approval/resume engine. It never
    grants approval or executes a package manager. The original run/action
    identifiers are carried through install and verification so a caller
    cannot accidentally create a replacement run as a side effect.
    """
    health = resolve(capability, available=[], platform_key=platform_key)
    if not health.get("remediation_available"):
        raise ValueError("no approved prerequisite remediation for capability")
    payload = {
        "capability": capability, "packages": health["packages"],
        "executables": health["executables"], "run_id": str(run_id),
        "action_id": str(action_id), "approval_reference": approval_reference,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {
        "kind": "prerequisite_remediation", "handoff_digest": sha256(canonical.encode()).hexdigest(),
        "resume_same_run": True, "resume_same_action": True, **payload,
        "capability_health": health,
    }
