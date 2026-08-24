"""OpenTelemetry-compatible trace semantics with safe durable projection.

The optional OTel SDK/exporter can consume these span-shaped records later. The
local projection is intentionally redacted and bounded so observability never
becomes a secret or prompt archive.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import uuid4
from sqlalchemy.orm import Session
from core.observability_models import TraceSpan

_SENSITIVE = ("secret", "token", "password", "passwd", "api_key", "authorization", "cookie", "prompt", "raw_body", "email_body")
_METRIC_KEYS = frozenset({"model.name", "provider", "domain", "capability.id", "action.effect_class", "status"})


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _id(prefix):
    return f"{prefix}_{uuid4().hex}"


def _safe_value(key: str, value: Any):
    key_l = key.casefold()
    if any(marker in key_l for marker in _SENSITIVE):
        return "[REDACTED]"
    if isinstance(value, str) and len(value) > 300:
        return {"digest": sha256(value.encode()).hexdigest(), "length": len(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_value(key, item) for item in list(value)[:20]]
    if isinstance(value, dict):
        return {str(k)[:80]: _safe_value(str(k), v) for k, v in list(value.items())[:30]}
    return str(value)[:300]


def sanitize_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    attributes = attributes or {}
    return {str(key)[:100]: _safe_value(str(key), value) for key, value in list(attributes.items())[:50]}


def metric_dimensions(attributes: dict[str, Any] | None) -> dict[str, Any]:
    safe = sanitize_attributes(attributes)
    return {key: value for key, value in safe.items() if key in _METRIC_KEYS and isinstance(value, (str, int, float, bool))}


class ObservabilityService:
    def __init__(self, db: Session):
        self.db = db

    def record_span(self, owner: str, name: str, *, run_id=None, trace_id=None, parent_span_id=None, attributes=None, status="ok", started_at=None, ended_at=None):
        if status not in {"ok", "error", "unset"}: raise ValueError("invalid trace status")
        started = started_at or _now()
        ended = ended_at or _now()
        duration = max(0, int((ended - started).total_seconds() * 1000))
        row = TraceSpan(id=_id("trace"), owner=owner, trace_id=str(trace_id or uuid4().hex), span_id=uuid4().hex, parent_span_id=parent_span_id, run_id=run_id, name=str(name or "request")[:128], status=status, attributes=sanitize_attributes(attributes), started_at=started, ended_at=ended, duration_ms=duration)
        self.db.add(row); self.db.commit(); self.db.refresh(row)
        return {column.name: (getattr(row, column.name).isoformat() if isinstance(getattr(row, column.name), datetime) else getattr(row, column.name)) for column in row.__table__.columns}

    def list_spans(self, owner: str, *, run_id=None, trace_id=None, limit=200):
        query = self.db.query(TraceSpan).filter_by(owner=owner)
        if run_id: query = query.filter_by(run_id=run_id)
        if trace_id: query = query.filter_by(trace_id=trace_id)
        return [{column.name: (getattr(row, column.name).isoformat() if isinstance(getattr(row, column.name), datetime) else getattr(row, column.name)) for column in row.__table__.columns} for row in query.order_by(TraceSpan.started_at.asc()).limit(max(1, min(int(limit), 500))).all()]
