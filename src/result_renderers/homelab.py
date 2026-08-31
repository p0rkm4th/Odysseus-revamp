"""Grounded owner-facing renderers for Homelab and Network Results."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def canonical_network_plan_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render a bounded discovery plan without implying execution."""
    event = next(
        (
            item for item in reversed(tuple(tool_events or ()))
            if isinstance(item, Mapping)
            and str(item.get("tool") or "").strip() == "manage_homelab"
        ),
        None,
    )
    if event is None or event.get("exit_code") not in (None, 0):
        return None
    projection = event.get("result_projection")
    if not isinstance(projection, Mapping):
        try:
            projection = json.loads(str(event.get("output") or ""))
        except (TypeError, ValueError):
            projection = None
    command: Mapping[str, Any] = {}
    try:
        parsed = json.loads(str(event.get("command") or ""))
        if isinstance(parsed, Mapping):
            command = parsed
    except (TypeError, ValueError):
        pass
    action = str((projection or {}).get("action") or command.get("action") or "").strip()
    if action != "plan_network_discovery":
        return None
    cidr = str((projection or {}).get("target") or command.get("cidr") or "").strip()
    if not cidr:
        return None
    status = str((projection or {}).get("status") or "").strip().upper()
    if status in {"FAILED", "UNAVAILABLE", "INVALID_RESULT", "ERROR"}:
        return None
    return (
        f"I interpreted that as {cidr}. I prepared a bounded network discovery "
        f"plan for exactly {cidr}. No scan has started; active discovery still "
        "requires exact approval for this scope."
    )


def _homelab_payload(event: Mapping[str, Any]) -> Mapping[str, Any] | None:
    payload = event.get("result_projection")
    if not isinstance(payload, Mapping):
        try:
            payload = json.loads(str(event.get("output") or ""))
        except (TypeError, ValueError):
            return None
    return payload if isinstance(payload, Mapping) else None


def _homelab_event(tool_events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    event = next(
        (
            item for item in reversed(tuple(tool_events or ()))
            if isinstance(item, Mapping)
            and str(item.get("tool") or "").strip() == "manage_homelab"
        ),
        None,
    )
    return event if event is not None and event.get("exit_code") in (None, 0) else None


def canonical_homelab_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render bounded host inspection evidence from a canonical Result."""
    event = _homelab_event(tool_events)
    payload = _homelab_payload(event) if event else None
    if not payload or str(payload.get("status") or "").strip().upper() in {"FAILED", "UNAVAILABLE", "INVALID_RESULT", "ERROR"}:
        return None
    if str(payload.get("action") or "").strip() != "inspect_host":
        return None
    output = str(payload.get("output") or "").strip()
    target = str(payload.get("target") or "local_host").strip()
    source = str(payload.get("observation_location") or "HOST_OPERATOR").strip()
    if not output:
        return f"The {target} inspection completed, but it returned no host details."
    return f"Host inspection for {target} (observed via {source}):\n{output[:2000]}"


def canonical_service_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render bounded service-health evidence for owner reads."""
    event = _homelab_event(tool_events)
    payload = _homelab_payload(event) if event else None
    if not payload or str(payload.get("action") or "").strip() != "service_status":
        return None
    if str(payload.get("status") or "").strip().upper() in {"FAILED", "UNAVAILABLE", "INVALID_RESULT", "ERROR"}:
        return None
    services = payload.get("services")
    if not isinstance(services, list):
        output = str(payload.get("output") or "").strip()
        target = str(payload.get("target") or "the requested service").strip()
        return f"Service status for {target}:\n{output[:2000]}" if output else f"No status details were returned for {target}."
    if not services and str(payload.get("output") or "").strip():
        target = str(payload.get("target") or "the requested service").strip()
        return f"Service status for {target}:\n{str(payload.get('output')).strip()[:2000]}"
    if not services:
        return "No service health observations are recorded for the Hades runtime."
    lines = [f"Hades runtime service health: {str(payload.get('overall') or 'unknown').strip()}."]
    for service in services[:50]:
        if not isinstance(service, Mapping):
            continue
        name = str(service.get("name") or "unnamed service").strip()
        status = str(service.get("status") or "unknown").strip()
        detail = str(service.get("detail") or "").strip()
        lines.append(f"- {name}: {status}" + (f" ({detail})" if detail else ""))
    return "\n".join(lines)
