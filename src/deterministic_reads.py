"""Compositional semantic predicates for harmless canonical reads.

This module is a derived intent projection, not a capability registry.  It
recognizes subject, ownership, and read semantics before provider inference so
ordinary paraphrases converge on the existing DomainContracts.
"""

from __future__ import annotations

import re


_READ_REQUEST = re.compile(
    r"^(?:what|which|where|who|show|list|tell|describe|summarize|give|provide|"
    r"review|display|remind|do\s+i|have\s+i|you\s+know)\b",
    re.IGNORECASE,
)
_OWNER_SELF = re.compile(
    r"\b(?:about|on)\s+(?:me|myself)\b|\bwho\s+i\s+am\b|\bmy\s+profile\b",
    re.IGNORECASE,
)
_MEMORY_KNOWLEDGE = re.compile(
    r"\b(?:remember(?:ed|ing)?|memor(?:y|ies)|know(?:n)?|learn(?:ed|t)|"
    r"information|profile|rundown)\b",
    re.IGNORECASE,
)
_WORK_SUBJECT = re.compile(
    r"\b(?:work|working|workload|"
    r"on\s+my\s+plate)\b",
    re.IGNORECASE,
)
_WORK_OWNER = re.compile(
    r"\b(?:my|i(?:'m|\s+am)?|i\s+have|have\s+i|i(?:'ve)?\s+got)\b",
    re.IGNORECASE,
)
_ASSET_SUBJECT = re.compile(
    r"\b(?:it\s+assets?|assets?|computers?|machines?|hardware|"
    r"physical\s+(?:machines?|boxes)|equipment|servers?)\b",
    re.IGNORECASE,
)
_ASSET_OWNER = re.compile(
    r"\b(?:my|mine|i\s+own|do\s+i\s+own|do\s+i\s+have|have\s+i|"
    r"i(?:'ve)?\s+got|registered)\b",
    re.IGNORECASE,
)
_NETWORK_SUBJECT = re.compile(r"\b(?:network|lan|connection|connected)\b", re.IGNORECASE)
_CURRENT_STATE = re.compile(
    r"\b(?:current(?:ly)?|right\s+now|now|am\s+i\s+on|connected\s+to|"
    r"where\s+am\s+i\s+connected)\b",
    re.IGNORECASE,
)


def _normalized(text: str) -> str:
    value = str(text or "").strip().casefold().replace("’", "'")
    return re.sub(r"\s+", " ", value).strip(" .?!")


def deterministic_read_concept(text: str) -> str | None:
    """Return an existing DomainContract concept for an unambiguous read."""
    query = _normalized(text)
    if not query or not _READ_REQUEST.search(query):
        return None

    # Explicit owner-knowledge predicates outrank narrower nouns: "what do
    # you remember about my work" asks Memory what it retains, not Work state.
    if _MEMORY_KNOWLEDGE.search(query) and (
        _OWNER_SELF.search(query) or re.search(r"\babout\s+my\b", query)
    ):
        return "MEMORY"
    if (
        _WORK_SUBJECT.search(query)
        and _WORK_OWNER.search(query)
        and not re.search(r"\b(?:projects?|tasks?|goals?|commitments?|runs?|missions?|watches?)\b", query)
    ):
        return "WORK"
    if _ASSET_SUBJECT.search(query) and _ASSET_OWNER.search(query):
        return "TECHNICAL_ASSET"
    if _NETWORK_SUBJECT.search(query) and _CURRENT_STATE.search(query):
        return "NETWORK"
    # A broad self-description request with no narrower subject is an
    # owner-self-knowledge read.  This covers "tell me about me" compositionally
    # (read/report verb + owner-self subject), without matching arbitrary
    # "tell me about <entity>" requests.
    if _OWNER_SELF.search(query):
        return "MEMORY"
    return None


def deterministic_read_view(text: str, concept: str | None) -> str | None:
    """Return a semantic view over an existing DomainContract, when evident."""
    query = _normalized(text)
    if concept == "NETWORK" and _CURRENT_STATE.search(query):
        return "context"
    if concept == "WORK" and re.search(r"\b(?:attention|on\s+my\s+plate|needs?\s+attention)\b", query):
        return "attention"
    return None
