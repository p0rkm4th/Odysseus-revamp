"""Grounded owner-facing renderers for Homelab and Network Results."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

def project_homelab_result(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Bound network/service evidence before it enters history or prompts."""
    action = str(payload.get("action") or "").strip()
    common = {"action": action, "status": payload.get("status"), "kind": payload.get("kind"),
              "target": payload.get("target"), "observation_location": payload.get("observation_location"),
              "freshness": payload.get("freshness")}
    if str(payload.get("kind") or "").strip().lower() == "plan" and action in {"plan_network_discovery", "execute_network_discovery"}:
        return {"action": "plan_network_discovery", "status": payload.get("status") or "SUCCESS",
                "kind": payload.get("kind"), "target": payload.get("target") or payload.get("cidr"),
                "operation_digest": payload.get("operation_digest"),
                       "preflight": payload.get("preflight"), "scanner_available": payload.get("scanner_available"),
                       "broker_scanner_available": payload.get("broker_scanner_available")}
    if action == "read_network_context":
        common.update({"interfaces": list(payload.get("interfaces", [])[:32]) if isinstance(payload.get("interfaces"), list) else [],
                       "default_routes": list(payload.get("default_routes", [])[:8]) if isinstance(payload.get("default_routes"), list) else []})
        return common
    if action == "read_network_observations":
        nodes = []
        for node in (payload.get("nodes", [])[:50] if isinstance(payload.get("nodes"), list) else []):
            if not isinstance(node, Mapping):
                continue
            attrs = node.get("attributes") if isinstance(node.get("attributes"), Mapping) else {}
            nodes.append({"id": node.get("id"), "name": node.get("name"), "status": node.get("status"),
                          "canonical": node.get("canonical"), "resolution_state": node.get("resolution_state"),
                          "attributes": {key: attrs.get(key) for key in ("hostname", "observed_ip", "ip") if attrs.get(key) not in (None, "")}})
        common.update({"nodes": nodes, "edges": list(payload.get("edges", [])[:50]) if isinstance(payload.get("edges"), list) else [],
                       "node_count": payload.get("node_count"), "edge_count": payload.get("edge_count")})
        return common
    if action == "inspect_host":
        common["output"] = str(payload.get("output") or "")[:2000]
        return common
    if action == "service_status":
        services = payload.get("services")
        common.update({"overall": payload.get("overall"), "output": str(payload.get("output") or "")[:2000],
                       "services": [{"name": item.get("name"), "status": item.get("status"), "detail": item.get("detail")}
                                     for item in (services[:50] if isinstance(services, list) else []) if isinstance(item, Mapping)],
                       "service_count": len(services) if isinstance(services, list) else 0})
        return common
    return None

