"""Bounded owner-facing Network field and scope extraction.

These functions produce semantic evidence only. Network authorization,
approval, probing, and observation persistence remain Hades-owned runtime
contracts.
"""

from __future__ import annotations

import ipaddress
import re


def explicit_private_discovery_cidr(text: str) -> str | None:
    """Extract an explicitly supplied, bounded private IPv4 discovery scope."""
    for address, _separator, prefix in re.findall(
        r"(?<![\w.])((?:\d{1,3}\.){3}\d{1,3})\s*([/\\])\s*(\d{1,2})(?!\w)",
        str(text or ""),
    ):
        try:
            network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
        except ValueError:
            continue
        if network.version == 4 and network.is_private and network.num_addresses <= 256:
            return str(network)
    return None


def network_discovery_request_cidr(text: str) -> str | None:
    """Return only a scope present in the current request."""
    return explicit_private_discovery_cidr(text)


def has_network_cidr_candidate(text: str) -> bool:
    """Detect a CIDR-shaped owner target, including safe separator typos."""
    return bool(re.search(
        r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}\s*[/\\]\s*\d{1,2}(?!\w)",
        str(text or ""),
    ))


def is_network_prerequisite_request(text: str) -> bool:
    """Recognize a request to prepare tools for bounded network work."""
    return bool(re.search(
        r"\b(?:install|setup|set up|prepare|need)\b.{0,100}"
        r"\b(?:tools?|utilities|packages?)\b.{0,100}"
        r"\b(?:network|nmap|scan|discovery)\b",
        str(text or "").lower(),
    ))


def is_explicit_network_discovery_request(text: str) -> bool:
    """Recognize actionable discovery language without authorizing it."""
    query = str(text or "").lower()
    if re.search(r"^\s*(?:what\s+is|what\s+are|define|explain|how\s+does)\b", query):
        return False
    return bool(
        re.search(r"\b(?:scan|discover|map|enumerate|identify|find)\b", query)
        and re.search(r"\b(?:network|lan|subnet|devices?|hosts?|192(?:\.168)?|rfc1918)\b", query)
    )


def is_network_service_enumeration_request(text: str) -> bool:
    """Recognize service-enumeration intent, not generic shell scanning."""
    query = str(text or "").lower()
    return bool(
        re.search(r"\b(?:service(?:s)?|port(?:s)?|version|enumeration|deeper|deep(?:er)? scan)\b", query)
        and re.search(r"\b(?:network|host(?:s)?|device(?:s)?|scan|discovery|nmap)\b", query)
    )


def explicitly_allows_diagnostic_install(query: str) -> bool:
    """Extract affirmative installation intent without granting authority."""
    q = str(query or "").lower().strip()
    if re.search(
        r"(?:\b(?:do\s+not|don't|dont|never)\b.{0,36}\b(?:install|add)\b|"
        r"\bwithout\s+(?:installing|adding)\b|\bno\s+(?:package\s+)?installs?\b|"
        r"\b(?:avoid|skip)\b.{0,28}\b(?:installing|installation|packages?)\b)", q,
    ):
        return False
    if re.search(
        r"(?:\b(?:you\s+can|you\s+may|you(?:'re|\s+are)\s+(?:allowed|authorized)|"
        r"feel\s+free\s+to|go\s+ahead\s+and)\b.{0,32}\b(?:install|add)\b|"
        r"\bpermission\s+(?:is\s+)?granted\b.{0,32}\b(?:install|add)\b)", q,
    ):
        return True
    if re.search(r"(?:^|[.!?;:]\s+|\bthen\s+|\band\s+then\s+)(?:please\s+)?(?:install|add)\b", q):
        return True
    return bool(re.search(
        r"(?:(?:^|[.!?;:]\s+|\bthen\s+|\band\s+then\s+)if\b.{0,36}\b(?:missing|needed|required|necessary|unavailable)\b.{0,52}\b(?:install|add)\b|"
        r"(?:^|[.!?;:]\s+|\bthen\s+|\band\s+then\s+)(?:please\s+)?(?:install|add)\b.{0,52}\bif\b.{0,40}\b(?:missing|needed|required|necessary|unavailable)\b)", q,
    ))


def network_substantive_fallback_command(intent_domains, query: str) -> str:
    """Project the legacy bounded remediation command, without executing it."""
    if "network_ops" not in set(intent_domains or set()):
        return ""
    install_flag = "--install-authorized" if explicitly_allows_diagnostic_install(query) else ""
    return ("python -m src.asset_inventory network-discover " + install_flag + " --record-observations").strip()
