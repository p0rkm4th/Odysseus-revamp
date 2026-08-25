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


def _is_continuation_phrase(text: str) -> bool:
    """Recognize operator continuation language without binding to a domain.

    A continuation may include a bounded natural-language qualification (for
    example, ``continue until the report is complete``).  The active Run and
    its pending Action remain authoritative; this helper only classifies the
    user turn and never selects or executes an Action.
    """
    return bool(re.match(
        r"^\s*(?:please\s+)?(?:continue|resume|proceed|go\s+ahead|do\s+it|"
        r"finish\s+it|keep\s+going|do\s+that|do\s+all\s+of\s+(?:the\s+)?"
        r"(?:above|those|them)|all\s+of\s+(?:the\s+)?(?:above|those|them))\b",
        str(text or ""),
        re.IGNORECASE,
    ))


@dataclass(frozen=True)
class IntentFrame:
    operation_class: str
    domain_concept: str
    workspace_hint: str | None = None
    target: str | None = None
    entity_reference: str | None = None
    run_reference: str | None = None
    continuation_reference: str | None = None
    filters: Mapping[str, Any] = field(default_factory=dict)
    scope: Mapping[str, Any] = field(default_factory=dict)
    depth: str = "STANDARD"
    constraints: tuple[str, ...] = ()
    desired_output: str | None = None
    reference_resolution: Mapping[str, Any] = field(default_factory=dict)
    read_explicit: bool = False
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


