"""Small, transport-independent capability and action registry.

This registry describes what a first-class capability can do.  LLM tool names,
schemas, and textual invocation syntax are projections owned by
``src.tool_bindings``; they are deliberately not the canonical identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class ApprovalMode(str, Enum):
    NONE = "none"
    NORMAL = "normal"
    EXACT = "exact"


@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    effects: tuple[str, ...] = ()
    result_integrity: str = "system"
    approval: ApprovalMode = ApprovalMode.NONE
    executor_key: str | None = None
    known: bool = True


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    actions: Mapping[str, ActionSpec]
    description: str = ""


def _actions(*specs: ActionSpec) -> Mapping[str, ActionSpec]:
    return MappingProxyType({spec.action_id: spec for spec in specs})


CAPABILITY_REGISTRY: Mapping[str, CapabilitySpec] = MappingProxyType({
    "inventory.manage": CapabilitySpec(
        capability_id="inventory.manage",
        description="Persistent asset inventory, relationships, and observations.",
        actions=_actions(
            *(
                ActionSpec(
                    action_id=action,
                    effects=("read_private",) if action in {"summary", "list", "search", "get"} else ("write_private",),
                    executor_key="manage_assets",
                )
                for action in (
                    "summary", "list", "search", "get", "add", "update",
                    "record_observation", "link_component", "unlink_component",
                    "retire", "merge",
                )
            )
        ),
    ),
    "system.privileged_diagnostics": CapabilitySpec(
        capability_id="system.privileged_diagnostics",
        description="Narrow brokered diagnostic operations.",
        actions=_actions(
            ActionSpec(
                action_id="status",
                result_integrity="system",
                executor_key="privileged_action",
            ),
            ActionSpec(
                action_id="install_packages",
                effects=("admin_change",),
                result_integrity="system",
                approval=ApprovalMode.EXACT,
                executor_key="privileged_action",
            ),
        ),
    ),
    "homelab.manage": CapabilitySpec(
        capability_id="homelab.manage",
        description="Bounded local homelab inspection, planning, and approved discovery.",
        actions=_actions(*(
            ActionSpec(
                action_id=action,
                effects=("read_private",) if not action.startswith("execute_") else ("admin_change",),
                approval=ApprovalMode.EXACT if action.startswith("execute_") else ApprovalMode.NONE,
                executor_key="manage_homelab",
            ) for action in (
                "inspect_host", "service_status", "discovery_status",
                "plan_service_restart", "execute_service_restart",
                "plan_network_discovery", "execute_network_discovery",
                "plan_diagnostic_install", "execute_diagnostic_install",
            )
        )),
    ),
    "research.public_sources": CapabilitySpec(
        capability_id="research.public_sources",
        description="Public-source-only research planning and validation.",
        actions=_actions(
            ActionSpec(action_id="plan", executor_key="manage_osint"),
            ActionSpec(action_id="search", executor_key="manage_osint"),
            ActionSpec(action_id="fetch", executor_key="manage_osint"),
        ),
    ),
    "security.assessment.read": CapabilitySpec(
        capability_id="security.assessment.read",
        description="Read owner-scoped bounded security assessment records.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("read_private",), executor_key="manage_security_assessment") for action in ("list_engagements", "get_engagement", "list_findings"))),
    ),
    "security.engagement.manage": CapabilitySpec(
        capability_id="security.engagement.manage",
        description="Manage draft and explicitly authorized security engagements.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("write_private",), approval=ApprovalMode.NORMAL, executor_key="security_assessment") for action in ("create_engagement", "authorize_engagement"))),
    ),
    "security.scope.manage": CapabilitySpec(
        capability_id="security.scope.manage",
        description="Manage explicit inclusion, exclusion, and action scope.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("write_private",), approval=ApprovalMode.NORMAL, executor_key="security_assessment") for action in ("add_scope", "add_target"))),
    ),
    "security.run.plan": CapabilitySpec(
        capability_id="security.run.plan",
        description="Plan a bounded, persisted assessment run after scope authorization.",
        actions=_actions(ActionSpec(action_id="plan_run", effects=("network_plan",), approval=ApprovalMode.NORMAL, executor_key="security_assessment")),
    ),
    "security.recon.execute": CapabilitySpec(
        capability_id="security.recon.execute",
        description="Reserved exact-approval boundary; V1 exposes no recon executor.",
        actions=_actions(ActionSpec(action_id="execute", effects=("external_network",), approval=ApprovalMode.EXACT)),
    ),
    "security.finding.manage": CapabilitySpec(
        capability_id="security.finding.manage",
        description="Record and advance findings with evidence references.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("write_private",), approval=ApprovalMode.NORMAL, executor_key="security_assessment") for action in ("add_evidence", "add_finding", "update_finding"))),
    ),
    "security.report.generate": CapabilitySpec(
        capability_id="security.report.generate",
        description="Generate a local projection report from canonical assessment state.",
        actions=_actions(ActionSpec(action_id="generate", effects=("read_private",), executor_key="security_assessment")),
    ),
})


TOOL_CAPABILITY_IDS: Mapping[str, str] = MappingProxyType({
    "manage_assets": "inventory.manage",
    "privileged_action": "system.privileged_diagnostics",
    "manage_homelab": "homelab.manage",
    "manage_osint": "research.public_sources",
    "manage_security_assessment": "security.assessment.read",
})


def capability_for_id(capability_id: str) -> CapabilitySpec | None:
    return CAPABILITY_REGISTRY.get(capability_id)


def capability_for_tool(tool_name: str) -> CapabilitySpec | None:
    capability_id = TOOL_CAPABILITY_IDS.get(tool_name)
    return CAPABILITY_REGISTRY.get(capability_id) if capability_id else None


def action_from_content(tool_name: str, content: Any) -> str | None:
    if isinstance(content, Mapping):
        payload = dict(content)
    elif isinstance(content, str):
        try:
            payload = json.loads(content or "{}")
        except (TypeError, ValueError):
            return None
    else:
        payload = {}
    if not isinstance(payload, dict):
        return None
    action = payload.get("action")
    return action.strip().replace("-", "_").casefold() if isinstance(action, str) and action.strip() else None


def action_for_tool(tool_name: str, content: Any) -> ActionSpec | None:
    capability = capability_for_tool(tool_name)
    if capability is None:
        return None
    action = action_from_content(tool_name, content)
    if action is None:
        return ActionSpec("<unknown>", approval=ApprovalMode.EXACT, known=False)
    return capability.actions.get(action) or ActionSpec(
        action, effects=("unknown_high_impact",), approval=ApprovalMode.EXACT, known=False
    )


def requires_exact_approval(tool_name: str, content: Any) -> bool:
    spec = action_for_tool(tool_name, content)
    return bool(spec and spec.approval is ApprovalMode.EXACT)


def registered_tool_names() -> frozenset[str]:
    return frozenset(TOOL_CAPABILITY_IDS)
