"""Bounded semantic intent frames and projections onto canonical ActionSpecs.

This is a resolver layer, not an executor or a second capability registry.
Natural-language classification may be imperfect; the returned contract must
still resolve through the existing Capability -> ActionSpec -> ToolBinding
chain before a tool can run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Mapping

from src.capability_registry import ActionSpec, capability_for_id
from src.tool_bindings import binding_for_tool


OPERATION_CLASSES = frozenset({
    "READ", "CREATE", "UPDATE", "DELETE", "EXECUTE", "RESEARCH",
    "MONITOR", "CONTINUE", "APPROVE",
})
DEPTHS = frozenset({"QUICK", "STANDARD", "DEEP"})


@dataclass(frozen=True)
class IntentFrame:
    operation_class: str
    domain_concept: str
    target: str | None = None
    entity_reference: str | None = None
    run_reference: str | None = None
    filters: Mapping[str, Any] = field(default_factory=dict)
    scope: Mapping[str, Any] = field(default_factory=dict)
    depth: str = "STANDARD"
    constraints: tuple[str, ...] = ()
    desired_output: str | None = None
    source: str = "deterministic_compiler"

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["filters"] = dict(self.filters)
        result["scope"] = dict(self.scope)
        return result


@dataclass(frozen=True)
class DomainContract:
    concept: str
    capability_id: str
    actions: Mapping[str, str]
    binding: str | None
    exposures: Mapping[str, str]
    result_contract: str


@dataclass(frozen=True)
class ResolvedContract:
    frame: IntentFrame
    contract: DomainContract | None
    action_id: str | None
    action: ActionSpec | None
    binding_name: str | None
    available: bool
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent_frame": self.frame.as_dict(),
            "domain_concept": self.frame.domain_concept,
            "capability_id": self.contract.capability_id if self.contract else None,
            "action_id": self.action_id,
            "binding": self.binding_name,
            "available": self.available,
            "reason": self.reason,
            "result_contract": self.contract.result_contract if self.contract else None,
            "exposure": dict(self.contract.exposures) if self.contract else {},
        }


# Mappings deliberately reference existing capability IDs/action IDs. A
# missing binding is reported by validate_contracts rather than being silently
# replaced with a shell or database path.
DOMAIN_CONTRACTS: Mapping[str, DomainContract] = {
    "TECHNICAL_ASSET": DomainContract(
        "TECHNICAL_ASSET", "inventory.manage", {"READ": "list"}, "manage_assets",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "technical_asset_list",
    ),
    "SECURITY_FINDING": DomainContract(
        "SECURITY_FINDING", "security.assessment.read", {"READ": "list_findings"}, "manage_security_assessment",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "security_finding_list",
    ),
    "NETWORK": DomainContract(
        "NETWORK", "homelab.manage", {"READ": "read_network_observations", "EXECUTE": "plan_network_discovery"}, "manage_homelab",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "network_capability_or_discovery",
    ),
    "OSINT_CASE": DomainContract(
        "OSINT_CASE", "research.public_sources", {"RESEARCH": "plan"}, "manage_osint",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "osint_plan",
    ),
    "MEMORY": DomainContract(
        "MEMORY", "memory.read", {"READ": "summarize_owner_memory"}, "read_memory",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "explicit_memory_read",
    ),
    "WORK": DomainContract(
        "WORK", "work.read", {"READ": "overview"}, "read_work",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "work_overview",
    ),
}


def _depth(text: str) -> str:
    q = text.lower()
    if re.search(r"\b(?:deep(?:er)?|deep dive|thorough|detailed)\b", q):
        return "DEEP"
    if re.search(r"\b(?:quick|brief|short)\b", q):
        return "QUICK"
    return "STANDARD"


def _operation(text: str, *, continuation: bool = False) -> str:
    if continuation:
        return "CONTINUE"
    q = text.lower()
    if re.search(r"\b(?:delete|remove|retire)\b", q): return "DELETE"
    if re.search(r"\b(?:update|change|edit|rename|reconcile|confirm)\b", q): return "UPDATE"
    if re.search(r"\b(?:create|add|new)\b", q): return "CREATE"
    if re.search(r"\b(?:restart|execute|run|scan|discover|install|turn on)\b", q): return "EXECUTE"
    if re.search(r"\b(?:research|investigate|deep dive|look into)\b", q): return "RESEARCH"
    if re.search(r"\b(?:monitor|watch|alert)\b", q): return "MONITOR"
    return "READ"


def compile_intent(query: str, *, continuation: bool = False, run_reference: str | None = None) -> IntentFrame:
    """Compile common current product concepts into a bounded IntentFrame."""
    text = str(query or "").strip()
    q = text.lower()
    operation = _operation(text, continuation=continuation)
    concept = "UNKNOWN"
    target = None
    if re.search(r"\b(?:asset(?:s)?|cmdb|hardware|server(?:s)?|technical equipment|machines?)\b", q):
        concept = "TECHNICAL_ASSET"
    elif re.search(r"\b(?:memory|remember|brain)\b", q):
        concept = "MEMORY"
    elif re.search(r"\b(?:network|lan|subnet|hosts?|devices?)\b", q):
        concept = "NETWORK"
    elif re.search(r"\b(?:finding|findings|security engagement|security assessment)\b", q):
        concept = "SECURITY_FINDING"
    elif re.search(r"\b(?:osint|open source intelligence|investigation|case)\b", q):
        concept = "OSINT_CASE"
    elif re.search(r"\b(?:work|working|project|task|goal|commitment)\b", q):
        concept = "WORK"
    elif re.search(r"\b(?:setup|configured|integration|connected)\b", q):
        concept = "INTEGRATION"
    match = re.search(r"\b(?:about|for|asset)\s+([A-Za-z0-9_.:-]{2,80})", text, re.IGNORECASE)
    if match:
        target = match.group(1)
    return IntentFrame(
        operation_class=operation,
        domain_concept=concept,
        target=target,
        entity_reference=target,
        run_reference=run_reference,
        depth=_depth(text),
        constraints=("no_filesystem_fallback",) if concept in {"TECHNICAL_ASSET", "NETWORK"} else (),
        desired_output="grounded_structured_summary" if operation == "READ" else None,
    )


def resolve_intent(frame: IntentFrame) -> ResolvedContract:
    contract = DOMAIN_CONTRACTS.get(frame.domain_concept)
    if contract is None:
        return ResolvedContract(frame, None, None, None, None, False, "no_domain_contract")
    action_id = contract.actions.get(frame.operation_class)
    if action_id is None and frame.operation_class == "CONTINUE":
        action_id = contract.actions.get("EXECUTE") or contract.actions.get("READ")
    if action_id is None:
        return ResolvedContract(frame, contract, None, None, contract.binding, False, "operation_not_registered")
    capability = capability_for_id(contract.capability_id)
    action = capability.actions.get(action_id) if capability else None
    if action is None or not action.known:
        return ResolvedContract(frame, contract, action_id, action, contract.binding, False, "actionspec_unavailable")
    binding = binding_for_tool(contract.binding or "") if contract.binding else None
    if binding is None or binding.capability_id != contract.capability_id:
        return ResolvedContract(frame, contract, action_id, action, contract.binding, False, "tool_binding_unavailable")
    return ResolvedContract(frame, contract, action_id, action, binding.transport_name, True)


def validate_contracts() -> list[str]:
    errors = []
    for concept, contract in DOMAIN_CONTRACTS.items():
        capability = capability_for_id(contract.capability_id)
        if capability is None:
            errors.append(f"{concept}: missing capability {contract.capability_id}")
            continue
        for operation, action_id in contract.actions.items():
            action = capability.actions.get(action_id)
            if action is None:
                errors.append(f"{concept}/{operation}: missing ActionSpec {action_id}")
                continue
            if contract.binding and binding_for_tool(contract.binding) is None:
                errors.append(f"{concept}: missing ToolBinding {contract.binding}")
            if operation == "READ" and action.approval.value != "none":
                errors.append(f"{concept}/{action_id}: read requires approval")
            if operation == "READ" and "read_private" not in action.effects:
                errors.append(f"{concept}/{action_id}: read lacks read_private effect")
            if not action.executor_key:
                errors.append(f"{concept}/{action_id}: missing executor")
            if not contract.result_contract:
                errors.append(f"{concept}/{action_id}: missing result contract")
    return errors


def generated_parity_matrix() -> list[dict[str, Any]]:
    """Generate transport applicability rows from the canonical contracts."""
    rows = []
    for concept, contract in DOMAIN_CONTRACTS.items():
        for operation, action_id in contract.actions.items():
            capability = capability_for_id(contract.capability_id)
            action = capability.actions.get(action_id) if capability else None
            rows.append({
                "concept": concept,
                "operation": operation,
                "action_id": action_id,
                "capability_id": contract.capability_id,
                "binding": contract.binding,
                "exposure": dict(contract.exposures),
                "result_contract": contract.result_contract,
                "effects": list(action.effects) if action else [],
                "approval": action.approval.value if action else None,
                "executor": action.executor_key if action else None,
                "execution_location": action.execution_location if action else None,
            })
    return rows


def result_status(result: Any) -> str:
    """Classify canonical results without turning failure-shaped empties into zero."""
    if not isinstance(result, Mapping):
        return "INVALID_RESULT"
    if result.get("error") or result.get("failed") is True or result.get("unavailable") is True:
        return "FAILED" if not result.get("unavailable") else "UNAVAILABLE"
    if result.get("status") in {"EMPTY_RESULT", "SUCCESS", "SUCCESS_RESULT"}:
        return str(result["status"])
    if not result:
        return "INVALID_RESULT"
    if isinstance(result.get("assets"), list) and not result["assets"]:
        return "EMPTY_RESULT"
    return "SUCCESS_RESULT"


def validate_result(frame: IntentFrame, result: Any) -> tuple[bool, str]:
    """Validate the small result shape promised by a resolved domain contract."""
    status = result_status(result)
    if status in {"FAILED", "UNAVAILABLE", "INVALID_RESULT"}:
        return False, status
    if frame.domain_concept == "TECHNICAL_ASSET" and frame.operation_class == "READ":
        if not isinstance(result.get("assets"), list):
            return False, "INVALID_RESULT"
    if frame.domain_concept == "NETWORK" and frame.operation_class == "READ":
        if not isinstance(result.get("nodes"), list) or not isinstance(result.get("edges"), list):
            return False, "INVALID_RESULT"
    if frame.domain_concept == "SECURITY_FINDING" and frame.operation_class == "READ":
        if not isinstance(result.get("findings"), list):
            return False, "INVALID_RESULT"
    return True, status