def canonical_network_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    """Render network observations/context without model-invented topology."""
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
    payload = event.get("result_projection")
    if not isinstance(payload, Mapping):
        try:
            payload = json.loads(str(event.get("output") or ""))
        except (TypeError, ValueError):
            return None
    if not isinstance(payload, Mapping):
        return None
    if str(payload.get("status") or "").upper() in {
        "FAILED", "INVALID_RESULT", "ERROR",
    }:
        return None

    def freshness_line(value: Any) -> str | None:
        """Expose canonical freshness without leaking internal field names."""
        normalized = " ".join(str(value or "").replace("_", " ").split()).strip()
        if not normalized:
            return None
        return f"Freshness: {normalized}."

    action = str(payload.get("action") or "").strip()
    if action == "read_network_context":
        if str(payload.get("status") or "").upper() == "UNAVAILABLE":
            message = str(payload.get("message") or "").strip()
            return message or "Current host network context is unavailable. Previously recorded network observations remain available."
        interfaces = payload.get("interfaces")
        routes = payload.get("default_routes")
        if not isinstance(interfaces, list) or not isinstance(routes, list):
            return None
        if not interfaces:
            return "No current host network interfaces were observed."
        lines = ["Current host network context (observed):"]
        for interface in interfaces[:32]:
            if not isinstance(interface, Mapping):
                continue
            name = str(interface.get("name") or "unknown").strip()
            addresses = interface.get("addresses") if isinstance(interface.get("addresses"), list) else []
            rendered = [str(item.get("address")) for item in addresses[:8] if isinstance(item, Mapping) and item.get("address")]
            suffix = f" addresses={', '.join(rendered)}" if rendered else ""
            lines.append(f"- {name} ({interface.get('kind') or 'unknown'}){suffix}")
        if routes:
            gateways = [str(route.get("gateway")) for route in routes[:8] if isinstance(route, Mapping) and route.get("gateway")]
            lines.append(f"Default route gateway: {', '.join(gateways)}." if gateways else "A default route was observed; gateway details are unavailable.")
        else:
            lines.append("No default route was observed.")
        if line := freshness_line(payload.get("freshness")):
            lines.append(line)
        return "\n".join(lines)
    if action == "read_network_observations":
        nodes = payload.get("nodes")
        edges = payload.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            return None
        if not nodes:
            return "No persisted network observations are recorded for this owner."
        freshness = payload.get("freshness")
        if not freshness:
            node_freshness = {
                str(node.get("freshness") or "").strip()
                for node in nodes
                if isinstance(node, Mapping) and str(node.get("freshness") or "").strip()
            }
            if len(node_freshness) == 1:
                freshness = next(iter(node_freshness))
        # A normal owner should not have to interpret CMDB UUIDs, discovery
        # placeholders, or repeated observations. Keep the full structured
        # Result available in technical details, but make the primary answer
        # a bounded summary with honest identity/freshness language.
        if len(nodes) == 1:
            node = nodes[0] if isinstance(nodes[0], Mapping) else {}
            attrs = node.get("attributes") if isinstance(node.get("attributes"), Mapping) else {}
            label = node.get("name") or attrs.get("hostname") or attrs.get("observed_ip") or node.get("id") or "Unnamed node"
            lines = ["I found 1 persisted network observation:", f"- {label}"]
        else:
            named: dict[str, int] = {}
            unresolved: dict[str, int] = {}

            def display_label(node: Mapping[str, Any]) -> tuple[str, bool]:
                attrs = node.get("attributes") if isinstance(node.get("attributes"), Mapping) else {}
                raw_name = str(node.get("name") or "").strip()
                hostname = str(attrs.get("hostname") or node.get("hostname") or "").strip()
                address = str(
                    attrs.get("observed_ip") or attrs.get("ip") or node.get("observed_ip") or ""
                ).strip()
                opaque = bool(
                    raw_name
                    and (
                        re.fullmatch(r"network-device-[a-z0-9-]+", raw_name, re.IGNORECASE)
                        or re.fullmatch(r"[0-9a-f]{8,}(?:-[0-9a-f-]+)?", raw_name, re.IGNORECASE)
                        or raw_name == str(node.get("id") or "").strip()
                    )
                )
                label = address or (hostname if hostname and not opaque else "") or (raw_name if raw_name and not opaque else "")
                reviewable = str(node.get("resolution_state") or "").casefold() in {
                    "unidentified", "pending_candidate"
                } or node.get("canonical") is False or str(node.get("status") or "").casefold() in {
                    "observed", "pending", "pending_review"
                }
                if not label:
                    label = "Unidentified observed device"
                    reviewable = True
                if reviewable and address:
                    label = f"Unidentified device {address}"
                return label, reviewable

            for node in nodes:
                if not isinstance(node, Mapping):
                    continue
                label, reviewable = display_label(node)
                bucket = unresolved if reviewable else named
                bucket[label] = bucket.get(label, 0) + 1
            lines = [f"I found {len(nodes)} persisted network observations."]
            if named:
                lines.append("Named or identified records:")
                for label, count in list(named.items())[:12]:
                    lines.append(f"- {label}" + (f" ({count} observations)" if count > 1 else ""))
                if len(named) > 12:
                    lines.append(f"- …and {len(named) - 12} more named records")
            if unresolved:
                if named:
                    lines.append("")
                lines.append("Unidentified or unconfirmed records:")
                for label, count in list(unresolved.items())[:12]:
                    lines.append(f"- {label}" + (f" ({count} observations)" if count > 1 else ""))
                if len(unresolved) > 12:
                    lines.append(f"- …and {len(unresolved) - 12} more unidentified records")
            if named or unresolved:
                lines.append("")
            if not named and not unresolved:
                lines.append("The observations do not contain readable host identities.")
            lines.append("These are saved observations, not confirmation that a device is online right now.")
        if line := freshness_line(freshness):
            lines.append(line)
        return "\n".join(lines)
    return None




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
