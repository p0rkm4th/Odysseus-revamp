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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

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
