"""Persisted, runtime-keyed model capability characterization.

This is evidence/cache, not an authority store.  It deliberately keeps the
provider protocol (for example ``openai-chat``) separate from the serving
runtime (for example ``ollama``), and never turns a model-name heuristic into
an executable capability.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

import httpx

from core.atomic_io import atomic_write_json
from src.constants import DATA_DIR


EVIDENCE_PRECEDENCE = (
    "admin_override",
    "capability_probe",
    "provider_reported",
    "endpoint_config",
    "registry",
    "heuristic",
    "unknown",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def runtime_profile_key(*, endpoint_id: str, protocol: str, runtime: str,
                        model_id: str, model_digest: str = "",
                        server_fingerprint: str = "") -> str:
    """Return a stable opaque key; secrets and URLs are not emitted."""
    value = {
        "endpoint_id": _clean(endpoint_id),
        "protocol": _clean(protocol),
        "runtime": _clean(runtime),
        "model_id": _clean(model_id),
        "model_digest": _clean(model_digest),
        "server_fingerprint": _clean(server_fingerprint),
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:32]


@dataclass(frozen=True)
class CapabilityEvidence:
    status: str = "unknown"
    source: str = "unknown"
    tested_at: float = 0.0
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def precedence(self) -> int:
        try:
            return EVIDENCE_PRECEDENCE.index(self.source)
        except ValueError:
            return len(EVIDENCE_PRECEDENCE) - 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source": self.source,
            "tested_at": self.tested_at,
            "evidence": dict(self.evidence),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "CapabilityEvidence":
        value = value if isinstance(value, Mapping) else {}
        try:
            tested_at = float(value.get("tested_at") or 0)
        except (TypeError, ValueError):
            tested_at = 0.0
        return cls(
            status=_clean(value.get("status")) or "unknown",
            source=_clean(value.get("source")) or "unknown",
            tested_at=tested_at,
            evidence=dict(value.get("evidence") or {}) if isinstance(value.get("evidence"), Mapping) else {},
        )


@dataclass(frozen=True)
class RuntimeCapabilityProfile:
    endpoint_id: str
    protocol: str
    runtime: str
    model_id: str
    model_digest: str = ""
    server_fingerprint: str = ""
    architecture_max_context: int = 0
    provider_configured_max_context: int = 0
    runtime_allocated_context: int = 0
    hardware_recommended_context: int = 0
    capabilities: Mapping[str, CapabilityEvidence] = field(default_factory=dict)
    created_at: float = 0.0
    refreshed_at: float = 0.0
    ttl_seconds: int = 86400

    @property
    def key(self) -> str:
        return runtime_profile_key(
            endpoint_id=self.endpoint_id, protocol=self.protocol,
            runtime=self.runtime, model_id=self.model_id,
            model_digest=self.model_digest,
            server_fingerprint=self.server_fingerprint,
        )

    def is_fresh(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return bool(self.refreshed_at and now <= self.refreshed_at + max(0, self.ttl_seconds))

    def supports(self, capability: str, *, fresh_only: bool = False) -> bool:
        evidence = self.capabilities.get(capability)
        if evidence is None or evidence.status not in {"pass", "verified", "supported"}:
            return False
        return not fresh_only or self.is_fresh()

    def with_probe(self, capability: str, status: str, *, evidence: Mapping[str, Any] | None = None,
                   tested_at: float | None = None) -> "RuntimeCapabilityProfile":
        """Return a profile with one empirical capability observation recorded."""
        observations = dict(self.capabilities)
        observations[_clean(capability)] = CapabilityEvidence(
            status=_clean(status) or "unknown",
            source="capability_probe",
            tested_at=tested_at if tested_at is not None else time.time(),
            evidence=dict(evidence or {}),
        )
        return replace(self, capabilities=observations, refreshed_at=time.time())

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint_id": self.endpoint_id,
            "protocol": self.protocol,
            "runtime": self.runtime,
            "model_id": self.model_id,
            "model_digest": self.model_digest,
            "server_fingerprint": self.server_fingerprint,
            "architecture_max_context": self.architecture_max_context,
            "provider_configured_max_context": self.provider_configured_max_context,
            "runtime_allocated_context": self.runtime_allocated_context,
            "hardware_recommended_context": self.hardware_recommended_context,
            "capabilities": {key: value.to_dict() for key, value in self.capabilities.items()},
            "created_at": self.created_at,
            "refreshed_at": self.refreshed_at,
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RuntimeCapabilityProfile":
        def integer(key: str) -> int:
            try:
                return max(0, int(value.get(key) or 0))
            except (TypeError, ValueError):
                return 0
        raw = value.get("capabilities")
        return cls(
            endpoint_id=_clean(value.get("endpoint_id")),
            protocol=_clean(value.get("protocol")),
            runtime=_clean(value.get("runtime")),
            model_id=_clean(value.get("model_id")),
            model_digest=_clean(value.get("model_digest")),
            server_fingerprint=_clean(value.get("server_fingerprint")),
            architecture_max_context=integer("architecture_max_context"),
            provider_configured_max_context=integer("provider_configured_max_context"),
            runtime_allocated_context=integer("runtime_allocated_context"),
            hardware_recommended_context=integer("hardware_recommended_context"),
            capabilities={key: CapabilityEvidence.from_dict(item) for key, item in (raw.items() if isinstance(raw, Mapping) else ())},
            created_at=float(value.get("created_at") or 0),
            refreshed_at=float(value.get("refreshed_at") or 0),
            ttl_seconds=max(0, integer("ttl_seconds") or 86400),
        )


def select_evidence(*evidence: CapabilityEvidence) -> CapabilityEvidence:
    """Select the strongest evidence; ties prefer the freshest observation."""
    usable = [item for item in evidence if isinstance(item, CapabilityEvidence)]
    if not usable:
        return CapabilityEvidence()
    return min(usable, key=lambda item: (item.precedence, -(item.tested_at or 0)))


class RuntimeProfileCache:
    """Small atomic JSON cache keyed by endpoint/runtime/model identity."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or (Path(DATA_DIR) / "runtime_capability_profiles.json"))

    def load(self, key: str) -> RuntimeCapabilityProfile | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, PermissionError, json.JSONDecodeError):
            return None
        item = data.get(key) if isinstance(data, Mapping) else None
        return RuntimeCapabilityProfile.from_dict(item) if isinstance(item, Mapping) else None

    def all(self) -> tuple[RuntimeCapabilityProfile, ...]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, PermissionError, json.JSONDecodeError):
            return ()
        if not isinstance(data, Mapping):
            return ()
        return tuple(
            RuntimeCapabilityProfile.from_dict(item)
            for item in data.values()
            if isinstance(item, Mapping)
        )

    def save(self, profile: RuntimeCapabilityProfile) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, PermissionError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data[profile.key] = profile.to_dict()
        atomic_write_json(self.path, data, indent=2)


