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
    # Execution is intentionally part of the capability contract.  In
    # particular, LAN discovery is brokered by the host and must not be
    # inferred from the Hades application container namespace.
    execution_location: str = "application"
    target_scope: str | None = None
    requires_direct_container_access: bool = True
    required_capabilities: tuple[str, ...] = ()
    target_resources: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    locks: tuple[str, ...] = ()
    risk_level: str = "low"
    idempotency: str = "unknown"
    retry_policy: Mapping[str, Any] | None = None
    timeout_seconds: int | None = None
    rollback_capability: str = "none"
    compensating_action: str | None = None
    postconditions: tuple[str, ...] = ()
    verification: tuple[str, ...] = ()
    expected_cost: Mapping[str, Any] | None = None
    # These fields are descriptive contract metadata.  They are intentionally
    # additive: existing bindings can continue to declare only the semantics
    # they actually know.
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    blast_radius: tuple[str, ...] = ()
    reversible: bool = False
    compensatable: bool = False
    irreversible: bool = False
    state_invalidations: tuple[str, ...] = ()
    precheck_actions: tuple[str, ...] = ()
    expected_downtime: Mapping[str, Any] | None = None
    execution_requirements: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    actions: Mapping[str, ActionSpec]
    description: str = ""


def _actions(*specs: ActionSpec) -> Mapping[str, ActionSpec]:
    return MappingProxyType({spec.action_id: spec for spec in specs})