@dataclass(frozen=True)
class ContinuationResolution:
    """Pure resolution result; it never executes or grants authority."""

    status: str
    run_reference: str | None = None
    action_reference: str | None = None
    phase: str | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_reference": self.run_reference,
            "action_reference": self.action_reference,
            "phase": self.phase,
            "reason": self.reason,
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
    "SECURITY_ENGAGEMENT": DomainContract(
        "SECURITY_ENGAGEMENT", "security.assessment.read", {"READ": "list_engagements"}, "manage_security_assessment",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "security_engagement_list",
    ),
    "SECURITY_EVIDENCE": DomainContract(
        "SECURITY_EVIDENCE", "security.assessment.read", {"READ": "list_evidence"}, "manage_security_assessment",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "security_evidence_list",
    ),
    "NETWORK": DomainContract(
        "NETWORK", "homelab.manage", {"READ": "read_network_observations", "READ_CONTEXT": "read_network_context", "READ_UNIDENTIFIED": "list_unidentified_hosts", "READ_ROLES": "infer_role_hypotheses", "EXECUTE": "plan_network_discovery"}, "manage_homelab",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "network_capability_or_discovery",
    ),
    "HOMELAB_HOST": DomainContract(
        "HOMELAB_HOST", "homelab.manage", {"READ": "inspect_host"}, "manage_homelab",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "homelab_host_observation",
    ),
    "SERVICE": DomainContract(
        "SERVICE", "homelab.manage", {"READ": "service_status"}, "manage_homelab",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "service_status_observation",
    ),
    "OSINT_CASE": DomainContract(
        "OSINT_CASE", "research.public_sources", {"READ": "list_cases", "RESEARCH": "plan"}, "manage_osint",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "osint_case_or_plan",
    ),
    "RESEARCH": DomainContract(
        "RESEARCH", "research.public_sources", {"READ": "list_cases"}, "manage_osint",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "research_case_or_history_list",
    ),
    "MEMORY": DomainContract(
        "MEMORY", "memory.read", {"READ": "summarize_owner_memory"}, "read_memory",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "explicit_memory_read",
    ),
    "WORK": DomainContract(
        "WORK", "work.read", {"READ": "overview", "READ_ATTENTION": "attention"}, "read_work",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "work_overview",
    ),
    "GOAL": DomainContract("GOAL", "work.read", {"READ": "list_goals"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_goals"),
    "PROJECT": DomainContract("PROJECT", "work.read", {"READ": "list_projects"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_projects"),
    "TASK": DomainContract("TASK", "work.read", {"READ": "list_tasks"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_tasks"),
    "RUN": DomainContract("RUN", "work.read", {"READ": "list_runs"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_runs"),
    "COMMITMENT": DomainContract("COMMITMENT", "work.read", {"READ": "list_commitments"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_commitments"),
    "MISSION": DomainContract("MISSION", "work.read", {"READ": "list_missions"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_missions"),
    "WATCH": DomainContract("WATCH", "work.read", {"READ": "list_watches"}, "read_work", {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "work_watches"),
    "HOUSEHOLD_ITEM": DomainContract(
        "HOUSEHOLD_ITEM", "household.read", {"READ": "overview"}, "read_household",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "household_overview",
    ),
    "INTEGRATION": DomainContract(
        "INTEGRATION", "setup.read", {"READ": "state", "READ_INTEGRATIONS": "integrations"}, "read_setup",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "setup_state_or_integrations",
    ),
    "COMMUNICATIONS": DomainContract(
        "COMMUNICATIONS", "communications.read", {"READ": "overview"}, "read_communications",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "communications_overview",
    ),
    "CONTACT": DomainContract(
        "CONTACT", "communications.read", {"READ": "contacts"}, "read_communications",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"},
        "contact_list_or_unavailable",
    ),
    "CAREER_PROFILE": DomainContract(
        "CAREER_PROFILE", "career.read", {"READ": "overview"}, "read_career",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "career_overview",
    ),
    "JOB_SEARCH": DomainContract(
        "JOB_SEARCH", "career.read", {"READ": "overview", "RESEARCH": "provider_status"}, "read_career",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "career_search_or_provider",
    ),
    "JOB_OPPORTUNITY": DomainContract(
        "JOB_OPPORTUNITY", "career.read", {"READ": "saved_opportunities", "RESEARCH": "provider_status"}, "read_career",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "career_opportunities",
    ),
    "APPLICATION": DomainContract(
        "APPLICATION", "career.read", {"READ": "applications"}, "read_career",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "career_applications",
    ),
    "INTERVIEW": DomainContract(
        "INTERVIEW", "career.read", {"READ": "interviews"}, "read_career",
        {"MODEL": "YES", "API": "YES", "WORK": "YES", "UI": "YES", "AUTOMATION": "N/A"}, "career_interviews",
    ),
}


def _depth(text: str) -> str:
    q = text.lower()
    if re.search(r"\b(?:deep(?:er)?|deep dive|thorough|detailed)\b", q):
        return "DEEP"
    if re.search(r"\b(?:quick|brief|short)\b", q):
        return "QUICK"
    return "STANDARD"


def resolve_structured_reference(
    text: str,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve conversational references against server-owned opaque refs.

    This is intentionally a pure projection.  It never looks up a guessed ID,
    broadens scope, or authorizes an Action.  Callers may persist the compact
    context and pass it back after a model/provider swap.  Singular references
    fail closed when more than one candidate exists; plural language returns
    the exact bounded set supplied by the caller.
    """
    query = str(text or "").strip().lower()
    supplied = context if isinstance(context, Mapping) else {}
    candidates = [
        item for item in (supplied.get("entities") or supplied.get("references") or [])
        if isinstance(item, Mapping) and str(item.get("ref") or item.get("id") or "").strip()
    ]
    last = supplied.get("last") if isinstance(supplied.get("last"), Mapping) else None
    if last is not None and not any(
        str(item.get("ref") or item.get("id") or "") == str(last.get("ref") or last.get("id") or "")
        for item in candidates
    ):
        candidates.insert(0, last)

    plural = bool(re.search(
        r"\b(?:those|them|these|all(?:\s+of)?\s+(?:the\s+)?(?:above|those|them)|"
        r"all\s+of\s+them|everything)\b", query,
    ))
    ordinal_match = re.search(r"\b(?:the\s+)?(first|second|third)\s+one\b", query)
    singular = bool(re.search(r"\b(?:it|that|this|that\s+one)\b", query)) or bool(ordinal_match)
    if not plural and not singular:
        return {"status": "NOT_REFERENCE", "refs": [], "reason": "no structured reference phrase"}
    if not candidates:
        return {"status": "UNRESOLVED", "refs": [], "reason": "no durable reference context"}
    if ordinal_match:
        index = {"first": 0, "second": 1, "third": 2}[ordinal_match.group(1)]
        if index >= len(candidates):
            return {"status": "UNRESOLVED", "refs": [], "reason": "ordinal reference is out of range"}
        selected = [candidates[index]]
    elif plural:
        selected = candidates
    elif len(candidates) == 1:
        selected = candidates
    else:
        return {
            "status": "AMBIGUOUS", "refs": [],
            "candidate_refs": [str(item.get("ref") or item.get("id")) for item in candidates],
            "reason": "singular reference has multiple candidates",
        }
    refs = [str(item.get("ref") or item.get("id")) for item in selected]
    concepts = sorted({str(item.get("concept") or "").strip() for item in selected if item.get("concept")})
    return {
        "status": "RESOLVED",
        "refs": refs,
        "concept": concepts[0] if len(concepts) == 1 else None,
        "concepts": concepts,
        "selection": "ALL" if plural else "ONE",
    }


def _operation(text: str, *, continuation: bool = False) -> str:
    q = text.lower().strip()
    if continuation or _is_continuation_phrase(q):
        return "CONTINUE"
    if re.search(r"\b(?:delete|remove|retire)\b", q): return "DELETE"
    if re.search(r"\b(?:update|change|edit|rename|reconcile|confirm)\b", q): return "UPDATE"
    if re.search(r"\b(?:create|add|new)\b", q): return "CREATE"
    if re.search(r"\b(?:restart|execute|run|scan|discover|install|turn on)\b", q): return "EXECUTE"
    if re.search(r"\b(?:research|investigate|deep dive|look into)\b", q): return "RESEARCH"
    if re.search(r"\b(?:monitor|watch|alert)\b", q): return "MONITOR"
    return "READ"


def compile_intent(
    query: str,
    *,
    continuation: bool = False,
    run_reference: str | None = None,
    reference_context: Mapping[str, Any] | None = None,
) -> IntentFrame:
    """Compile common current product concepts into a bounded IntentFrame."""
    text = str(query or "").strip()
    q = text.lower()
    reference_resolution = resolve_structured_reference(text, reference_context)
    operation = _operation(text, continuation=continuation)
    # READ is the safe fallback operation for semantically incomplete text,
    # but canonical read projection must not treat every imperative containing
    # a domain noun as a request to inspect state. Keep this as bounded intent
    # metadata rather than a tool-name/route heuristic.
    read_explicit = bool(re.match(
        r"\s*(?:what(?:'s| is| are)?|which|who|where|when|how many|show|list|"
        r"tell me|do you have|are there|is there|find my|what do you)\b",
        q,
    ))
    # Interrogative requests about the research store are canonical reads;
    # the noun "research" must not turn "What research history do I have?"
    # into a new research execution request.
    if read_explicit and operation in {"RESEARCH", "MONITOR", "EXECUTE"}:
        operation = "READ"
    concept = "UNKNOWN"
    target = None
    if re.search(r"\b(?:security\s+engagement|engagements?)\b", q):
        concept = "SECURITY_ENGAGEMENT"
    elif re.search(r"\b(?:security\s+evidence|evidence\s+for\s+security|security\s+artifacts?)\b", q):
        concept = "SECURITY_EVIDENCE"
    elif re.search(r"\b(?:service(?:s)?|daemon(?:s)?)\b", q) and re.search(r"\b(?:status|running|active|homelab|server)\b", q):
        concept = "SERVICE"
    elif re.search(r"\b(?:homelab|container(?:s)?|storage|remote host(?:s)?)\b", q):
        concept = "HOMELAB_HOST"
    elif re.search(r"\b(?:mission(?:s)?)\b", q):
        concept = "MISSION"
    elif re.search(r"\b(?:watch(?:es)?|monitors?)\b", q):
        concept = "WATCH"
    elif re.search(r"\b(?:goal(?:s)?)\b", q):
        concept = "GOAL"
    elif re.search(r"\b(?:project(?:s)?)\b", q):
        concept = "PROJECT"
    elif re.search(r"\b(?:task(?:s)?)\b", q):
        concept = "TASK"
    elif re.search(r"\b(?:commitment(?:s)?)\b", q):
        concept = "COMMITMENT"
    elif re.search(r"\b(?:run(?:s)?)\b", q) and re.search(r"\b(?:active|current|durable|waiting|pending|run)\b", q):
        concept = "RUN"
    elif re.search(r"\b(?:research|research history)\b", q) and not re.search(r"\b(?:osint|investigation|case|cases)\b", q):
        concept = "RESEARCH"
    elif re.search(r"\b(?:devices?|hosts?)\b", q) and re.search(
        r"\b(?:look like|probably|role|roles|unidentified|unknown|on my network)\b", q,
    ):
        concept = "NETWORK"
    elif re.search(r"\b(?:asset(?:s)?|cmdb|hardware|server(?:s)?|technical equipment|machines?)\b", q):
        concept = "TECHNICAL_ASSET"
    elif re.search(r"\b(?:memory|remember|brain)\b", q):
        concept = "MEMORY"
    elif re.search(r"\b(?:network|lan|subnet|hosts?|devices?)\b", q):
        concept = "NETWORK"
    elif re.search(r"\b(?:finding|findings|security engagement|security assessment)\b", q):
        concept = "SECURITY_FINDING"
    elif re.search(r"\b(?:osint|open source intelligence|investigations?|cases?)\b", q):
        concept = "OSINT_CASE"
    elif re.search(r"\b(?:household|pantry|stock|shopping|recipe|recipes|groceries)\b", q):
        concept = "HOUSEHOLD_ITEM"
    elif re.search(r"\b(?:what(?:'s| is)\s+hades\s+waiting\s+on|what\s+needs\s+attention|waiting\s+on|pending\s+approvals?)\b", q):
        concept = "WORK"
    elif re.search(r"\b(?:work|working|project|task|goal|commitment)\b", q):
        concept = "WORK"
    elif re.search(r"\b(?:communications?|email accounts?|calendars?|calendar events?)\b", q):
        concept = "COMMUNICATIONS"
    elif re.search(r"\b(?:contacts?|address\s*book)\b", q):
        concept = "CONTACT"
    elif re.search(r"\b(?:setup|configured|integrations?|connected)\b", q):
        concept = "INTEGRATION"
    elif re.search(r"\b(?:career|job search|jobs?|opportunit(?:y|ies)|applications?|interviews?|resume|roles?)\b", q):
        if re.search(r"\b(?:application|applied|follow[- ]?up)", q): concept = "APPLICATION"
        elif re.search(r"\b(?:interview|interviews)", q): concept = "INTERVIEW"
        # Opportunity nouns and ordinary save/search language are semantic
        # evidence for the canonical opportunity collection.  In particular,
        # "did I save" must not fall through to the broader career profile.
        elif re.search(r"\b(?:opportunit(?:y|ies)|roles?)\b", q) or re.search(
            r"\b(?:sav(?:e|ed|ing)|similar|find|search)\b", q
        ): concept = "JOB_OPPORTUNITY"
        else: concept = "CAREER_PROFILE"
    # A resolved opaque reference may supply the semantic subject when the
    # latest turn is intentionally terse (for example, "scan those hosts").
    # It never supplies an ActionSpec or executor.  Conflicting concepts stay
    # ambiguous and are handled by the normal caller/UI clarification path.
    if reference_resolution.get("status") == "RESOLVED":
        referenced_concept = str(reference_resolution.get("concept") or "").strip()
        if concept == "UNKNOWN" and referenced_concept:
            concept = referenced_concept
        resolved_refs = list(reference_resolution.get("refs") or [])
        if len(resolved_refs) == 1 and not target:
            target = resolved_refs[0]
    match = re.search(r"\b(?:about|for|asset)\s+([A-Za-z0-9_.:-]{2,80})", text, re.IGNORECASE)
    if match:
        target = match.group(1)
    reference_filters = {}
    if reference_resolution.get("status") == "RESOLVED" and len(reference_resolution.get("refs") or []) > 1:
        reference_filters["entity_refs"] = list(reference_resolution["refs"])
    if concept == "WORK" and re.search(r"\b(?:attention|waiting\s+on|pending\s+approvals?)\b", q):
        reference_filters["view"] = "attention"
    elif concept == "INTEGRATION" and re.search(
        r"\bintegrations?\b.*\b(?:degraded|broken|attention|health|connected|working)\b|"
        r"\b(?:degraded|broken|attention|health)\b.*\bintegrations?\b", q,
    ):
        reference_filters["view"] = "integrations"
    elif concept == "NETWORK" and re.search(r"\b(?:unidentified|unknown|unrecognised|unrecognized)\b", q):
        reference_filters["view"] = "unidentified"
    elif concept == "NETWORK" and re.search(
        r"\b(?:what\s+network|which\s+network|network\s+am\s+i|currently\s+connected|current(?:ly)?\s+(?:on|connected))\b",
        q,
    ):
        reference_filters["view"] = "context"
    elif concept == "NETWORK" and re.search(r"\b(?:role|roles|server|servers|router|routers|nas|printer|workstation|iot)\b", q):
        reference_filters["view"] = "roles"
    workspace = {
        "MEMORY": "hades", "WORK": "work", "GOAL": "work", "PROJECT": "work", "TASK": "work", "RUN": "work", "COMMITMENT": "work", "MISSION": "work", "WATCH": "work", "CAREER_PROFILE": "work", "JOB_SEARCH": "work",
        "JOB_OPPORTUNITY": "work", "APPLICATION": "work", "INTERVIEW": "communications",
        "TECHNICAL_ASSET": "infrastructure", "NETWORK": "infrastructure", "HOMELAB_HOST": "infrastructure",
        "SERVICE": "infrastructure", "SECURITY_FINDING": "infrastructure", "SECURITY_ENGAGEMENT": "infrastructure",
        "SECURITY_EVIDENCE": "infrastructure", "OSINT_CASE": "research", "RESEARCH": "research",
        "HOUSEHOLD_ITEM": "home", "INTEGRATION": "system",
        "COMMUNICATIONS": "communications",
        "CONTACT": "communications",
    }.get(concept)
    return IntentFrame(
        operation_class=operation,
        domain_concept=concept,
        workspace_hint=workspace,
        target=target,
        entity_reference=target or (
            (reference_resolution.get("refs") or [None])[0]
            if reference_resolution.get("status") == "RESOLVED"
            else None
        ),
        run_reference=run_reference,
        continuation_reference=run_reference if operation == "CONTINUE" else None,
        depth=_depth(text),
        constraints=("no_filesystem_fallback",) if concept in {"TECHNICAL_ASSET", "NETWORK", "HOMELAB_HOST", "SERVICE"} else (),
        desired_output="grounded_structured_summary" if operation == "READ" else None,
        reference_resolution=reference_resolution,
        filters=reference_filters,
        read_explicit=read_explicit,
    )


def resolve_continuation(frame: IntentFrame, active_run: Mapping[str, Any] | None) -> ContinuationResolution:
    """Resolve generic continuation language against durable Run state.

    This is deliberately a decision projection. The caller still performs
    normal policy, approval, ActionSpec, and executor checks.
    """
    if frame.operation_class != "CONTINUE":
        return ContinuationResolution("NOT_CONTINUATION", reason="intent is not CONTINUE")
    if not isinstance(active_run, Mapping):
        return ContinuationResolution("BLOCKED", reason="no active Run")
    status = str(active_run.get("status") or "").lower()
    run_id = str(active_run.get("id") or active_run.get("run_id") or "").strip() or None
    if status in {"completed", "failed", "cancelled"}:
        return ContinuationResolution("BLOCKED", run_reference=run_id, phase="TERMINAL", reason="Run is terminal")
    state = active_run.get("continuation_state") if isinstance(active_run.get("continuation_state"), Mapping) else {}
    action_id = str(state.get("pending_action_id") or active_run.get("pending_action_id") or "").strip() or None
    if not run_id:
        return ContinuationResolution("BLOCKED", reason="active Run has no durable reference")
    if state.get("execution_ambiguous"):
        return ContinuationResolution(
            "BLOCKED", run_reference=run_id, action_reference=action_id,
            phase="EXECUTION_AMBIGUOUS", reason="independent verification is required before retry",
        )
    next_step = active_run.get("next_step")
    if isinstance(next_step, Mapping):
        next_status = str(next_step.get("status") or "").upper()
        next_action = next_step.get("action") if isinstance(next_step.get("action"), Mapping) else {}
        next_action_id = str(next_action.get("id") or "").strip() or action_id
        if next_status == "WAITING_APPROVAL":
            return ContinuationResolution("RESOLVED", run_id, next_action_id, "AWAITING_APPROVAL", "exact approval is pending")
        if next_status == "WAITING_INPUT":
            return ContinuationResolution("RESOLVED", run_id, next_action_id, "AWAITING_INPUT", "required input is pending")
        if next_status in {"READY", "IN_PROGRESS"} and next_action:
            return ContinuationResolution("RESOLVED", run_id, next_action_id, next_status, "durable next Action is available")
        if next_status == "COMPLETE":
            return ContinuationResolution("BLOCKED", run_id, next_action_id, "COMPLETE", "Run deliverable is already complete")
        if next_status in {"BLOCKED", "NO_PLAN", "UNAVAILABLE"}:
            return ContinuationResolution("BLOCKED", run_id, next_action_id, next_status, str(next_step.get("reason") or "Run cannot be continued safely"))
    actions = active_run.get("actions")
    if isinstance(actions, list):
        candidates = [item for item in actions if isinstance(item, Mapping) and item.get("status") in {
            "awaiting_approval", "awaiting_input", "proposed", "approved", "executing", "completed",
        }]
        for item in reversed(candidates):
            item_id = str(item.get("id") or "").strip() or None
            item_status = str(item.get("status") or "").lower()
            if item_status == "awaiting_approval":
                return ContinuationResolution("RESOLVED", run_id, item_id, "AWAITING_APPROVAL", "exact approval is pending")
            if item_status == "awaiting_input":
                return ContinuationResolution("RESOLVED", run_id, item_id, "AWAITING_INPUT", "required input is pending")
            if item_status in {"proposed", "approved", "executing"}:
                return ContinuationResolution("RESOLVED", run_id, item_id, item_status.upper(), "pending Action is available")
    phase = "AWAITING_APPROVAL" if status == "awaiting_approval" else "AWAITING_INPUT" if status == "awaiting_input" else "RUNNING"
    return ContinuationResolution("RESOLVED", run_id, action_id, phase)


def resolve_intent(frame: IntentFrame) -> ResolvedContract:
    contract = DOMAIN_CONTRACTS.get(frame.domain_concept)
    if contract is None:
        return ResolvedContract(frame, None, None, None, None, False, "no_domain_contract")
    action_key = frame.operation_class
    if frame.domain_concept == "WORK" and frame.filters.get("view") == "attention":
        action_key = "READ_ATTENTION"
    elif frame.domain_concept == "INTEGRATION" and frame.filters.get("view") == "integrations":
        action_key = "READ_INTEGRATIONS"
    elif frame.domain_concept == "NETWORK" and frame.filters.get("view") == "unidentified":
        action_key = "READ_UNIDENTIFIED"
    elif frame.domain_concept == "NETWORK" and frame.filters.get("view") == "context":
        action_key = "READ_CONTEXT"
    elif frame.domain_concept == "NETWORK" and frame.filters.get("view") == "roles":
        action_key = "READ_ROLES"
    action_id = contract.actions.get(action_key)
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
            if contract.binding:
                binding = binding_for_tool(contract.binding)
                properties = (((binding.native_schema or {}).get("function") or {}).get("parameters") or {}).get("properties") or {} if binding else {}
                action_enum = ((properties.get("action") or {}).get("enum") or []) if isinstance(properties, Mapping) else []
                missing_exposure = sorted(set(contract.actions.values()) - set(action_enum))
                if missing_exposure:
                    errors.append(f"{concept}: native schema omits ActionSpec exposure {missing_exposure}")
                textual_contract = str(binding.textual_contract or "") if binding else ""
                missing_textual = sorted(
                    action_id for action_id in set(contract.actions.values())
                    if action_id not in textual_contract
                )
                if missing_textual:
                    errors.append(f"{concept}: textual contract omits ActionSpec exposure {missing_textual}")
            if operation in {"READ", "READ_INTEGRATIONS", "READ_UNIDENTIFIED", "READ_ROLES", "READ_CONTEXT"} and action.approval.value != "none":
                errors.append(f"{concept}/{action_id}: read requires approval")
            if operation in {"READ", "READ_INTEGRATIONS", "READ_UNIDENTIFIED", "READ_ROLES", "READ_CONTEXT"} and "read_private" not in action.effects:
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
    if result.get("status") in {
        "EMPTY_RESULT", "SUCCESS_EMPTY", "SUCCESS", "SUCCESS_WITH_DATA",
        "SUCCESS_RESULT", "DEGRADED", "UNAVAILABLE", "FAILED",
    }:
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
        view = frame.filters.get("view")
        if view == "unidentified":
            if not isinstance(result.get("hosts"), list):
                return False, "INVALID_RESULT"
        elif view == "roles":
            if not isinstance(result.get("hypotheses"), list):
                return False, "INVALID_RESULT"
        elif not isinstance(result.get("nodes"), list) or not isinstance(result.get("edges"), list):
            return False, "INVALID_RESULT"
    if frame.domain_concept == "SECURITY_FINDING" and frame.operation_class == "READ":
        if not isinstance(result.get("findings"), list):
            return False, "INVALID_RESULT"
    return True, status


def validate_bound_result(binding_name: str, action_id: str, result: Any) -> tuple[bool, str]:
    """Validate a registered binding result against its declared contract.

    The dispatcher knows the canonical binding and ActionSpec but does not
    receive natural-language text. Resolve the owning DomainContract by that
    stable pair instead of asking an adapter or model to identify its own
    result semantics. Mutating/unregistered actions intentionally pass
    through here; their existing verified-execution lifecycle remains the
    authority for those payloads.
    """
    binding_name = str(binding_name or "").strip()
    action_id = str(action_id or "").strip()
    for concept, contract in DOMAIN_CONTRACTS.items():
        if contract.binding != binding_name:
            continue
        for operation, registered_action in contract.actions.items():
            if registered_action != action_id:
                continue
            if operation in {"READ", "READ_INTEGRATIONS", "READ_UNIDENTIFIED", "READ_ROLES"}:
                filters = {}
                if operation == "READ_INTEGRATIONS":
                    filters["view"] = "integrations"
                elif operation == "READ_UNIDENTIFIED":
                    filters["view"] = "unidentified"
                elif operation == "READ_ROLES":
                    filters["view"] = "roles"
                frame = IntentFrame(
                    operation_class="READ",
                    domain_concept=concept,
                    filters=filters,
                    read_explicit=True,
                )
                valid, reason = validate_result(frame, result)
                # Explicit adapter availability failures are truthful control
                # plane outcomes, not malformed successful payloads. Preserve
                # them for grounded reporting while still rejecting invalid
                # success-shaped data below.
                if reason in {"FAILED", "UNAVAILABLE"}:
                    return True, reason
                if not valid:
                    return valid, reason
                # Collection reads have a stable top-level member even when
                # the collection is empty.  Enforce that small contract at
                # the control-plane boundary rather than allowing an
                # adapter's bare SUCCESS marker to become canonical truth.
                expected = {
                    ("OSINT_CASE", "list_cases"): "cases",
                    ("RESEARCH", "list_cases"): "cases",
                    ("GOAL", "list_goals"): "goals",
                    ("PROJECT", "list_projects"): "projects",
                    ("TASK", "list_tasks"): "tasks",
                    ("RUN", "list_runs"): "runs",
                    ("COMMITMENT", "list_commitments"): "commitments",
                    ("MISSION", "list_missions"): "missions",
                    ("WATCH", "list_watches"): "watches",
                    ("HOUSEHOLD_ITEM", "list_items"): "items",
                    ("HOUSEHOLD_ITEM", "search_items"): "items",
                    ("COMMUNICATIONS", "overview"): "email",
                    ("CONTACT", "contacts"): "contacts",
                }.get((concept, action_id))
                if expected and not isinstance(result.get(expected), (list, dict)):
                    return False, "INVALID_RESULT"
                return True, reason
            # Contracted non-read projections currently have no additional
            # shape rules here; the trusted executor and Run verifier remain
            # authoritative for their effects.
            return True, result_status(result)
    return True, result_status(result)
