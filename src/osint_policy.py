"""Safety and scope validation for public-source OSINT workflows."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse
from typing import Any


class OsintPolicyError(ValueError):
    pass


_SENSITIVE = re.compile(
    r"\b(?:passwords?|passcodes?|private keys?|credentials?|ssn|social security|"
    r"home address(?:es)?|doxx(?:ing)?|stalk(?:ing)?|track(?:ing)? a private person)\b",
    re.I,
)
_SOURCES = frozenset({"web_search", "web_fetch", "news", "security_advisory"})


def _text(value: Any, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise OsintPolicyError(f"{label} must be a non-empty string of at most {maximum} characters")
    return value.strip()


def _reject_sensitive(value: str) -> None:
    if _SENSITIVE.search(value):
        raise OsintPolicyError("OSINT is limited to lawful public-source research and cannot target private sensitive data")


def validate_target(target: Any) -> str:
    value = _text(target, "target", 256)
    _reject_sensitive(value)
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if parsed.username or parsed.password:
        raise OsintPolicyError("credential-bearing URLs are not allowed")
    if parsed.hostname:
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            address = None
        if address is not None and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved):
            raise OsintPolicyError("private, loopback, link-local, and reserved targets are not allowed")
    return value


def validate_request(request: dict[str, Any]) -> tuple[str, str, str, list[str]]:
    if not isinstance(request, dict):
        raise OsintPolicyError("arguments must be an object")
    action = str(request.get("action") or "").strip().casefold()
    if action not in {"plan", "search", "fetch"}:
        raise OsintPolicyError("OSINT action must be plan, search, or fetch")
    target = validate_target(request.get("target"))
    objective = _text(request.get("objective") or "public-source background research", "objective", 512)
    _reject_sensitive(objective)
    sources = request.get("sources") or ["web_search", "web_fetch"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= 4 or any(source not in _SOURCES for source in sources):
        raise OsintPolicyError("sources must contain 1 to 4 supported public-source types")
    return action, target, objective, list(dict.fromkeys(sources))


def build_plan(target: str, objective: str, sources: list[str]) -> dict[str, Any]:
    return {
        "scope": "public_source_only", "target": target, "objective": objective,
        "sources": sources,
        "steps": [
            "Search public indexed sources for the target and objective.",
            "Fetch only named public URLs returned by the search or supplied by the user.",
            "Cross-check material claims across independent sources and preserve citations.",
        ],
        "prohibited": ["credentialed access, private-network probing, bypassing access controls, or sensitive personal-data collection"],
    }