CAPABILITY_REGISTRY: Mapping[str, CapabilitySpec] = MappingProxyType({
    "developer.workspace_shell": CapabilitySpec(
        capability_id="developer.workspace_shell", description="Owner-granted workspace developer execution.",
        actions=_actions(ActionSpec(action_id="execute", effects=("write_workspace", "execute_code"), approval=ApprovalMode.EXACT, executor_key="workspace_yolo")),
    ),
    "intelligence.route": CapabilitySpec(
        capability_id="intelligence.route", description="Inspect deterministic domain/model routing.",
        actions=_actions(ActionSpec(action_id="read", effects=("read_private",), executor_key="local_intelligence")),
    ),
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
    "memory.read": CapabilitySpec(
        capability_id="memory.read",
        description="Owner-scoped explicit reads from the canonical Brain memory store.",
        actions=_actions(*(
            ActionSpec(action_id=action, effects=("read_private",), executor_key="read_memory")
            for action in ("summarize_owner_memory", "search_memory", "inspect_memory")
        )),
    ),
    "work.read": CapabilitySpec(
        capability_id="work.read",
        description="Owner-scoped read projections over the canonical Work Engine.",
        actions=_actions(*(
            ActionSpec(action_id=action, effects=("read_private",), executor_key="read_work")
            for action in ("overview", "review", "attention", "context", "list_goals", "list_projects", "list_tasks", "list_runs", "list_commitments", "list_missions", "list_watches")
        )),
    ),
    "household.read": CapabilitySpec(
        capability_id="household.read",
        description="Owner-scoped read projections over Household Inventory.",
        actions=_actions(*(
            ActionSpec(action_id=action, effects=("read_private",), executor_key="read_household")
            for action in ("overview", "list_items", "search_items", "get_item")
        )),
    ),
    "setup.read": CapabilitySpec(
        capability_id="setup.read",
        description="Owner-scoped read projections over Setup Center and integrations.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("read_private",), executor_key="read_setup") for action in ("state", "integrations", "permissions"))),
    ),
    "career.read": CapabilitySpec(
        capability_id="career.read", description="Owner-scoped Career reads under Work.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("read_private",), executor_key="read_career") for action in ("overview", "saved_opportunities", "applications", "follow_ups", "interviews", "provider_status"))),
    ),
    "career.provider": CapabilitySpec(
        capability_id="career.provider", description="External Career mutations; exact approval required.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("external_side_effect",), approval=ApprovalMode.EXACT, executor_key="career_provider") for action in ("submit_application", "send_message", "book_interview"))),
    ),
    "communications.read": CapabilitySpec(
        capability_id="communications.read",
        description="Owner-scoped read projection over configured communications providers.",
        actions=_actions(*(
            ActionSpec(action_id=action, effects=("read_private",), executor_key="read_communications")
            for action in ("overview", "contacts")
        )),
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
                execution_location=("host_broker" if action in {"execute_network_discovery", "execute_network_service_enumeration", "execute_diagnostic_install"} else "application"),
                target_scope=("private_network" if action in {"plan_network_discovery", "execute_network_discovery", "plan_network_service_enumeration", "execute_network_service_enumeration"} else None),
                requires_direct_container_access=(action not in {"plan_network_discovery", "execute_network_discovery", "plan_network_service_enumeration", "execute_network_service_enumeration", "execute_diagnostic_install"}),
                target_resources=("network:private_scope",) if action in {"plan_network_discovery", "execute_network_discovery", "plan_network_service_enumeration", "execute_network_service_enumeration"} else (),
                locks=(("network:private_scope",) if action in {"execute_network_discovery", "execute_network_service_enumeration"} else (("host:package_manager",) if action == "execute_diagnostic_install" else ())),
                rollback_capability="none",
                precheck_actions=("plan_service_restart",) if action == "execute_service_restart" else (("plan_network_service_enumeration",) if action == "execute_network_service_enumeration" else (("plan_diagnostic_install",) if action == "execute_diagnostic_install" else ())),
                postconditions=("service_active",) if action == "execute_service_restart" else (("prerequisites_verified",) if action == "execute_diagnostic_install" else ()),
                verification=("service_active",) if action == "execute_service_restart" else (("observations_persisted", "network_map_reconciled") if action == "execute_network_discovery" else (("service_observations_persisted", "network_map_reconciled") if action == "execute_network_service_enumeration" else (("prerequisites_verified",) if action == "execute_diagnostic_install" else ()))),
                state_invalidations=("service.status", "service.uptime", "service.process_start_time") if action == "execute_service_restart" else (("network.observations", "network.map") if action in {"execute_network_discovery", "execute_network_service_enumeration"} else (("capability.health", "executable.availability") if action == "execute_diagnostic_install" else ())),
                risk_level=("high" if action in {"execute_network_discovery", "execute_network_service_enumeration", "execute_service_restart", "execute_diagnostic_install"} else ("low")),
                idempotency=("conditional_retry" if action in {"execute_network_service_enumeration", "execute_service_restart", "execute_diagnostic_install"} else ("replay_safe" if action == "execute_network_discovery" else "unknown")),
            ) for action in (
                "inspect_host", "service_status", "discovery_status", "read_network_context", "read_network_observations",
                "list_unidentified_hosts", "infer_role_hypotheses",
                "plan_service_restart", "execute_service_restart",
                "plan_network_discovery", "execute_network_discovery",
                "plan_network_service_enumeration", "execute_network_service_enumeration",
                "plan_diagnostic_install", "execute_diagnostic_install",
            )
        )),
    ),
    "research.public_sources": CapabilitySpec(
        capability_id="research.public_sources",
        description="Public-source-only research planning and validation.",
        actions=_actions(
            ActionSpec(action_id="list_cases", effects=("read_private",), executor_key="manage_osint"),
            ActionSpec(action_id="get_case", effects=("read_private",), executor_key="manage_osint"),
            ActionSpec(action_id="plan", executor_key="manage_osint"),
            ActionSpec(action_id="search", executor_key="manage_osint"),
            ActionSpec(action_id="fetch", executor_key="manage_osint"),
        ),
    ),
    "security.assessment.read": CapabilitySpec(
        capability_id="security.assessment.read",
        description="Read owner-scoped bounded security assessment records.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("read_private",), executor_key="manage_security_assessment") for action in ("list_engagements", "get_engagement", "list_findings", "list_evidence"))),
    ),
    "security.engagement.manage": CapabilitySpec(
        capability_id="security.engagement.manage",
        description="Manage draft and explicitly authorized security engagements.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("write_private",), approval=ApprovalMode.NORMAL, executor_key="manage_security_assessment") for action in ("create_engagement", "authorize_engagement"))),
    ),
    "security.scope.manage": CapabilitySpec(
        capability_id="security.scope.manage",
        description="Manage explicit inclusion, exclusion, and action scope.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("write_private",), approval=ApprovalMode.NORMAL, executor_key="manage_security_assessment") for action in ("add_scope", "add_target"))),
    ),
    "security.target.resolve": CapabilitySpec(
        capability_id="security.target.resolve",
        description="Resolve assessment targets against canonical CMDB identity without mutation.",
        actions=_actions(ActionSpec(action_id="resolve", effects=("read_private",), executor_key="manage_security_assessment")),
    ),
    "security.context.read": CapabilitySpec(
        capability_id="security.context.read",
        description="Read a provenance-aware canonical CMDB security context projection.",
        actions=_actions(ActionSpec(action_id="read", effects=("read_private",), executor_key="manage_security_assessment")),
    ),
    "security.observation.ingest": CapabilitySpec(
        capability_id="security.observation.ingest",
        description="Attach an authorized bounded Homelab observation to an assessment run as evidence.",
        actions=_actions(ActionSpec(action_id="ingest", effects=("write_private",), approval=ApprovalMode.NORMAL, executor_key="manage_security_assessment")),
    ),
    "security.run.plan": CapabilitySpec(
        capability_id="security.run.plan",
        description="Plan a bounded, persisted assessment run after scope authorization.",
        actions=_actions(ActionSpec(action_id="plan_run", effects=("network_plan",), approval=ApprovalMode.NORMAL, executor_key="manage_security_assessment")),
    ),
    "security.recon.execute": CapabilitySpec(
        capability_id="security.recon.execute",
        description="Reserved exact-approval boundary; V1 exposes no recon executor.",
        actions=_actions(ActionSpec(action_id="execute", effects=("external_network",), approval=ApprovalMode.EXACT)),
    ),
    "security.finding.manage": CapabilitySpec(
        capability_id="security.finding.manage",
        description="Record and advance findings with evidence references.",
        actions=_actions(*(ActionSpec(action_id=action, effects=("write_private",), approval=ApprovalMode.NORMAL, executor_key="manage_security_assessment") for action in ("add_evidence", "add_finding", "update_finding", "propose"))),
    ),
    "security.finding.confirm": CapabilitySpec(
        capability_id="security.finding.confirm",
        description="Explicitly confirm a proposed finding candidate.",
        actions=_actions(ActionSpec(action_id="confirm", effects=("write_private",), approval=ApprovalMode.NORMAL, executor_key="manage_security_assessment")),
    ),
    "security.finding.verify": CapabilitySpec(
        capability_id="security.finding.verify",
        description="Record explicit finding verification state.",
        actions=_actions(ActionSpec(action_id="verify", effects=("write_private",), approval=ApprovalMode.NORMAL, executor_key="manage_security_assessment")),
    ),
    "security.report.generate": CapabilitySpec(
        capability_id="security.report.generate",
        description="Generate a local projection report from canonical assessment state.",
        actions=_actions(ActionSpec(action_id="generate", effects=("read_private",), executor_key="manage_security_assessment")),
    ),
    "work.goal.read": CapabilitySpec("work.goal.read", _actions(*(ActionSpec(action_id=a, effects=("read_private",), executor_key="manage_work") for a in ("list", "get", "context"))), "Read durable work goals and context."),
    "work.goal.manage": CapabilitySpec("work.goal.manage", _actions(*(ActionSpec(action_id=a, effects=("write_private",), executor_key="manage_work") for a in ("create", "update"))), "Manage desired outcomes."),
    "work.project.read": CapabilitySpec("work.project.read", _actions(ActionSpec("list", effects=("read_private",), executor_key="manage_work")), "Read work projects."),
    "work.project.manage": CapabilitySpec("work.project.manage", _actions(ActionSpec("create", effects=("write_private",), executor_key="manage_work")), "Manage work projects."),
    "work.task.read": CapabilitySpec("work.task.read", _actions(ActionSpec("list", effects=("read_private",), executor_key="manage_work")), "Read work tasks."),
    "work.task.manage": CapabilitySpec("work.task.manage", _actions(*(ActionSpec(action_id=a, effects=("write_private",), executor_key="manage_work") for a in ("create", "dependency"))), "Manage bounded task state."),
    "work.run.read": CapabilitySpec("work.run.read", _actions(*(ActionSpec(action_id=a, effects=("read_private",), executor_key="manage_work") for a in ("list", "get", "context"))), "Read durable runs and actions."),
    "work.run.manage": CapabilitySpec("work.run.manage", _actions(*(ActionSpec(action_id=a, effects=("write_private",), executor_key="manage_work") for a in ("create", "update", "action", "complete"))), "Manage durable execution state."),
    "work.commitment.read": CapabilitySpec("work.commitment.read", _actions(ActionSpec("list", effects=("read_private",), executor_key="manage_work")), "Read commitments."),
    "work.commitment.manage": CapabilitySpec("work.commitment.manage", _actions(ActionSpec("create", effects=("write_private",), executor_key="manage_work")), "Manage commitments."),
})


TOOL_CAPABILITY_IDS: Mapping[str, str] = MappingProxyType({
    "manage_assets": "inventory.manage",
    "privileged_action": "system.privileged_diagnostics",
    "manage_homelab": "homelab.manage",
    "manage_osint": "research.public_sources",
    "manage_security_assessment": "security.assessment.read",
    "read_memory": "memory.read",
    "read_work": "work.read",
    "read_household": "household.read",
    "read_setup": "setup.read",
    "read_career": "career.read",
    "read_communications": "communications.read",
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