def characterize_ollama(base_url: str, model_id: str, *, endpoint_id: str = "",
                         cache: RuntimeProfileCache | None = None,
                         force: bool = False, timeout: float = 3.0) -> RuntimeCapabilityProfile:
    """Read explicit Ollama metadata for one configured endpoint/model.

    This is intentionally metadata-only: it calls ``/api/show`` for the
    requested model and performs no discovery, generation, or tool execution.
    The caller must supply a configured endpoint; URL safety still rejects
    non-HTTP(S), link-local, multicast, and metadata targets.
    """
    from src.url_safety import check_outbound_url

    base = _clean(base_url).rstrip("/")
    ok, reason = check_outbound_url(base, block_private=False)
    if not ok:
        raise ValueError(f"unsafe Ollama endpoint: {reason}")
    # A cache lookup requires a digest, so metadata is fetched only when the
    # caller has no already-characterized identity. This endpoint has no
    # model listing/discovery side effect.
    response = httpx.post(
        f"{base}/api/show",
        json={"name": _clean(model_id)},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("Ollama metadata response is not an object")
    details = payload.get("details") if isinstance(payload.get("details"), Mapping) else {}
    info = payload.get("model_info") if isinstance(payload.get("model_info"), Mapping) else {}
    digest = _clean(payload.get("digest"))
    context = details.get("context_length") or info.get("general.context_length") or 0
    if not context:
        context = next((value for key, value in info.items() if str(key).endswith(".context_length")), 0)
    # Ollama versions differ: some expose digest/context only in /api/tags.
    # This remains a single configured endpoint/model inventory read, not
    # network discovery. Do not fail characterization merely because /show is
    # an older response shape.
    if not digest or not context:
        tags_response = httpx.get(f"{base}/api/tags", timeout=timeout)
        tags_response.raise_for_status()
        tags_payload = tags_response.json()
        models = tags_payload.get("models") if isinstance(tags_payload, Mapping) else ()
        match = next((item for item in models if isinstance(item, Mapping) and _clean(item.get("name")) == _clean(model_id)), None)
        if isinstance(match, Mapping):
            digest = digest or _clean(match.get("digest"))
            tag_details = match.get("details") if isinstance(match.get("details"), Mapping) else {}
            context = context or tag_details.get("context_length") or 0
    try:
        context = max(0, int(context or 0))
    except (TypeError, ValueError):
        context = 0
    observed = time.time()
    capabilities = {
        name: CapabilityEvidence("pass", "provider_reported", observed, {"source": "ollama_api_show"})
        for name in (payload.get("capabilities") or ())
        if _clean(name)
    }
    profile = RuntimeCapabilityProfile(
        endpoint_id=_clean(endpoint_id) or base,
        protocol="ollama-chat",
        runtime="ollama",
        model_id=_clean(model_id),
        model_digest=digest,
        server_fingerprint=_clean(response.headers.get("x-ollama-version")) or "unknown",
        architecture_max_context=context,
        provider_configured_max_context=context,
        capabilities=capabilities,
        created_at=observed,
        refreshed_at=observed,
    )
    if cache is not None:
        if not force:
            cached = cache.load(profile.key)
            if cached is not None and cached.is_fresh():
                return cached
        cache.save(profile)
    return profile
