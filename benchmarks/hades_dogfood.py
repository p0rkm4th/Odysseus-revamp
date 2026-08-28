"""Shared Hades dogfood contract loading, normalization, scoring, and reports.

The contract is declarative, while source adapters reuse the existing ACI,
live-dogfood, Jarvis, and metamorphic corpora.  Records are sanitized at the
runtime boundary: prompts and answers are represented by digests/counts only.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import random
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from benchmarks.jarvis.synthetic_tools import fixture_tool_for_semantic_concept

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path(__file__).with_name("hades_dogfood_contract.json")
SCHEMA_VERSION = 1
_INTERNAL = re.compile(
    r"(?:manage_memory|read_memory|read_work|manage_assets|manage_homelab|"
    r"ToolBinding|ActionSpec|invalid bounded decision|invalid action choice)", re.I,
)
_SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:api[_-]?key|access[_-]?token|secret)\s*[:=]",
    re.I,
)
_REFUSAL = re.compile(
    r"\b(?:cannot|can't|won't|will not|unable to|need (?:your )?confirmation|"
    r"requires? (?:your )?approval|not going to|blocked|refuse)\b", re.I,
)
_REPAIR_LAYERS = {
    "answer_present": "runtime_completion",
    "concept": "semantic_routing",
    "operation": "semantic_routing",
    "decision_budget": "bounded_decision",
    "model_budget": "model_burden",
    "tool_index_budget": "tool_selection",
    "failed_action_budget": "action_authority",
    "context_budget": "context_projection",
    "exactly_once": "delivery_idempotency",
    "no_internal_leak": "answer_boundary",
}

_CHECK_FAILURE_CLASSES = {
    "answer_present": "COMPLETION_FAILURE", "concept": "DOMAIN_ROUTING_FAILURE",
    "operation": "INTENT_FAILURE", "decision_budget": "BURDEN_REGRESSION",
    "model_budget": "BURDEN_REGRESSION", "tool_index_budget": "BURDEN_REGRESSION",
    "failed_action_budget": "EXECUTION_FAILURE", "context_budget": "CONTEXT_FAILURE",
    "completion": "COMPLETION_FAILURE", "fallback": "MODEL_REASONING_FAILURE",
    "required_tools": "CANDIDATE_RETRIEVAL_FAILURE", "forbidden_tools": "SECURITY_FAILURE",
    "must_refuse": "SECURITY_FAILURE", "response_excludes": "GROUNDING_FAILURE",
    "recovery": "CONTINUATION_FAILURE", "exactly_once": "DUPLICATE_OUTPUT_FAILURE",
    "tool_budget": "BURDEN_REGRESSION",
}

# Corpus family names describe the evidence/view under test, while the
# runtime reports canonical IntentFrame concepts. Keep that translation
# explicit at the evaluator boundary; do not make production routing learn
# the corpus label.
_CANONICAL_CONCEPT_ALIASES = {
    "NETWORK_CONTEXT": "NETWORK",
}


def digest(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def load_contract(path: str | Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(contract, dict) or contract.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid Hades dogfood contract schema")
    for key in ("frozen_failures", "journeys", "imports", "budgets"):
        if not isinstance(contract.get(key), (list, dict)):
            raise ValueError(f"contract.{key} has invalid shape")
    return contract


def _case(case_id: str, prompt: str, *, family: str, source: str, split: str = "development",
          expected: Mapping[str, Any] | None = None, journey: str | None = None,
          scenario: Mapping[str, Any] | None = None, fixture_id: str | None = None,
          environment: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": case_id, "prompt": prompt, "family": family, "source": source,
        "split": split, "expected": dict(expected or {}), "journey": journey,
        "scenario": dict(scenario or {}), "fixture_id": fixture_id,
        "environment": dict(environment or {}),
    }


def _live_case_fixture_environment(data: Mapping[str, Any]) -> dict[str, Any]:
    """Declare synthetic live-case tools without consulting scoring fields."""
    family = str(data.get("family") or "").casefold()
    name = str(data.get("name") or "").casefold()
    prompt = str(data.get("prompt") or "").casefold()
    if family == "golden":
        if name.startswith("memory"):
            family = "memory"
        elif name.startswith("work"):
            family = "work"
        elif name.startswith("assets"):
            family = "assets"
        elif name.startswith(("network", "infra")):
            family = "infrastructure"
    if family == "memory":
        tool = "manage_memory" if any(word in prompt for word in ("forget", "save")) else "read_memory"
    elif family == "work" or (
        family == "continuation" and any(
            word in prompt for word in ("review", "outstanding", "work", "task", "run", "waiting", "blocked", "failed")
        )
    ):
        tool = "read_work"
    elif family == "assets":
        tool = "manage_assets"
    elif family in {"golden", "infrastructure", "network"} and not any(
        word in name for word in ("definition", "update", "scan", "near_miss")
    ):
        tool = "manage_homelab"
    else:
        return {}
    return {"fixture_profile": {"tools": [tool]}}


# These are semantic scenario generators, not production routing rules.  The
# generated prompt is merely an adversarial rendering of the structured case;
# the expected contract remains the source of truth.
_SCENARIO_ARCHETYPES: tuple[dict[str, Any], ...] = (
    {"family": "asset", "domain": "TECHNICAL_ASSET", "intent": "READ", "target": "asset", "prompts": ("tell me about {asset}", "what hardware is in {asset}", "{asset} info")},
    {"family": "asset_reference", "domain": "TECHNICAL_ASSET", "intent": "READ", "target": "reference", "prompts": ("what about {reference}", "show me the {ordinal} one", "what is that server")},
    {"family": "network_context", "domain": "NETWORK", "intent": "READ", "target": "network", "prompts": ("what network am i on", "show current network context", "where am i connected right now")},
    {"family": "remote_host", "domain": "HOMELAB_HOST", "intent": "READ", "target": "asset", "prompts": ("inspect remote host {asset} over SSH", "check the remote server {asset} via ssh", "what is running on remote machine {asset}")},
    {"family": "network_discovery", "domain": "NETWORK", "intent": "EXECUTE", "target": "subnet", "prompts": ("discover hosts on {subnet}", "scan the authorized lab range {subnet}", "find what is reachable on {subnet}")},
    {"family": "service_health", "domain": "SERVICE", "intent": "READ", "target": "service", "prompts": ("is {service} healthy", "check {service}", "why is {service} down")},
    {"family": "service_repair", "domain": "SERVICE", "intent": "EXECUTE", "target": "service", "prompts": ("restart {service} and verify it", "repair {service}", "make sure {service} comes back")},
    {"family": "memory", "domain": "MEMORY", "intent": "READ", "target": "owner", "prompts": ("what do you remember about me", "what have i told you", "show relevant memory")},
    {"family": "work", "domain": "WORK", "intent": "READ", "target": "work", "prompts": ("what am i working on", "show open work", "what needs attention")},
    {"family": "continuation", "domain": "WORK", "intent": "CONTINUE", "target": "run", "prompts": ("continue that run", "resume the task", "keep going with the current work")},
    {"family": "container", "domain": "CONTAINER", "intent": "READ", "target": "container", "prompts": ("inspect container {service}", "why is the container unhealthy", "show container state")},
    {"family": "storage", "domain": "STORAGE", "intent": "READ", "target": "storage", "prompts": ("how much disk space is left", "check storage pressure", "show backup freshness")},
    {"family": "model_runtime", "domain": "MODEL_RUNTIME", "intent": "READ", "target": "model", "prompts": ("is {model} available", "what model is running", "check Ollama health")},
    {"family": "dependency", "domain": "DEPENDENCY", "intent": "READ", "target": "dependency", "prompts": ("is nmap installed", "check the dependency for network discovery", "what is missing for this capability")},
    {"family": "security_scope", "domain": "SECURITY", "intent": "EXECUTE", "target": "scope", "prompts": ("scan {security_target}", "audit services on {security_target}", "check anything exposed on {security_target}")},
    {"family": "osint", "domain": "OSINT", "intent": "RESEARCH", "target": "public", "prompts": ("research {company} from public sources", "find public infrastructure for {company}", "build a sourced brief on {company}")},
    {"family": "household", "domain": "HOUSEHOLD_ITEM", "intent": "READ", "target": "item", "prompts": ("where is the {item}", "find my {item}", "list household items in the garage")},
    {"family": "kitchen", "domain": "KITCHEN", "intent": "READ", "target": "food", "prompts": ("what food expires soon", "what is in the pantry", "what should go on the shopping list")},
    {"family": "crm", "domain": "CRM", "intent": "READ", "target": "prospect", "prompts": ("which prospects need followup", "show the pipeline", "what do we know about this company")},
    {"family": "finance", "domain": "FINANCE", "intent": "READ", "target": "finance", "prompts": ("what bills are coming up", "show my budget state", "is the finance connector configured")},
    {"family": "developer", "domain": "DEVELOPER", "intent": "READ", "target": "workspace", "prompts": ("show the repository map", "search the workspace for the failing test", "view that file region")},
    {"family": "setup", "domain": "SETUP", "intent": "READ", "target": "integration", "prompts": ("what setup is incomplete", "show integration health", "what authority is enabled")},
    {"family": "background", "domain": "BACKGROUND_WORK", "intent": "READ", "target": "job", "prompts": ("what background jobs are running", "did the download finish", "show blocked runs")},
    {"family": "unknown_near_miss", "domain": "UNKNOWN", "intent": "READ", "target": "none", "prompts": ("what is a network", "how should i think about memory", "explain what a container is")},
)

_ASSET_NAMES = ("Thanatos", "Morpheus", "Cerberus", "Athena", "the media server")
_SERVICES = ("Jellyfin", "the reverse proxy", "Postgres", "Ollama", "the web service")
_SUBNETS = ("192.168.10.0/24", "10.20.30.0/24", "192.168.50.0/28")
_MODELS = ("qwen3:8b", "llama3.2", "the local model")
_COMPANIES = ("Acme", "the public company", "example.org")
_ITEMS = ("spare SSD", "monitor", "router")
_ORDINALS = ("first", "second", "third")
_FORMS = (
    "DIRECT", "PARAPHRASE", "FRAGMENT", "TYPO", "PROFANITY", "CASUAL",
    "TECHNICAL", "AMBIGUOUS", "PRONOUN", "ORDINAL", "FOLLOWUP",
    "SELF_CORRECTION", "DOMAIN_SWITCH", "MULTI_INTENT",
)
_STATES = ("HEALTHY", "DEGRADED", "FAILED", "MISSING", "STALE", "CONFLICTING", "UNKNOWN", "PARTIAL", "OFFLINE", "CHANGING")
_AUTHORITIES = ("READ_ALLOWED", "MUTATION_ALLOWED", "APPROVAL_REQUIRED", "APPROVAL_GRANTED", "APPROVAL_STALE", "OUT_OF_SCOPE", "UNKNOWN_SCOPE", "BLOCKED")
_RESULTS = ("SUCCESS", "FAILURE", "TIMEOUT", "PARTIAL", "STALE_PRECONDITION", "VERIFICATION_FAILURE", "DEPENDENCY_MISSING", "CAPABILITY_UNAVAILABLE")
_ENTITY_TYPES = (
    "asset", "service", "container", "vm", "network", "subnet", "interface",
    "route", "dns", "firewall", "gpu", "model", "storage", "backup",
    "remote_node", "owner", "workspace", "none",
)
_MODEL_PROFILES = ("qwen3:8b", "small_local", "strong_local", "teacher", "unknown")
_VERIFICATION_RESULTS = ("VERIFIED", "FAILED", "PARTIAL", "NOT_RUN", "UNKNOWN")
_INTENT_CLASSES = (
    "READ", "CREATE", "UPDATE", "DELETE", "EXECUTE", "RESEARCH", "MONITOR",
    "CONTINUE", "ANSWER", "CLARIFY", "BLOCKED", "DIAGNOSE", "COMPARE",
    "EXPLAIN", "PLAN", "CHANGE", "REPAIR", "DISCOVER", "VERIFY",
)
_CROSS_DOMAIN_PAIRS = (
    "ASSETSxNETWORK", "ASSETSxINFRA", "ASSETSxMEMORY", "ASSETSxWORK",
    "NETWORKxSECURITY", "NETWORKxINFRA", "NETWORKxSELFSTATE", "NETWORKxMEMORY",
    "INFRAxDEPENDENCIES", "INFRAxBACKGROUND_JOBS", "INFRAxWORK", "INFRAxVERIFICATION",
    "MODELSxGPU", "MODELSxINFRA", "MODELSxDEPENDENCIES", "MODELSxSELFSTATE",
    "WORKxCONTINUATION", "WORKxAPPROVALS", "WORKxBACKGROUND_JOBS",
    "MCPxPOLICY", "MCPxSECURITY", "MCPxCAPABILITIES", "SETUPxCAPABILITIES",
    "SETUPxHEALTH", "DEVELOPERxWORK", "DEVELOPERxSECURITY", "DEVELOPERxVERIFICATION",
)

_CAPABILITY_FOR_FAMILY = {
    "asset": ("inventory.manage", "get"), "asset_reference": ("inventory.manage", "get"),
    "remote_host": ("homelab.manage", "remote_host_inspect"),
    "network_context": ("homelab.manage", "read_network_context"), "network_discovery": ("homelab.manage", "execute_network_discovery"),
    "service_health": ("homelab.manage", "service_status"), "service_repair": ("homelab.manage", "execute_service_restart"),
    "memory": ("memory.read", "summarize_owner_memory"), "work": ("work.read", "overview"),
    "continuation": ("work.run.read", "context"), "container": ("homelab.manage", "inspect_host"),
    "storage": ("homelab.manage", "inspect_host"), "model_runtime": ("setup.read", "state"),
    "dependency": ("capability.registry", "inspect_registry"), "security_scope": ("security.assessment.read", "list_findings"),
    "osint": ("research.public_sources", "search"), "household": ("household.read", "search_items"),
    "kitchen": ("household.read", "search_items"), "crm": ("work.read", "context"),
    "finance": ("work.read", "overview"), "developer": ("developer.read", "show_repo_map"),
    "setup": ("setup.read", "state"), "background": ("work.run.read", "list"),
}

_SYNTHETIC_TOOL_FOR_CAPABILITY = {
    "inventory.manage": "manage_assets",
    "homelab.manage": "manage_homelab",
    "memory.read": "read_memory",
    "work.read": "read_work",
    "work.goal.read": "read_work",
    "work.project.read": "read_work",
    "work.task.read": "read_work",
    "work.run.read": "read_work",
    "work.commitment.read": "read_work",
    "household.read": "read_household",
    "setup.read": "read_setup",
    "capability.registry": "read_setup",
    "research.public_sources": "manage_osint",
    "security.assessment.read": "manage_security_assessment",
    "developer.read": "developer_read",
}

# Registry entries use fine-grained capability IDs, while the synthetic
# executor exposes these existing bounded transport names. This is fixture
# projection only; it never selects an Action or changes authority.
_SYNTHETIC_TOOL_FOR_EXECUTOR = {
    "manage_assets": "manage_assets", "manage_homelab": "manage_homelab",
    "manage_memory": "read_memory", "read_memory": "read_memory",
    "manage_work": "read_work", "read_work": "read_work",
    "read_household": "read_household", "manage_household": "read_household",
    "read_setup": "read_setup", "manage_osint": "manage_osint",
    "manage_security_assessment": "manage_security_assessment",
    "developer_read": "developer_read",
}


def _generated_fixture_environment(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """Project only the simulated external world for a generated case.

    Capability identity is part of the generated semantic frame.  It is not
    an evaluator expectation, so this projection keeps fixture availability
    independent of the answer key and prevents oracle metadata from shaping
    the product trajectory.
    """
    capability = str(scenario.get("capability_id") or "").strip()
    tool = _SYNTHETIC_TOOL_FOR_CAPABILITY.get(capability)
    if not tool:
        tool = _SYNTHETIC_TOOL_FOR_EXECUTOR.get(str(scenario.get("executor") or "").strip())
    return {"fixture_profile": {"tools": [tool]}} if tool else {}

_CAPABILITY_DOMAIN_HINTS = {
    "developer.workspace_shell": "DEVELOPER", "developer.read": "DEVELOPER",
    "inventory.manage": "TECHNICAL_ASSET", "memory.read": "MEMORY",
    "work.read": "WORK", "work.goal.read": "WORK", "work.goal.manage": "WORK",
    "work.project.read": "WORK", "work.project.manage": "WORK",
    "work.task.read": "WORK", "work.task.manage": "WORK",
    "work.run.read": "WORK", "work.run.manage": "WORK",
    "work.commitment.read": "WORK", "work.commitment.manage": "WORK",
    "household.read": "HOUSEHOLD_ITEM", "setup.read": "SETUP",
    "career.read": "CRM", "career.provider": "CRM",
    "communications.read": "CRM", "system.privileged_diagnostics": "HOMELAB_HOST",
    "homelab.manage": "HOMELAB_HOST", "research.public_sources": "OSINT",
    "web.evidence": "OSINT", "capability.registry": "SETUP",
    "security.assessment.read": "SECURITY", "security.engagement.manage": "SECURITY",
    "security.scope.manage": "SECURITY", "security.target.resolve": "SECURITY",
    "security.context.read": "SECURITY", "security.observation.ingest": "SECURITY",
    "security.run.plan": "SECURITY", "security.recon.execute": "SECURITY",
    "security.finding.manage": "SECURITY", "security.finding.confirm": "SECURITY",
    "security.finding.verify": "SECURITY", "security.report.generate": "SECURITY",
    "intelligence.route": "UNKNOWN",
}


# The scenario universe is deliberately separate from production routing.  A
# frame is the oracle; its wording is only an adversarial projection.  Keeping
# this contract typed makes it possible to grow coverage without turning the
# generator into a phrase dictionary.
_SEMANTIC_ENTITY_TYPES = (
    "PERSON", "HOST", "NETWORK", "SERVICE", "CONTAINER", "VM", "ASSET",
    "PROJECT", "TASK", "RUN", "BUSINESS", "CONTACT", "MODEL", "PROVIDER",
    "STORAGE", "BACKUP", "INTEGRATION",
)
_SEMANTIC_INTENTS = (
    "IDENTIFY", "READ", "LOCATE", "LIST", "COUNT", "SUMMARIZE", "COMPARE",
    "EXPLAIN", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "FIND_ANOMALY",
    "PLAN", "DISCOVER", "CHECK_EXPECTATION", "CHANGE", "REPAIR", "INSTALL",
    "START", "STOP", "RESTART", "ROLLBACK", "CONTINUE",
)
_SEMANTIC_AUTHORITIES = _AUTHORITIES + ("DISABLED",)
_TEMPORAL_SCOPES = (
    "CURRENT", "LATEST_OBSERVED", "HISTORICAL", "AT_TIME", "SINCE_TIME",
    "BEFORE_EVENT", "AFTER_EVENT", "DELTA", "TREND", "EXPECTED_FUTURE",
)
_EPISTEMIC_STATES = (
    "OBSERVED", "USER_ASSERTED", "RETRIEVED", "REMEMBERED", "INFERRED",
    "HISTORICAL", "UNKNOWN", "CONTRADICTED", "STALE",
)
_REFERENCE_STRATEGIES = (
    "EXACT_NAME", "CASE_VARIATION", "ALIAS", "MISSPELLING", "HOSTNAME", "IP",
    "ROLE", "PROPERTY", "RELATION", "PRONOUN", "DEICTIC", "ORDINAL",
    "RECENT_REFERENT", "OLDER_REFERENT", "AMBIGUOUS_ALIAS", "MULTIPLE_MATCHES",
    "SELF_CORRECTION",
)
_RELATIONS = (
    "OWNS", "RUNS", "MEMBER_OF", "DEPENDS_ON", "LOCATED_IN", "USES",
    "ASSOCIATED_WITH", "BACKED_UP_BY", "EXPOSES", "CHANGED_FROM",
)
_REQUESTED_PROPERTIES = (
    "identity", "name", "role", "owner", "hardware", "cpu", "ram", "gpu",
    "storage", "filesystem", "os", "packages", "processes", "services",
    "network", "ip", "dns", "routes", "gateway", "ports", "reachability",
    "health", "dependencies", "backups", "history", "changes", "provenance",
)

# A semantic generator must not claim coverage for questions that cannot be
# meaningful for the selected entity.  These are evaluator constraints only;
# production routing remains contract/state driven.  Keep the fallback broad
# enough that newly added entity types still receive useful exploratory cases.
_ENTITY_PROPERTIES: dict[str, tuple[str, ...]] = {
    "PERSON": ("identity", "name", "owner", "history", "changes", "provenance"),
    "HOST": ("identity", "name", "role", "hardware", "cpu", "ram", "gpu", "storage", "filesystem", "os", "packages", "processes", "services", "network", "ip", "dns", "routes", "gateway", "ports", "reachability", "health", "dependencies", "backups", "history", "changes", "provenance"),
    "NETWORK": ("identity", "name", "owner", "network", "ip", "dns", "routes", "gateway", "ports", "reachability", "health", "services", "history", "changes", "provenance"),
    "SERVICE": ("identity", "name", "owner", "processes", "ports", "reachability", "health", "dependencies", "history", "changes", "provenance"),
    "CONTAINER": ("identity", "name", "owner", "storage", "processes", "services", "network", "ports", "reachability", "health", "dependencies", "history", "changes", "provenance"),
    "VM": ("identity", "name", "role", "hardware", "storage", "os", "processes", "services", "network", "ip", "reachability", "health", "history", "changes", "provenance"),
    "ASSET": ("identity", "name", "role", "owner", "hardware", "storage", "os", "network", "ip", "services", "reachability", "health", "history", "changes", "provenance"),
    "PROJECT": ("identity", "name", "owner", "history", "changes", "provenance"),
    "TASK": ("identity", "name", "owner", "history", "changes", "provenance"),
    "RUN": ("identity", "name", "owner", "status", "history", "changes", "provenance"),
    "BUSINESS": ("identity", "name", "owner", "history", "changes", "provenance"),
    "CONTACT": ("identity", "name", "owner", "history", "changes", "provenance"),
    "MODEL": ("identity", "name", "provider", "gpu", "health", "dependencies", "history", "changes", "provenance"),
    "PROVIDER": ("identity", "name", "health", "dependencies", "history", "changes", "provenance"),
    "STORAGE": ("identity", "name", "owner", "storage", "filesystem", "health", "backups", "history", "changes", "provenance"),
    "BACKUP": ("identity", "name", "owner", "storage", "health", "history", "changes", "provenance"),
    "INTEGRATION": ("identity", "name", "owner", "health", "dependencies", "history", "changes", "provenance"),
}

_ENTITY_RELATIONS: dict[str, tuple[str, ...]] = {
    "PERSON": ("OWNS", "USES", "ASSOCIATED_WITH"),
    "HOST": ("RUNS", "MEMBER_OF", "LOCATED_IN", "BACKED_UP_BY", "EXPOSES", "CHANGED_FROM"),
    "NETWORK": ("MEMBER_OF", "LOCATED_IN", "EXPOSES", "CHANGED_FROM"),
    "SERVICE": ("RUNS", "DEPENDS_ON", "LOCATED_IN", "EXPOSES", "CHANGED_FROM"),
    "CONTAINER": ("RUNS", "DEPENDS_ON", "MEMBER_OF", "EXPOSES", "CHANGED_FROM"),
    "VM": ("RUNS", "MEMBER_OF", "LOCATED_IN", "BACKED_UP_BY", "CHANGED_FROM"),
    "ASSET": ("OWNS", "MEMBER_OF", "LOCATED_IN", "BACKED_UP_BY", "ASSOCIATED_WITH", "CHANGED_FROM"),
    "PROJECT": ("OWNS", "ASSOCIATED_WITH", "CHANGED_FROM"),
    "TASK": ("ASSOCIATED_WITH", "DEPENDS_ON", "CHANGED_FROM"),
    "RUN": ("ASSOCIATED_WITH", "DEPENDS_ON", "CHANGED_FROM"),
    "BUSINESS": ("OWNS", "ASSOCIATED_WITH", "LOCATED_IN", "CHANGED_FROM"),
    "CONTACT": ("ASSOCIATED_WITH", "OWNS", "CHANGED_FROM"),
    "MODEL": ("RUNS", "USES", "DEPENDS_ON", "LOCATED_IN", "CHANGED_FROM"),
    "PROVIDER": ("OWNS", "ASSOCIATED_WITH", "CHANGED_FROM"),
    "STORAGE": ("BACKED_UP_BY", "LOCATED_IN", "ASSOCIATED_WITH", "CHANGED_FROM"),
    "BACKUP": ("BACKED_UP_BY", "ASSOCIATED_WITH", "CHANGED_FROM"),
    "INTEGRATION": ("DEPENDS_ON", "ASSOCIATED_WITH", "CHANGED_FROM"),
}
_LANGUAGE_TRANSFORMS = (
    "formal", "normal", "terse", "fragment", "run_on", "novice", "expert",
    "sysadmin", "casual", "profane", "polite", "lowercase", "typo",
    "asr", "filler", "self_correction", "relational", "implied_verb",
)
_NETWORK_SCOPE_STATES = ("HOME", "WORK", "VPN", "UNKNOWN")
_ADDRESS_STATES = ("UNCHANGED", "DHCP_CHANGED", "NEW", "UNKNOWN")
_ASSET_IDENTITY_STRENGTHS = ("STRONG", "WEAK", "IP_ONLY", "CONFLICTED")
_STATE_MUTATIONS = (
    "NONE", "DHCP_ADDRESS_CHANGED", "SERVICE_DEGRADED", "HOST_DISAPPEARED",
    "HOST_REAPPEARED", "VPN_ACTIVATED", "ROUTE_CHANGED", "DEPENDENCY_REMOVED",
    "ASSET_RENAMED", "NEW_DEVICE_JOINED", "APPROVAL_EXPIRED", "MODEL_UNAVAILABLE",
    "BACKGROUND_JOB_FINISHED",
)


@dataclass(frozen=True)
class ScenarioFrame:
    """Canonical semantic oracle used to generate and grade dogfood input."""

    entity_type: str
    entity_id: str
    related_entities: tuple[str, ...]
    intent: str
    requested_property: str
    relation: str
    relation_depth: int
    temporal_scope: str
    epistemic_state: str
    expected_domain: str
    secondary_domains: tuple[str, ...]
    expected_reference_resolution: str
    expected_authority: str
    expected_action_class: str
    execution_required: bool
    approval_state: str
    initial_world_state: Mapping[str, Any]
    expected_result_state: str
    expected_completion_state: str
    expected_grounding: str
    network_scope: str = "UNKNOWN"
    address_state: str = "UNKNOWN"
    asset_identity_strength: str = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe frame without changing its semantic fields."""
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ScenarioFrame":
        """Rehydrate a persisted frame for exact failure replay."""
        fields = {
            field: value[field]
            for field in cls.__dataclass_fields__
            if field in value
        }
        fields["related_entities"] = tuple(fields.get("related_entities") or ())
        fields["secondary_domains"] = tuple(fields.get("secondary_domains") or ())
        return cls(**fields)


_ENTITY_INTENTS: dict[str, tuple[str, ...]] = {
    "PERSON": ("IDENTIFY", "READ", "LOCATE", "LIST", "SUMMARIZE", "HISTORY", "COMPARE", "CONTINUE"),
    "HOST": ("IDENTIFY", "READ", "LOCATE", "LIST", "COUNT", "COMPARE", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "FIND_ANOMALY", "PLAN", "DISCOVER", "CHANGE", "REPAIR", "INSTALL", "START", "STOP", "RESTART", "ROLLBACK"),
    "NETWORK": ("IDENTIFY", "READ", "LOCATE", "LIST", "COUNT", "SUMMARIZE", "COMPARE", "EXPLAIN", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "FIND_ANOMALY", "PLAN", "DISCOVER", "CHECK_EXPECTATION", "CHANGE", "REPAIR"),
    "SERVICE": ("IDENTIFY", "READ", "LOCATE", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "FIND_ANOMALY", "PLAN", "CHANGE", "REPAIR", "START", "STOP", "RESTART", "ROLLBACK"),
    "CONTAINER": ("IDENTIFY", "READ", "LIST", "COMPARE", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "PLAN", "CHANGE", "REPAIR", "START", "STOP", "RESTART", "ROLLBACK"),
    "VM": ("IDENTIFY", "READ", "LIST", "COMPARE", "VERIFY", "DIAGNOSE", "PLAN", "CHANGE", "REPAIR", "START", "STOP", "RESTART", "ROLLBACK"),
    "ASSET": ("IDENTIFY", "READ", "LOCATE", "LIST", "COUNT", "SUMMARIZE", "COMPARE", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "DISCOVER", "CHANGE"),
    "PROJECT": ("IDENTIFY", "READ", "LIST", "COUNT", "SUMMARIZE", "COMPARE", "HISTORY", "DELTA", "VERIFY", "PLAN", "CHANGE", "CONTINUE"),
    "TASK": ("IDENTIFY", "READ", "LIST", "COUNT", "SUMMARIZE", "COMPARE", "HISTORY", "DELTA", "VERIFY", "PLAN", "CHANGE", "REPAIR", "CONTINUE"),
    "RUN": ("IDENTIFY", "READ", "LIST", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "CONTINUE", "ROLLBACK"),
    "BUSINESS": ("IDENTIFY", "READ", "LOCATE", "LIST", "COUNT", "SUMMARIZE", "COMPARE", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "PLAN", "CHANGE"),
    "CONTACT": ("IDENTIFY", "READ", "LOCATE", "LIST", "COUNT", "SUMMARIZE", "COMPARE", "HISTORY", "DELTA", "VERIFY", "CHANGE"),
    "MODEL": ("IDENTIFY", "READ", "LIST", "COMPARE", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "PLAN", "CHANGE", "REPAIR", "INSTALL", "START", "STOP", "RESTART", "ROLLBACK"),
    "PROVIDER": ("IDENTIFY", "READ", "LIST", "COMPARE", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "CHANGE", "REPAIR"),
    "STORAGE": ("IDENTIFY", "READ", "LIST", "COUNT", "SUMMARIZE", "COMPARE", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "FIND_ANOMALY", "PLAN", "CHANGE", "REPAIR"),
    "BACKUP": ("IDENTIFY", "READ", "LIST", "COUNT", "SUMMARIZE", "COMPARE", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "PLAN", "CHANGE", "REPAIR", "ROLLBACK"),
    "INTEGRATION": ("IDENTIFY", "READ", "LIST", "COMPARE", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "PLAN", "CHANGE", "REPAIR", "INSTALL", "START", "STOP", "RESTART"),
}


def _semantic_entity_id(entity_type: str, index: int) -> str:
    names = {
        "PERSON": ("owner", "Alex", "Jordan"), "HOST": _ASSET_NAMES,
        "NETWORK": _SUBNETS, "SERVICE": _SERVICES, "CONTAINER": ("jellyfin", "proxy", "postgres"),
        "VM": ("vm-01", "proxmox-guest", "media-vm"), "ASSET": _ASSET_NAMES,
        "PROJECT": ("homelab refresh", "website", "onboarding"), "TASK": ("inspect host", "renew certificate", "check backup"),
        "RUN": ("current run", "discovery run", "repair run"), "BUSINESS": _COMPANIES,
        "CONTACT": ("primary contact", "operator", "vendor contact"), "MODEL": _MODELS,
        "PROVIDER": ("Ollama", "cloud provider", "SSH provider"), "STORAGE": ("root disk", "bulk pool", "backup volume"),
        "BACKUP": ("nightly backup", "snapshot", "PBS job"), "INTEGRATION": ("Telegram", "Chroma", "broker"),
    }
    return str(names.get(entity_type, (entity_type.casefold(),))[index % len(names.get(entity_type, (entity_type.casefold(),)))])


def _build_scenario_frame(*, index: int, rng: random.Random, archetype: Mapping[str, Any],
                          state: str, authority: str, execution_result: str,
                          reference_type: str, domain: str, intent: str,
                          action_class: str | None = None) -> ScenarioFrame:
    """Build a constrained semantic frame before rendering any language."""
    target_entity = str(archetype.get("target") or "").casefold()
    entity_type = {
        "person": "PERSON", "host": "HOST", "business": "BUSINESS", "contact": "CONTACT",
        "provider": "PROVIDER", "project": "PROJECT", "task": "TASK", "run": "RUN",
        "vm": "VM", "backup": "BACKUP", "integration": "INTEGRATION", "storage": "STORAGE",
        "model": "MODEL",
        "asset": "ASSET", "reference": "ASSET", "service": "SERVICE", "container": "CONTAINER",
        "subnet": "NETWORK", "network": "NETWORK", "owner": "PERSON", "work": "PROJECT",
        "run": "RUN", "storage": "STORAGE", "model": "MODEL", "dependency": "INTEGRATION",
        "scope": "NETWORK", "public": "BUSINESS", "item": "ASSET", "food": "ASSET",
        "prospect": "BUSINESS", "finance": "PERSON", "workspace": "PROJECT", "integration": "INTEGRATION",
        "job": "RUN", "capability": "INTEGRATION", "none": "NETWORK",
    }.get(target_entity, target_entity.upper() if target_entity.upper() in _SEMANTIC_ENTITY_TYPES else "HOST")
    entity_id = _semantic_entity_id(entity_type, index)
    relation_choices = _ENTITY_RELATIONS.get(entity_type, _RELATIONS)
    relation = relation_choices[index % len(relation_choices)]
    relation_depth = index % 4
    temporal_scope = _TEMPORAL_SCOPES[index % len(_TEMPORAL_SCOPES)]
    epistemic_state = _EPISTEMIC_STATES[index % len(_EPISTEMIC_STATES)]
    property_choices = _ENTITY_PROPERTIES.get(entity_type, _REQUESTED_PROPERTIES)
    execution_required = intent in {"EXECUTE", "CHANGE", "REPAIR", "INSTALL", "START", "STOP", "RESTART", "ROLLBACK", "DISCOVER"}
    approval_state = (
        "STALE" if authority == "APPROVAL_STALE" else
        "REQUIRED" if authority == "APPROVAL_REQUIRED" else
        "GRANTED" if authority == "APPROVAL_GRANTED" else
        "DENIED" if authority in {"OUT_OF_SCOPE", "UNKNOWN_SCOPE", "BLOCKED", "DISABLED"} else
        "NONE"
    )
    result_state = execution_result
    completion = {
        "SUCCESS": "COMPLETE_AFTER_ANSWER", "FAILURE": "BLOCKED", "TIMEOUT": "BLOCKED",
        "PARTIAL": "NEEDS_BOUNDED_REASONING", "STALE_PRECONDITION": "BLOCKED",
        "VERIFICATION_FAILURE": "BLOCKED", "DEPENDENCY_MISSING": "NEEDS_CONTEXT",
        "CAPABILITY_UNAVAILABLE": "BLOCKED",
    }[execution_result]
    grounding = "CURRENT_ACTION_RESULT" if execution_result == "SUCCESS" else (
        "QUALIFIED_STALE_EVIDENCE" if temporal_scope in {"HISTORICAL", "BEFORE_EVENT"} or epistemic_state in {"STALE", "HISTORICAL"}
        else "CANONICAL_CONTEXT"
    )
    secondary = tuple(part for part in ("NETWORK", "ASSETS", "MEMORY", "WORK") if part != domain and index % (len(part) + 1) == 0)[:2]
    return ScenarioFrame(
        entity_type=entity_type, entity_id=entity_id,
        related_entities=(_semantic_entity_id("SERVICE", index), _semantic_entity_id("NETWORK", index))[:1 + (relation_depth > 1)],
        intent=intent, requested_property=property_choices[index % len(property_choices)],
        relation=relation, relation_depth=relation_depth, temporal_scope=temporal_scope,
        epistemic_state=epistemic_state, expected_domain=domain, secondary_domains=secondary,
        expected_reference_resolution=reference_type, expected_authority=authority,
        expected_action_class=action_class or intent, execution_required=execution_required,
        approval_state=approval_state, initial_world_state={"condition": state, "evidence": epistemic_state},
        expected_result_state=result_state, expected_completion_state=completion,
        expected_grounding=grounding,
        network_scope=_NETWORK_SCOPE_STATES[index % len(_NETWORK_SCOPE_STATES)],
        address_state=_ADDRESS_STATES[index % len(_ADDRESS_STATES)],
        asset_identity_strength=_ASSET_IDENTITY_STRENGTHS[index % len(_ASSET_IDENTITY_STRENGTHS)],
    )


def generate_scenario_frames(*, seed: int = 0, count: int = 1000) -> list[ScenarioFrame]:
    """Generate reproducible, compatibility-constrained semantic frames.

    This is intentionally a covering-array style sampler, not a Cartesian
    product.  Every frame is valid for its entity's intent universe while the
    rotating dimensions force broad pairwise/3-way coverage before random
    combinations are introduced.
    """
    rng = random.Random(int(seed))
    frames: list[ScenarioFrame] = []
    for index in range(max(0, int(count))):
        entity_type = _SEMANTIC_ENTITY_TYPES[index % len(_SEMANTIC_ENTITY_TYPES)]
        compatible = _ENTITY_INTENTS[entity_type]
        intent = compatible[(index // len(_SEMANTIC_ENTITY_TYPES)) % len(compatible)] if index < len(_SEMANTIC_ENTITY_TYPES) * len(compatible) else rng.choice(compatible)
        domain = {"PERSON": "MEMORY", "HOST": "HOMELAB_HOST", "NETWORK": "NETWORK", "SERVICE": "SERVICE", "CONTAINER": "CONTAINER", "VM": "HOMELAB_HOST", "ASSET": "TECHNICAL_ASSET", "PROJECT": "WORK", "TASK": "WORK", "RUN": "WORK", "BUSINESS": "CRM", "CONTACT": "CRM", "MODEL": "MODEL_RUNTIME", "PROVIDER": "SETUP", "STORAGE": "STORAGE", "BACKUP": "STORAGE", "INTEGRATION": "SETUP"}[entity_type]
        archetype = {"target": entity_type.casefold()}
        authority = _SEMANTIC_AUTHORITIES[(index // len(_STATES)) % len(_SEMANTIC_AUTHORITIES)]
        state = _STATES[index % len(_STATES)]
        result = _RESULTS[index % len(_RESULTS)]
        reference = _REFERENCE_STRATEGIES[index % len(_REFERENCE_STRATEGIES)]
        action_class = "READ" if intent in {"IDENTIFY", "READ", "LOCATE", "LIST", "COUNT", "SUMMARIZE", "COMPARE", "EXPLAIN", "HISTORY", "DELTA", "VERIFY", "DIAGNOSE", "FIND_ANOMALY", "CHECK_EXPECTATION"} else intent
        frames.append(_build_scenario_frame(index=index, rng=rng, archetype=archetype, state=state, authority=authority, execution_result=result, reference_type=reference, domain=domain, intent=intent, action_class=action_class))
    return frames


def _frame_archetype(frame: ScenarioFrame) -> dict[str, Any]:
    """Project a frame into neutral language templates.

    The templates intentionally mention semantic attributes and relations;
    they do not encode production routing decisions.
    """
    subject = frame.entity_id
    prop = frame.requested_property.replace("_", " ")
    if frame.relation_depth:
        prompt = f"what {prop} is associated with {subject} through {frame.relation.lower().replace('_', ' ')}"
    elif frame.intent in {"CHANGE", "REPAIR", "INSTALL", "START", "STOP", "RESTART", "ROLLBACK"}:
        prompt = f"{frame.intent.lower()} {subject}"
    elif frame.intent == "CONTINUE":
        prompt = f"continue work for {subject}"
    else:
        prompt = f"{frame.intent.lower()} {prop} for {subject}"
    return {
        "family": "semantic_frame", "domain": frame.expected_domain,
        "intent": frame.expected_action_class, "target": "reference",
        "prompts": (prompt, f"what is the {prop} of {subject}", f"{subject} {prop}"),
    }


def _registry_action_entries() -> tuple[dict[str, Any], ...]:
    """Return deterministic semantic entries for every known ActionSpec."""
    from src.capability_registry import CAPABILITY_REGISTRY

    # ``writes`` is not the only signal for an operational ActionSpec:
    # workspace execution and network plans carry effects without using the
    # private-state write flag. Keep this evaluator-side classification
    # aligned with the registry's authority semantics so generated oracle
    # cases do not call an effectful Action a READ merely because its wording
    # happens to be generic.
    non_read_effects = {
        "admin_change", "execute_code", "external_network",
        "external_side_effect", "network_egress", "network_plan",
        "write_private", "write_workspace",
    }
    entries = []
    for capability_id, capability in CAPABILITY_REGISTRY.items():
        for action_id, action in capability.actions.items():
            if not action.known:
                continue
            read_only = not action.writes and not set(action.effects).intersection(non_read_effects)
            operation = "READ" if read_only else "EXECUTE"
            entries.append({
                "capability_id": capability_id, "action_id": action_id,
                "domain": _CAPABILITY_DOMAIN_HINTS.get(capability_id, "UNKNOWN"),
                "operation": operation, "executor": action.executor_key or "none",
                "approval": action.approval.value.upper(),
            })
    return tuple(entries)


def _render_generated_prompt(archetype: Mapping[str, Any], rng: random.Random, *, form: str | None = None) -> str:
    values = {
        "asset": rng.choice(_ASSET_NAMES), "reference": "that server", "ordinal": rng.choice(_ORDINALS),
        "service": rng.choice(_SERVICES), "subnet": rng.choice(_SUBNETS), "model": rng.choice(_MODELS),
        "security_target": rng.choice(("192.168.10.0/24", "the authorized lab", "an Internet host")),
        "company": rng.choice(_COMPANIES), "item": rng.choice(_ITEMS),
    }
    text = rng.choice(tuple(archetype["prompts"])).format(**values)
    form = form or rng.choice(_FORMS)
    if form == "TYPO":
        text = text.replace("the", "te", 1).replace("what", "wat", 1)
    elif form == "PROFANITY":
        text = "hey, " + text + ", please"
    elif form == "CASUAL":
        text = "yo " + text + " rn"
    elif form == "TECHNICAL":
        text = text + " and return the current verified state"
    elif form == "FRAGMENT":
        text = text.replace("what ", "").replace("show ", "")
    elif form == "AMBIGUOUS" and archetype["target"] in {"reference", "service"}:
        text = text.replace(values.get("service", "never"), "it").replace("that server", "it")
    elif form == "PRONOUN" and archetype["target"] in {"asset", "service", "reference"}:
        text = text.replace(values.get("asset", "never"), "it").replace(values.get("service", "never"), "it")
        text = text.replace("that server", "it")
    elif form == "ORDINAL" and archetype["target"] in {"asset", "reference"}:
        text = f"show me the {rng.choice(_ORDINALS)} one"
    elif form == "SELF_CORRECTION":
        text = f"{text} — actually, just use the current verified state"
    elif form == "DOMAIN_SWITCH":
        text = f"switching back to this: {text}"
    elif form == "MULTI_INTENT":
        text = f"{text}, and summarize the relevant changes"
    if rng.random() < 0.45:
        text = text.capitalize()
    if rng.random() < 0.35:
        text = text + rng.choice((".", "?", "!", "", "  "))
    return text


def generate_semantic_cases(*, seed: int = 0, count: int = 1000, split: str = "generated") -> list[dict[str, Any]]:
    """Generate reproducible semantic scenarios with pairwise dimensions.

    This intentionally samples dimensions across archetypes instead of taking
    their full Cartesian product.  The generated case contains the semantic
    oracle, so a wording mutation cannot silently redefine expected behavior.
    """
    rng = random.Random(int(seed))
    registry_entries = _registry_action_entries()
    frame_cases = generate_scenario_frames(seed=seed + 65537, count=max(1, int(count)))
    result: list[dict[str, Any]] = []
    for index in range(max(0, int(count))):
        registry_entry = registry_entries[index] if index < len(registry_entries) else None
        if registry_entry:
            readable_action = registry_entry["action_id"].replace("_", " ")
            domain_label = registry_entry["domain"].replace("_", " ").casefold()
            operation = registry_entry["operation"]
            if operation == "READ":
                prompts = (
                    f"show my {domain_label} {readable_action} information",
                    f"what is the current {readable_action} for my {domain_label}",
                    f"look up {readable_action} in my {domain_label} state",
                )
            else:
                prompts = (
                    f"perform the {readable_action} operation for my {domain_label}",
                    f"I need to {readable_action} in my {domain_label}",
                    f"execute {readable_action} against my {domain_label} target",
                )
            archetype = {
                "family": "registry_action", "domain": registry_entry["domain"],
                "intent": operation, "target": "capability", "prompts": prompts,
            }
            base_frame = None
        else:
            semantic_index = index - len(registry_entries)
            # Reserve one deterministic pass for the hand-authored semantic
            # families before sampling the broader ScenarioFrame universe.
            # This keeps product domains such as Kitchen, Finance, and
            # Background Work represented even when their current registry
            # surface is intentionally thin; the archetype is still only a
            # test oracle and never production routing logic.
            if semantic_index < len(_SCENARIO_ARCHETYPES):
                archetype = dict(_SCENARIO_ARCHETYPES[semantic_index])
                base_frame = None
            else:
                base_frame = frame_cases[semantic_index % len(frame_cases)]
                archetype = _frame_archetype(base_frame)
        # Rotating the archetype while independently sampling dimensions gives
        # deterministic pairwise/3-way coverage without an explosive product.
        state = _STATES[index % len(_STATES)] if index < len(_STATES) else rng.choice(_STATES)
        authority = _AUTHORITIES[(index // len(_STATES)) % len(_AUTHORITIES)] if index < len(_STATES) * len(_AUTHORITIES) else rng.choice(_AUTHORITIES)
        # Cycle each dimension at least once before adding random pairings.
        # This keeps large runs combinatorial rather than Cartesian while
        # making coverage reproducible and preventing a lucky seed from
        # silently omitting a required form/result class.
        execution_result = _RESULTS[index % len(_RESULTS)] if index < len(_RESULTS) * 2 else rng.choice(_RESULTS)
        form = _FORMS[index % len(_FORMS)] if index < len(_FORMS) * 2 else rng.choice(_FORMS)
        reference_type = (
            base_frame.expected_reference_resolution.casefold() if base_frame else (
                _REFERENCE_TYPES[index % len(_REFERENCE_TYPES)]
                if archetype["target"] in {"asset", "reference", "service", "container"}
                else ("none" if archetype["target"] in {"none", "capability", "owner"} else "named")
            )
        )
        if registry_entry:
            # Registry-action cases are primarily action-identity probes.
            # Keep their semantic frame coherent with the transport world:
            # supported reads have a successful canonical result, while a
            # registry action without a synthetic transport is an explicit
            # capability gap. Do not pair a read prompt with a random
            # verification-failure oracle that the fixture cannot produce.
            fixture_tool = (
                _SYNTHETIC_TOOL_FOR_CAPABILITY.get(registry_entry["capability_id"])
                or _SYNTHETIC_TOOL_FOR_EXECUTOR.get(registry_entry["executor"])
            )
            if registry_entry["operation"] == "READ" and fixture_tool:
                authority = "READ_ALLOWED"
                execution_result = "SUCCESS"
            elif not fixture_tool:
                execution_result = "CAPABILITY_UNAVAILABLE"

        frame = base_frame or _build_scenario_frame(
            index=index, rng=rng, archetype=archetype, state=state,
            authority=authority, execution_result=execution_result,
            reference_type=reference_type, domain=archetype["domain"],
            intent=archetype["intent"], action_class=archetype["intent"],
        )
        if base_frame:
            state = str(frame.initial_world_state.get("condition") or state)
            authority = frame.expected_authority
            execution_result = frame.expected_result_state
        scenario = {
            "intent": archetype["intent"], "domain": archetype["domain"],
            "target_type": archetype["target"], "state": state,
            "authority": authority, "conversation_form": form,
            "execution_result": execution_result,
            "authority_state": authority,
            "reference_type": reference_type,
            "cross_domain_pair": _CROSS_DOMAIN_PAIRS[index % len(_CROSS_DOMAIN_PAIRS)],
            "failure_injection": _FAILURE_TAXONOMY[index % len(_FAILURE_TAXONOMY)],
            "negative_near_miss": archetype["family"] == "unknown_near_miss",
            "scenario_frame": frame.to_dict(),
            "language_transform_chain": [_LANGUAGE_TRANSFORMS[index % len(_LANGUAGE_TRANSFORMS)], form.casefold()],
        }
        scenario.update({
            "entity_type": frame.entity_type, "entity_id": frame.entity_id,
            "related_entities": frame.related_entities, "requested_property": frame.requested_property,
            "relation": frame.relation, "relation_depth": frame.relation_depth,
            "temporal_scope": frame.temporal_scope, "epistemic_state": frame.epistemic_state,
            "secondary_domains": frame.secondary_domains,
            "expected_reference_resolution": frame.expected_reference_resolution,
            "execution_required": frame.execution_required, "approval_state": frame.approval_state,
            "expected_result_state": frame.expected_result_state,
            "expected_completion_state": frame.expected_completion_state,
            "network_scope": frame.network_scope,
            "address_state": frame.address_state,
            "asset_identity_strength": frame.asset_identity_strength,
        })
        capability_action = _CAPABILITY_FOR_FAMILY.get(archetype["family"])
        if registry_entry:
            scenario["capability_id"] = registry_entry["capability_id"]
            scenario["action_id"] = registry_entry["action_id"]
            scenario["action_spec"] = f'{registry_entry["capability_id"]}:{registry_entry["action_id"]}'
            scenario["executor"] = registry_entry["executor"]
            scenario["approval"] = registry_entry["approval"]
            # A registry ActionSpec may intentionally have no first-class
            # ToolBinding yet (for example workspace_yolo or a provider
            # adapter). Keep it in coverage, but do not fabricate a
            # read-only fixture that makes the unsupported action appear
            # executable. Unsupported cases are graded as fail-closed below.
            scenario["synthetic_capability_available"] = bool(
                _generated_fixture_environment(scenario)
                .get("fixture_profile", {}).get("tools")
            )
            capability_action = None
        if capability_action:
            scenario["capability_id"], scenario["action_id"] = capability_action
            scenario["action_spec"] = f"{capability_action[0]}:{capability_action[1]}"
            try:
                from src.capability_registry import capability_for_id
                action = capability_for_id(capability_action[0]).actions.get(capability_action[1])
                scenario["executor"] = action.executor_key if action and action.executor_key else "none"
                scenario["approval"] = action.approval.value.upper() if action else "UNKNOWN"
            except Exception:
                scenario["executor"] = "unknown"
                scenario["approval"] = "UNKNOWN"
        scenario["policy"] = {
            "READ_ALLOWED": "ALLOW", "MUTATION_ALLOWED": "ALLOW", "APPROVAL_REQUIRED": "REQUIRES_APPROVAL",
            "APPROVAL_GRANTED": "ALLOW", "APPROVAL_STALE": "STALE", "OUT_OF_SCOPE": "OUT_OF_SCOPE",
            "UNKNOWN_SCOPE": "UNKNOWN", "BLOCKED": "DENY", "DISABLED": "DENY",
        }.get(authority, "UNKNOWN")
        scenario["post_result_state"] = {
            "SUCCESS": "COMPLETE_AFTER_ANSWER", "FAILURE": "BLOCKED", "TIMEOUT": "BLOCKED",
            "PARTIAL": "NEEDS_BOUNDED_REASONING", "STALE_PRECONDITION": "BLOCKED",
            "VERIFICATION_FAILURE": "BLOCKED", "DEPENDENCY_MISSING": "NEEDS_CONTEXT",
            "CAPABILITY_UNAVAILABLE": "BLOCKED",
        }[execution_result]
        scenario["model_profile"] = _MODEL_PROFILES[index % len(_MODEL_PROFILES)]
        scenario["verification_result"] = {
            "SUCCESS": "VERIFIED", "FAILURE": "FAILED", "TIMEOUT": "FAILED",
            "PARTIAL": "PARTIAL", "STALE_PRECONDITION": "FAILED",
            "VERIFICATION_FAILURE": "FAILED", "DEPENDENCY_MISSING": "NOT_RUN",
            "CAPABILITY_UNAVAILABLE": "NOT_RUN",
        }[execution_result]
        scenario["grounding"] = "CURRENT_ACTION_RESULT" if execution_result == "SUCCESS" else "CANONICAL_CONTEXT"
        scenario["side_effect_boundary"] = "NO_SIDE_EFFECT" if archetype["intent"] == "READ" else (
            "APPROVAL_BOUND" if authority in {"APPROVAL_REQUIRED", "APPROVAL_GRANTED", "APPROVAL_STALE"}
            else "POLICY_BOUND"
        )
        scenario["failure_class"] = {
            "FAILURE": "EXECUTION_FAILURE", "TIMEOUT": "EXECUTION_FAILURE", "PARTIAL": "VERIFICATION_FAILURE",
            "STALE_PRECONDITION": "STATE_PERSISTENCE_FAILURE", "VERIFICATION_FAILURE": "VERIFICATION_FAILURE",
            "DEPENDENCY_MISSING": "DEPENDENCY_FAILURE", "CAPABILITY_UNAVAILABLE": "CAPABILITY_GAP",
        }.get(execution_result, "")
        prompt = _render_generated_prompt(archetype, rng, form=form)
        expected = {
            "concept": archetype["domain"], "operation": archetype["intent"],
            "semantic_case": True,
            "negative_near_miss": scenario["negative_near_miss"],
            "max_tool_index_lookups": 0,
            "semantic_oracle": {
                "initial_state": scenario["state"],
                "user_intent": scenario["intent"],
                "expected_domain": scenario["domain"],
                "expected_entity": scenario["target_type"],
                "expected_authority": scenario["authority"],
                "expected_action_class": scenario["intent"],
                "expected_completion": scenario["post_result_state"],
                "expected_grounding": scenario["grounding"],
                "expected_side_effect_boundary": scenario["side_effect_boundary"],
                "scenario_frame": frame.to_dict(),
            },
        }
        if registry_entry and not scenario.get("synthetic_capability_available", False):
            expected["capability_available"] = False
        if archetype["intent"] == "READ":
            expected["max_decision_calls"] = 0
        if archetype["intent"] == "EXECUTE" and authority in {"OUT_OF_SCOPE", "UNKNOWN_SCOPE", "APPROVAL_STALE", "BLOCKED"}:
            expected["must_refuse"] = True
        result.append(_case(
            f"generated-{int(seed)}-{index:05d}", prompt,
            family=archetype["family"], source="generated_semantic", split=split,
            expected=expected, scenario=scenario,
            fixture_id=f"fixture-{int(seed)}-{index:05d}",
            environment=_generated_fixture_environment(scenario),
        ) | {"seed": int(seed), "variant_id": f"variant-{index:05d}"})
    return result


_METAMORPHIC_TRANSFORMS = (
    ("CASE", lambda text: text.casefold()),
    ("PUNCTUATION", lambda text: re.sub(r"[.!?]+$", "", text).strip() + "?"),
    ("WHITESPACE", lambda text: re.sub(r"\s+", "  ", text).strip()),
    ("POLITENESS", lambda text: "please " + text),
    ("CASUAL", lambda text: "hey, " + text + " rn"),
    ("TECHNICAL", lambda text: text + " and report only verified current state"),
    ("FILLER", lambda text: "uh, " + text),
    ("PROFANITY", lambda text: "what the hell, " + text),
    ("TYPO", lambda text: text.replace("what", "wat", 1).replace("the", "teh", 1)),
    ("ASR", lambda text: re.sub(r"[^A-Za-z0-9:/? -]", "", text).casefold()),
    ("NOVICE", lambda text: text + " in simple words"),
    ("EXPERT", lambda text: text + " from canonical current state"),
    ("SYSADMIN", lambda text: text + " with observed evidence only"),
    ("FRAGMENT", lambda text: text.removeprefix("what ").removeprefix("show ").strip()),
    ("RUN_ON", lambda text: text + " and tell me the relevant result"),
    ("SELF_CORRECTION", lambda text: text + " — I mean the current verified one"),
    ("REDUNDANCY", lambda text: text + " please, just this one request"),
    ("LOWERCASE", lambda text: text.casefold()),
    ("CAPITALIZATION", lambda text: text.upper()),
)

_MINIMAL_PAIRS = (
    ("network_concept", "What is a network?", "What network am I on?", "UNKNOWN", "ANSWER", "NETWORK", "READ"),
    ("networking_concept", "Explain networking.", "Explain my network.", "UNKNOWN", "ANSWER", "NETWORK", "READ"),
    ("raid_concept", "What is RAID 10?", "What RAID do I have?", "UNKNOWN", "ANSWER", "STORAGE", "READ"),
    ("gpu_concept", "What is a GPU?", "What GPUs do I own?", "UNKNOWN", "ANSWER", "TECHNICAL_ASSET", "READ"),
    ("docker_concept", "How does Docker work?", "What's running in Docker?", "UNKNOWN", "ANSWER", "CONTAINER", "READ"),
    ("dns_concept", "What is DNS?", "What DNS am I using?", "UNKNOWN", "ANSWER", "NETWORK", "READ"),
    ("restart_explanation", "How do I restart Jellyfin?", "Restart Jellyfin.", "SERVICE", "ANSWER", "SERVICE", "EXECUTE"),
    ("scan_explanation", "What is a network scan?", "Scan my current network.", "NETWORK", "ANSWER", "NETWORK", "EXECUTE"),
    ("package_explanation", "What package contains smartctl?", "Install smartmontools.", "DEPENDENCY", "ANSWER", "DEPENDENCY", "EXECUTE"),
)


def generate_minimal_pair_cases(*, seed: int = 0, count: int = 0, split: str = "generated") -> list[dict[str, Any]]:
    """Generate semantic minimal pairs whose small wording change changes operation.

    The pair oracle is explicit: the left side is conceptual/informational and
    must not execute; the right side may select the bounded operational path.
    This is intentionally separate from keyword routing in production.
    """
    if count <= 0:
        return []
    cases: list[dict[str, Any]] = []
    for index in range(int(count)):
        pair_id, conceptual, operational, domain_left, op_left, domain_right, op_right = _MINIMAL_PAIRS[index % len(_MINIMAL_PAIRS)]
        pair_seed = int(seed) + index
        for side, prompt, domain, operation, must_not_execute in (
            ("conceptual", conceptual, domain_left, op_left, True),
            ("operational", operational, domain_right, op_right, False),
        ):
            frame = ScenarioFrame(
                entity_type="NETWORK" if domain_right == "NETWORK" else "SERVICE" if domain_right == "SERVICE" else "ASSET",
                entity_id="minimal-pair",
                related_entities=(), intent=operation, requested_property="identity",
                relation="ASSOCIATED_WITH", relation_depth=0, temporal_scope="CURRENT",
                epistemic_state="UNKNOWN", expected_domain=domain,
                secondary_domains=(), expected_reference_resolution="EXACT_NAME",
                expected_authority="READ_ALLOWED" if must_not_execute else "UNKNOWN_SCOPE",
                expected_action_class=operation, execution_required=not must_not_execute,
                approval_state="NONE" if must_not_execute else "REQUIRED",
                initial_world_state={"condition": "UNKNOWN", "pair": pair_id},
                expected_result_state="UNKNOWN" if must_not_execute else "BLOCKED",
                expected_completion_state="ANSWER" if must_not_execute else "BLOCKED",
                expected_grounding="MODEL_KNOWLEDGE" if must_not_execute else "CANONICAL_CONTEXT",
            )
            scenario = {
                "semantic_case": True, "minimal_pair": True, "pair_id": pair_id,
                "pair_side": side, "must_not_execute": must_not_execute,
                "negative_near_miss": must_not_execute, "intent": operation,
                "domain": domain, "authority": frame.expected_authority,
                "operation": operation, "conversation_form": "DIRECT",
                "execution_result": "CAPABILITY_UNAVAILABLE" if must_not_execute else "SUCCESS",
                "scenario_frame": frame.to_dict(),
                "language_transform_chain": ["minimal_pair", side],
            }
            expected = {
                "concept": domain, "operation": operation,
                "semantic_case": True, "minimal_pair": True,
                "pair_id": pair_id, "pair_side": side,
                "max_tool_index_lookups": 0,
                "max_tool_calls": 0 if must_not_execute else None,
                "semantic_oracle": {
                    "expected_domain": domain, "expected_action_class": operation,
                    "expected_side_effect_boundary": "NO_SIDE_EFFECT" if must_not_execute else "POLICY_BOUND",
                    "scenario_frame": frame.to_dict(),
                },
            }
            cases.append(_case(
                f"minimal-pair-{pair_seed:05d}-{pair_id}-{side}", prompt,
                family="minimal_pair", source="generated_minimal_pair", split=split,
                expected=expected, scenario=scenario,
                fixture_id=f"minimal-pair-fixture-{pair_seed:05d}",
            ) | {"seed": pair_seed, "variant_id": f"{pair_id}-{side}"})
    return cases


def generate_metamorphic_cases(*, seed: int = 0, count: int = 250, split: str = "generated") -> list[dict[str, Any]]:
    """Generate equivalent phrasings with an explicit semantic invariant.

    The base case owns the oracle.  A transform may alter surface wording, but
    it is not allowed to alter the expected domain, intent, authority, or
    action class.  This catches phrase-specific routing without making the
    production router aware of these strings.
    """
    bases = generate_semantic_cases(seed=seed, count=count, split=split)
    variants: list[dict[str, Any]] = []
    for index, base in enumerate(bases):
        kind, transform = _METAMORPHIC_TRANSFORMS[index % len(_METAMORPHIC_TRANSFORMS)]
        variant = dict(base)
        variant["id"] = f"metamorphic-{int(seed)}-{index:05d}-{kind.casefold()}"
        variant["prompt"] = transform(str(base["prompt"]))
        variant["source"] = "generated_metamorphic"
        variant["variant_id"] = f"metamorphic-{kind.casefold()}-{index:05d}"
        scenario = dict(base.get("scenario") or {})
        scenario.update({
            "metamorphic_group": base["id"],
            "metamorphic_transform": kind,
            "metamorphic_invariants": ("domain", "intent", "authority", "action_class"),
            "language_transform_chain": list(scenario.get("language_transform_chain") or ()) + [kind.casefold()],
        })
        variant["scenario"] = scenario
        expected = dict(base.get("expected") or {})
        expected["metamorphic"] = True
        expected["metamorphic_invariants"] = list(scenario["metamorphic_invariants"])
        variant["expected"] = expected
        variants.append(variant)
    return variants


def generate_hidden_holdout_cases(*, seed: int = 0, count: int = 500) -> list[dict[str, Any]]:
    """Generate oracle-bearing holdout cases without retaining literal prompts.

    The case is executable through the normal runner, but the resulting report
    contains only the prompt digest and ScenarioFrame metadata. A fixed seed
    reproduces the same hidden wording for an authorized replay without making
    the holdout a visible phrase corpus.
    """
    bases = generate_semantic_cases(seed=seed + 104729, count=count, split="held_out")
    rng = random.Random(int(seed) + 161803)
    cases: list[dict[str, Any]] = []
    for index, base in enumerate(bases):
        transform_names = rng.sample(
            list(_METAMORPHIC_TRANSFORMS),
            k=2,
        )
        prompt = str(base["prompt"])
        for _name, transform in transform_names:
            prompt = transform(prompt)
        case = dict(base)
        case.update({
            "id": f"hidden-holdout-{int(seed)}-{index:05d}",
            "prompt": prompt,
            "source": "generated_hidden_holdout",
            "split": "held_out",
            "variant_id": f"hidden-{index:05d}",
        })
        scenario = dict(base.get("scenario") or {})
        scenario.update({
            "hidden_holdout": True,
            "metamorphic_transform": "+".join(name for name, _ in transform_names),
            "language_transform_chain": list(scenario.get("language_transform_chain") or ()) + [
                name.casefold() for name, _ in transform_names
            ],
        })
        case["scenario"] = scenario
        expected = dict(base.get("expected") or {})
        expected["hidden_holdout"] = True
        case["expected"] = expected
        cases.append(case)
    return cases


def generate_negative_near_miss_cases(*, seed: int = 0, count: int = 250, split: str = "generated") -> list[dict[str, Any]]:
    """Generate informational near-misses that must not execute a capability."""
    bases = generate_semantic_cases(seed=seed + 7919, count=count, split=split)
    cases: list[dict[str, Any]] = []
    for index, base in enumerate(bases):
        prompt = str(base["prompt"])
        prompt = re.sub(r"\b(?:scan|discover|restart|repair|execute|install)\b", "explain", prompt, flags=re.IGNORECASE)
        prompt = "what does it mean to " + prompt.removeprefix("what does it mean to ")
        case = dict(base)
        case["id"] = f"near-miss-{int(seed)}-{index:05d}"
        case["prompt"] = prompt
        case["source"] = "generated_negative_near_miss"
        case["variant_id"] = f"near-miss-{index:05d}"
        scenario = dict(base.get("scenario") or {})
        scenario.update({
            "negative_near_miss": True,
            "must_not_execute": True,
            "near_miss_of": base["id"],
        })
        case["scenario"] = scenario
        expected = dict(base.get("expected") or {})
        expected.update({
            "negative_near_miss": True,
            "max_tool_calls": 0,
            "max_decision_calls": 0,
            "max_tool_index_lookups": 0,
        })
        # A near-miss can still be answered as an informational question; it
        # must not inherit an execution oracle from its positive base case.
        expected.pop("must_refuse", None)
        expected["operation"] = "READ"
        oracle = dict(expected.get("semantic_oracle") or {})
        oracle["user_intent"] = "EXPLAIN"
        oracle["expected_action_class"] = "EXPLAIN"
        expected["semantic_oracle"] = oracle
        scenario["intent"] = "EXPLAIN"
        scenario["side_effect_boundary"] = "NO_SIDE_EFFECT"
        scenario["failure_class"] = ""
        case["scenario"] = scenario
        case["expected"] = expected
        cases.append(case)
    return cases


_CHAOS_JOURNEYS = (
    (
        ("what network am i on right now", "NETWORK", "READ", "none"),
        ("which of my servers are on it", "TECHNICAL_ASSET", "READ", "conversational"),
        ("scan it", "NETWORK", "EXECUTE", "pronoun"),
        ("actually do not scan Thanatos, just tell me what we already know", "NETWORK", "READ", "self_correction"),
    ),
    (
        ("tell me about Thanatos", "TECHNICAL_ASSET", "READ", "named"),
        ("what is running there", "SERVICE", "READ", "pronoun"),
        ("restart the web service and verify it", "SERVICE", "EXECUTE", "named"),
        ("wait, which service did you mean", "SERVICE", "CLARIFY", "ambiguous"),
        ("the WordPress one, do it", "SERVICE", "EXECUTE", "conversational"),
    ),
    (
        ("what model are you using", "MODEL_RUNTIME", "READ", "none"),
        ("is Ollama healthy", "MODEL_RUNTIME", "READ", "named"),
        ("why is qwen slow", "MODEL_RUNTIME", "READ", "named"),
        ("check GPU usage", "HOMELAB_HOST", "READ", "named"),
        ("switch back to qwen after", "MODEL_RUNTIME", "CONTINUE", "conversational"),
    ),
    (
        ("restart Jellyfin", "SERVICE", "EXECUTE", "named"),
        ("why did that fail", "SERVICE", "READ", "conversational"),
        ("fix it", "SERVICE", "EXECUTE", "pronoun"),
        ("make sure it actually came back", "SERVICE", "VERIFY", "pronoun"),
    ),
)


def generate_chaos_journeys(*, seed: int = 0, count: int = 50, split: str = "generated") -> list[dict[str, Any]]:
    """Generate bounded 2–20-turn journeys over the existing runner seam."""
    rng = random.Random(int(seed) + 104729)
    cases: list[dict[str, Any]] = []
    for journey_index in range(max(0, int(count))):
        template = _CHAOS_JOURNEYS[journey_index % len(_CHAOS_JOURNEYS)]
        journey_id = f"generated-chaos-{int(seed)}-{journey_index:04d}"
        turns = list(template)
        if journey_index % 5 == 0:
            turns.insert(1, ("sorry, I meant the second server", "TECHNICAL_ASSET", "CLARIFY", "self_correction"))
        if journey_index % 7 == 0:
            turns.append(("what changed since yesterday", "WORK", "READ", "domain_switch"))
        if journey_index % 11 == 0:
            turns.append(("show me the current verified state", "SELFSTATE", "READ", "technical"))
        state_mutation = _STATE_MUTATIONS[journey_index % len(_STATE_MUTATIONS)]
        for turn_index, (prompt, domain, intent, reference_type) in enumerate(turns, 1):
            result = "FAILURE" if "fail" in prompt or prompt == "fix it" else "SUCCESS"
            # A journey turn is an oracle in its own right.  Keep the
            # conversational template as a projection, but attach the same
            # semantic frame used by single-turn generation so reference,
            # epistemic, mutation, and completion assertions can be graded at
            # trace level rather than inferred from prompt text.
            frame_entity = {
                "MEMORY": "PERSON", "TECHNICAL_ASSET": "ASSET",
                "NETWORK": "NETWORK", "SERVICE": "SERVICE",
                "MODEL_RUNTIME": "MODEL", "HOMELAB_HOST": "HOST",
                "WORK": "PROJECT", "SELFSTATE": "INTEGRATION",
            }.get(domain, "ASSET")
            frame_intent = intent if intent in _SEMANTIC_INTENTS else "READ"
            reference_strategy = {
                "none": "DEICTIC",
                "named": "EXACT_NAME",
                "pronoun": "PRONOUN",
                "ordinal": "ORDINAL",
                "conversational": "RECENT_REFERENT",
                "self_correction": "SELF_CORRECTION",
                "stale": "OLDER_REFERENT",
                "ambiguous": "MULTIPLE_MATCHES",
                "conflicting": "MULTIPLE_MATCHES",
            }.get(reference_type, "EXACT_NAME")
            frame = ScenarioFrame(
                entity_type=frame_entity,
                entity_id=_semantic_entity_id(frame_entity, journey_index),
                related_entities=(),
                intent=frame_intent,
                requested_property="current_state",
                relation="ASSOCIATED_WITH",
                relation_depth=0,
                temporal_scope="CURRENT" if turn_index == 1 else "LATEST_OBSERVED",
                epistemic_state="OBSERVED" if turn_index > 1 else "UNKNOWN",
                expected_domain=domain,
                secondary_domains=(),
                expected_reference_resolution=reference_strategy,
                expected_authority="APPROVAL_REQUIRED" if intent in {"EXECUTE", "REPAIR"} else "READ_ALLOWED",
                expected_action_class=intent,
                execution_required=intent in {"EXECUTE", "REPAIR"},
                approval_state="REQUIRED" if intent in {"EXECUTE", "REPAIR"} else "NONE",
                initial_world_state={
                    "condition": "FAILED" if result == "FAILURE" else "CHANGING",
                    "mutation": state_mutation if turn_index > 1 else "NONE",
                },
                expected_result_state=result,
                expected_completion_state="BLOCKED" if result == "FAILURE" else "COMPLETE_AFTER_ANSWER",
                expected_grounding="CURRENT_ACTION_RESULT" if result == "SUCCESS" else "CANONICAL_CONTEXT",
            )
            scenario = {
                "intent": intent, "domain": domain, "target_type": "reference" if reference_type != "none" else "none",
                "state": "FAILED" if result == "FAILURE" else "CHANGING",
                "authority": "APPROVAL_REQUIRED" if intent in {"EXECUTE", "REPAIR"} else "READ_ALLOWED",
                "conversation_form": reference_type.upper(), "execution_result": result,
                "reference_type": reference_type, "journey_length": len(turns),
                "failure_class": "EXECUTION_FAILURE" if result == "FAILURE" else "",
                "state_mutation": state_mutation if turn_index > 1 else "NONE",
                "mutation_boundary": "BEFORE_TURN" if turn_index > 1 and state_mutation != "NONE" else "NONE",
                "conversation_state": "FRESH" if turn_index == 1 else "CONTINUING",
                "scenario_frame": frame.to_dict(),
                "semantic_oracle": {
                    "expected_domain": domain, "expected_action_class": intent,
                    "expected_reference_type": reference_type,
                    "scenario_frame": frame.to_dict(),
                },
            }
            expected = {
                "concept": domain, "operation": intent if intent in {"READ", "EXECUTE", "RESEARCH", "CONTINUE"} else None,
                "semantic_case": True, "journey_turn": turn_index,
                "max_tool_index_lookups": 0,
                "state_mutation": state_mutation if turn_index > 1 else "NONE",
                "semantic_oracle": {
                    "expected_domain": domain,
                    "expected_action_class": intent,
                    "expected_reference_type": reference_type,
                    "scenario_frame": frame.to_dict(),
                },
            }
            if intent in {"READ", "CLARIFY"}:
                expected["max_decision_calls"] = 1
            cases.append(_case(
                f"{journey_id}-{turn_index:02d}", prompt, family="generated_chaos",
                source="generated_chaos", split=split, journey=journey_id,
                expected=expected, scenario=scenario,
                fixture_id=f"fixture-{journey_id}",
            ) | {"seed": int(seed), "variant_id": f"{journey_id}-turn-{turn_index:02d}"})
    return cases


def shard_cases(cases: Iterable[Mapping[str, Any]], *, shard_index: int = 0, shard_count: int = 1) -> list[dict[str, Any]]:
    count = max(1, int(shard_count))
    index = int(shard_index)
    if index < 0 or index >= count:
        raise ValueError("shard_index must be within shard_count")
    return [dict(case) for position, case in enumerate(cases) if position % count == index]


def load_regression_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load previously captured synthetic failures as permanent test cases."""
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    cases = []
    for item in payload.get("cases", []) if isinstance(payload, Mapping) else []:
        if not isinstance(item, Mapping) or not str(item.get("prompt") or "").strip():
            # Live runs intentionally have no retained owner prompt and cannot
            # become replayable text fixtures.
            continue
        prompts = [(str(item["prompt"]), "original")]
        prompts.extend(
            (str(variant.get("prompt")), str(variant.get("kind") or "variant"))
            for variant in item.get("variants", [])
            if isinstance(variant, Mapping) and str(variant.get("prompt") or "").strip()
        )
        for prompt, variant_kind in prompts:
            case_id = str(item.get("id") or f"regression-{digest(item.get('prompt'))}")
            if variant_kind != "original":
                case_id = f"{case_id}-{variant_kind.casefold()}"
            case = _case(
                case_id, prompt, family=str(item.get("family") or "regression"),
                source="failure_regression", expected=item.get("expected"),
                scenario=item.get("scenario"), fixture_id=item.get("fixture_id"),
            )
            case.update({
                "seed": item.get("seed"), "variant_id": item.get("variant_id") or variant_kind,
                "run_id": item.get("run_id"),
                "run_metadata": dict(item.get("run_metadata") or {}),
            })
            cases.append(case)
    return cases


def _semantic_regression_variants(prompt: str) -> list[dict[str, str]]:
    """Create bounded, reproducible evaluator variants for synthetic failures."""
    text = str(prompt or "").strip()
    if not text:
        return []
    candidates = (
        ("CASE", text.casefold()),
        ("PUNCTUATION", re.sub(r"[.!?]+$", "", text) + "?"),
        ("WHITESPACE", re.sub(r"\s+", "  ", text)),
        ("POLITENESS", "please " + text),
        ("CASUAL", "hey, " + text),
    )
    variants = []
    seen = {text}
    for kind, value in candidates:
        value = value.strip()
        if value and value not in seen:
            variants.append({"kind": kind, "prompt": value})
            seen.add(value)
    return variants


def _import_symbol(spec: Mapping[str, Any]) -> Any:
    return getattr(importlib.import_module(str(spec["module"])), str(spec["symbol"]))


def expand_cases(
    contract: Mapping[str, Any], *, suite: str = "baseline", generated_count: int = 0,
    seed: int = 0, shard_index: int = 0, shard_count: int = 1,
    regressions_path: str | Path | None = None,
    metamorphic_count: int = 0, negative_count: int = 0,
    chaos_journey_count: int = 0, minimal_pair_count: int = 0,
    hidden_holdout_count: int = 0,
) -> list[dict[str, Any]]:
    """Expand all selected sources into one stable scenario list."""
    if suite not in {"baseline", "all", "security", "held_out"}:
        raise ValueError(f"unknown dogfood suite: {suite}")
    cases: list[dict[str, Any]] = []
    for frozen in contract["frozen_failures"]:
        if suite == "held_out":
            continue
        for index, prompt in enumerate(frozen["prompts"], 1):
            expected = dict(frozen.get("expected") or {})
            expected.setdefault("concept", frozen.get("domain"))
            cases.append(_case(f"{frozen['id']}-{index:02d}", prompt, family=frozen["family"],
                               source="frozen_failure", expected=expected))

    for spec in contract["imports"]:
        if suite == "baseline" and not spec.get("baseline"):
            continue
        if suite == "security" and spec.get("id") not in {"jarvis_control_plane"}:
            continue
        if spec["kind"] == "json":
            payload = json.loads((ROOT / str(spec["path"])).read_text(encoding="utf-8"))
            values = payload.get("cases", [])
        else:
            values = _import_symbol(spec)
        adapter = spec.get("adapter")
        if adapter == "aci_corpus":
            values = [item for item in values if suite != "baseline" or item.get("canary")]
            for item in values:
                reference_expectation = (
                    "UNRESOLVED" if item.get("category") in {"ambiguity", "references"} else None
                )
                cases.append(_case(f"aci-{item['id']}", item["prompt"], family=item["category"],
                                   source=spec["id"], split=item.get("split", "development"),
                                   expected={
                                       "trajectory": item.get("expected_trajectory", {}),
                                       **({"reference_resolution": reference_expectation} if reference_expectation else {}),
                                   },
                                   environment=item.get("environment")))
        elif adapter == "jarvis":
            for item in values:
                reference_expectation = (
                    "UNRESOLVED" if item.get("id") in {"referent-all", "referent-selection", "referent-action"} else None
                )
                cases.append(_case(f"jarvis-{item['id']}", item["prompt"], family=item["category"],
                                   source=spec["id"], expected={
                                       **dict(item.get("expected", {})),
                                       **({"reference_resolution": reference_expectation} if reference_expectation else {}),
                                   }))
        elif adapter == "metamorphic":
            for group, prompts in values.items():
                selected = prompts[:3] if suite == "baseline" else prompts
                fixture_tool = fixture_tool_for_semantic_concept(group)
                environment = (
                    {"fixture_profile": {"tools": [fixture_tool]}}
                    if fixture_tool else {}
                )
                for index, prompt in enumerate(selected, 1):
                    cases.append(_case(f"meta-{group.casefold()}-{index:02d}", prompt,
                                       family="metamorphic", source=spec["id"],
                                       expected={"concept": group, "max_decision_calls": 0,
                                                 "max_tool_index_lookups": 0},
                                       environment=environment))
        elif adapter == "live_case":
            for item in values:
                data = item.__dict__ if hasattr(item, "__dict__") else dict(item)
                cases.append(_case(f"live-{data['name']}", data["prompt"], family=data.get("family", "golden"),
                                   source=spec["id"], split=data.get("split", "core"),
                                   expected={"max_tool_calls": data.get("max_tools"),
                                             "max_decision_calls": data.get("expect_bounded_decisions"),
                                             "max_tool_index_lookups": data.get("expect_tool_index_lookups"),
                                             "completion": data.get("expect_completion"),
                                             "fallback": data.get("expect_fallback")},
                                   environment=_live_case_fixture_environment(data)))
    if suite != "held_out":
        for journey in contract["journeys"]:
            for index, turn in enumerate(journey["turns"], 1):
                cases.append(_case(f"journey-{journey['id']}-{index:02d}", turn["prompt"],
                                   family="cross_domain", source="journey", journey=journey["id"],
                                   expected={"concept": turn["domain"], "journey_turn": index,
                                             "max_decision_calls": 1}))
    if generated_count:
        generated = generate_semantic_cases(
            seed=seed, count=generated_count,
            split="held_out" if suite == "held_out" else "generated",
        )
        if suite == "security":
            generated = [case for case in generated if case["family"] in {"security_scope", "dependency", "developer", "unknown_near_miss"}]
        cases.extend(generated)
    if metamorphic_count and suite != "security":
        cases.extend(generate_metamorphic_cases(seed=seed, count=metamorphic_count, split="held_out" if suite == "held_out" else "generated"))
    if negative_count:
        cases.extend(generate_negative_near_miss_cases(seed=seed, count=negative_count, split="held_out" if suite == "held_out" else "generated"))
    if chaos_journey_count and suite not in {"security", "held_out"}:
        cases.extend(generate_chaos_journeys(seed=seed, count=chaos_journey_count))
    if minimal_pair_count and suite != "security":
        cases.extend(generate_minimal_pair_cases(
            seed=seed, count=minimal_pair_count,
            split="held_out" if suite == "held_out" else "generated",
        ))
    if hidden_holdout_count and suite != "security":
        cases.extend(generate_hidden_holdout_cases(seed=seed, count=hidden_holdout_count))
    if regressions_path and suite != "held_out":
        cases.extend(load_regression_cases(regressions_path))
    if suite == "held_out":
        cases = [case for case in cases if case["split"] == "held_out"]
    return shard_cases(cases, shard_index=shard_index, shard_count=shard_count)


def contract_summary(contract: Mapping[str, Any], cases: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    values = list(cases)
    return {
        "contract": contract["name"], "scenario_count": len(values),
        "prompt_variant_count": len(values),
        "journey_count": len(contract["journeys"]),
        "source_counts": dict(sorted(Counter(str(c["source"]) for c in values).items())),
    }


_FAILURE_TAXONOMY = (
    "INTENT_FAILURE", "DOMAIN_ROUTING_FAILURE", "ENTITY_RESOLUTION_FAILURE",
    "REFERENCE_FAILURE", "CONTEXT_FAILURE", "GROUNDING_FAILURE",
    "CANDIDATE_RETRIEVAL_FAILURE", "SHORTLIST_FAILURE", "CAPABILITY_GAP",
    "MODEL_REASONING_FAILURE", "DECISION_PROTOCOL_FAILURE", "POLICY_BLOCK",
    "APPROVAL_FAILURE", "EXECUTION_FAILURE", "DEPENDENCY_FAILURE",
    "VERIFICATION_FAILURE", "CONTINUATION_FAILURE", "COMPLETION_FAILURE",
    "DUPLICATE_OUTPUT_FAILURE", "STATE_PERSISTENCE_FAILURE", "SECURITY_FAILURE",
    "BURDEN_REGRESSION",
)
_AUTHORITY_STATES = ("READ_ALLOWED", "MUTATION_ALLOWED", "APPROVAL_REQUIRED", "APPROVAL_GRANTED", "APPROVAL_STALE", "OUT_OF_SCOPE", "UNKNOWN_SCOPE", "BLOCKED")
_REFERENCE_TYPES = ("none", "named", "pronoun", "ordinal", "conversational", "stale", "ambiguous", "conflicting")
_CONVERSATION_FORMS = ("DIRECT", "PARAPHRASE", "FRAGMENT", "TYPO", "PROFANITY", "CASUAL", "TECHNICAL", "AMBIGUOUS", "PRONOUN", "ORDINAL", "FOLLOWUP", "SELF_CORRECTION", "DOMAIN_SWITCH", "MULTI_INTENT")
_EXECUTION_RESULTS = ("SUCCESS", "FAILURE", "TIMEOUT", "PARTIAL", "STALE_PRECONDITION", "VERIFICATION_FAILURE", "DEPENDENCY_MISSING", "CAPABILITY_UNAVAILABLE")


def _coverage_values(cases: Iterable[Mapping[str, Any]], key: str) -> set[str]:
    values: set[str] = set()
    for case in cases:
        scenario = case.get("scenario") if isinstance(case.get("scenario"), Mapping) else {}
        # Frame dimensions are intentionally stored under a separate namespace
        # so legacy scenario labels (for example operation ``READ``) cannot be
        # mistaken for the richer semantic intent (for example ``DIAGNOSE``).
        lookup_key = key.removeprefix("frame_") if key.startswith("frame_") else key
        value = scenario.get(lookup_key)
        if key.startswith("frame_"):
            frame = scenario.get("scenario_frame")
            value = frame.get(lookup_key) if isinstance(frame, Mapping) else None
        if isinstance(value, (list, tuple, set)):
            values.update(str(item) for item in value if item)
        elif value is not None and value != "":
            values.add(str(value))
    return values


def _coverage_dimension(known: Iterable[str], cases: list[Mapping[str, Any]], key: str) -> dict[str, Any]:
    known_values = {str(value) for value in known}
    covered = _coverage_values(cases, key)
    negative_cases = [case for case in cases if (case.get("scenario") or {}).get("negative_near_miss") or "security" in str(case.get("family", "")).lower()]
    failure_cases = [case for case in cases if (case.get("scenario") or {}).get("execution_result") not in {None, "SUCCESS"}]
    multi_cases = [case for case in cases if case.get("journey")]
    negative_values = _coverage_values(negative_cases, key)
    failure_values = _coverage_values(failure_cases, key)
    multi_values = _coverage_values(multi_cases, key)
    statuses = {}
    for value in sorted(known_values):
        statuses[value] = {
            "covered": value in covered,
            "negative_tested": value in negative_values,
            "failure_injected": value in failure_values,
            "multi_turn_tested": value in multi_values,
        }
    return {
        "known": sorted(known_values), "covered": sorted(known_values & covered),
        "untested": sorted(known_values - covered),
        "partially_tested": sorted(value for value, status in statuses.items() if status["covered"] and not (status["negative_tested"] and status["failure_injected"])),
        "statuses": statuses,
    }


def coverage_audit(cases: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare semantic dogfood metadata to current canonical registries."""
    values = [dict(case) for case in cases]
    from src.aci import PostResultState
    from src.capability_registry import CAPABILITY_REGISTRY
    known_actions = {
        f"{capability_id}:{action_id}"
        for capability_id, capability in CAPABILITY_REGISTRY.items()
        for action_id in capability.actions
    }
    known_executors = {
        str(action.executor_key) for capability in CAPABILITY_REGISTRY.values()
        for action in capability.actions.values() if action.executor_key
    }
    known_domains = {
        "MEMORY", "WORK", "TECHNICAL_ASSET", "NETWORK", "SERVICE", "CONTAINER",
        "STORAGE", "MODEL_RUNTIME", "HOMELAB_HOST", "DEPENDENCY", "SECURITY", "OSINT",
        "HOUSEHOLD_ITEM", "KITCHEN", "CRM", "FINANCE", "DEVELOPER", "SETUP",
        "BACKGROUND_WORK", "UNKNOWN",
    }
    known_policy = {"ALLOW", "DENY", "REQUIRES_APPROVAL", "STALE", "OUT_OF_SCOPE", "DISABLED", "UNKNOWN"}
    known_approval = {"NONE", "NORMAL", "EXACT", "MISSING", "EXPIRED", "REPLAY", "DIGEST_MISMATCH", "OWNER_MISMATCH"}
    dimensions = {
        "domains": _coverage_dimension(known_domains, values, "domain"),
        "intent_classes": _coverage_dimension(_INTENT_CLASSES, values, "intent"),
        "action_specs": _coverage_dimension(known_actions, values, "action_spec"),
        "capabilities": _coverage_dimension(CAPABILITY_REGISTRY.keys(), values, "capability_id"),
        "executors": _coverage_dimension(known_executors, values, "executor"),
        "policy_branches": _coverage_dimension(known_policy, values, "policy"),
        "approval_branches": _coverage_dimension(known_approval, values, "approval"),
        "post_result_states": _coverage_dimension((state.value for state in PostResultState), values, "post_result_state"),
        "failure_classes": _coverage_dimension(_FAILURE_TAXONOMY, values, "failure_class"),
        "reference_types": _coverage_dimension(_REFERENCE_TYPES, values, "reference_type"),
        "conversation_forms": _coverage_dimension(_CONVERSATION_FORMS, values, "conversation_form"),
        "execution_results": _coverage_dimension(_EXECUTION_RESULTS, values, "execution_result"),
        "authority_states": _coverage_dimension(_AUTHORITY_STATES, values, "authority"),
        "entity_types": _coverage_dimension(_ENTITY_TYPES, values, "target_type"),
        "model_profiles": _coverage_dimension(_MODEL_PROFILES, values, "model_profile"),
        "verification_results": _coverage_dimension(_VERIFICATION_RESULTS, values, "verification_result"),
        "cross_domain_pairs": _coverage_dimension(_CROSS_DOMAIN_PAIRS, values, "cross_domain_pair"),
        "failure_injections": _coverage_dimension(_FAILURE_TAXONOMY, values, "failure_injection"),
        # Semantic-universe coverage is kept alongside the established
        # runtime dimensions.  This makes the evaluator aware of what a user
        # can mean even when no high-level ActionSpec exists yet.
        "semantic_entity_types": _coverage_dimension(_SEMANTIC_ENTITY_TYPES, values, "frame_entity_type"),
        "semantic_intents": _coverage_dimension(_SEMANTIC_INTENTS, values, "frame_intent"),
        "requested_properties": _coverage_dimension(_REQUESTED_PROPERTIES, values, "frame_requested_property"),
        "relations": _coverage_dimension(_RELATIONS, values, "frame_relation"),
        "relation_depths": _coverage_dimension((str(value) for value in range(4)), values, "frame_relation_depth"),
        "temporal_scopes": _coverage_dimension(_TEMPORAL_SCOPES, values, "frame_temporal_scope"),
        "epistemic_states": _coverage_dimension(_EPISTEMIC_STATES, values, "frame_epistemic_state"),
        "reference_strategies": _coverage_dimension(_REFERENCE_STRATEGIES, values, "frame_expected_reference_resolution"),
        "semantic_authority_states": _coverage_dimension(_SEMANTIC_AUTHORITIES, values, "frame_expected_authority"),
        "network_scope_states": _coverage_dimension(_NETWORK_SCOPE_STATES, values, "network_scope"),
        "address_states": _coverage_dimension(_ADDRESS_STATES, values, "address_state"),
        "asset_identity_strengths": _coverage_dimension(_ASSET_IDENTITY_STRENGTHS, values, "asset_identity_strength"),
        "language_transformations": _coverage_dimension(_LANGUAGE_TRANSFORMS, values, "language_transform_chain"),
    }
    gaps = []
    for dimension, data in dimensions.items():
        for value in data["untested"]:
            gaps.append(_coverage_gap(dimension, value, tested=False))
        for value in data["partially_tested"]:
            gaps.append(_coverage_gap(dimension, value, tested=True))
    priority_counts = Counter(str(item["priority"]) for item in gaps)
    return {
        "scenario_count": len(values), "dimensions": dimensions,
        "covering_arrays": _covering_array_report(dimensions, values),
        "coverage_gaps": gaps, "coverage_gap_count": len(gaps),
        "critical_gaps_remaining": priority_counts.get("CRITICAL", 0),
        "high_gaps_remaining": priority_counts.get("HIGH", 0),
        "normal_gaps_remaining": priority_counts.get("NORMAL", 0),
        "intentional_exemptions": [],
    }


def _coverage_gap(dimension: str, value: str, *, tested: bool) -> dict[str, Any]:
    """Classify gaps without hiding the raw untested/partial condition."""
    critical_dimensions = {
        "policy_branches", "approval_branches", "post_result_states",
        "failure_classes", "authority_states", "semantic_authority_states", "executors",
    }
    high_dimensions = {
        "domains", "semantic_entity_types", "semantic_intents", "reference_types",
        "reference_strategies", "temporal_scopes", "epistemic_states", "relations",
    }
    if dimension in critical_dimensions:
        priority = "CRITICAL"
        reason = "authority, execution, recovery, or security branch"
    elif dimension in high_dimensions:
        priority = "HIGH"
        reason = "owner-facing semantic or grounding coverage"
    else:
        priority = "NORMAL"
        reason = "coverage expansion dimension"
    return {
        "kind": f"{'PARTIAL' if tested else 'UNTESTED'}_{dimension.upper()}",
        "value": value, "priority": priority, "reason": reason,
        "intentional_exemption": False,
    }


_COVERING_ARRAYS: dict[str, tuple[str, ...]] = {
    "entity_x_intent": ("semantic_entity_types", "semantic_intents"),
    "reference_x_domain_switch_x_stale": (
        "reference_strategies", "conversation_forms", "temporal_scopes",
    ),
    "network_scope_x_authority_x_cross_domain": (
        "network_scope_states", "semantic_authority_states", "cross_domain_pairs",
    ),
    "asset_x_address_change_x_identity": (
        "address_states", "asset_identity_strengths", "reference_strategies",
    ),
    "memory_x_current_observation_x_conflict": (
        "domains", "temporal_scopes", "epistemic_states",
    ),
    "action_x_approval_x_failure": (
        "semantic_intents", "approval_branches", "execution_results",
    ),
    "action_x_verification_failure_x_continuation": (
        "semantic_intents", "verification_results", "post_result_states",
    ),
    "dependency_x_remediation_x_resume": (
        "domains", "failure_classes", "post_result_states",
    ),
}


def _covering_array_report(
    dimensions: Mapping[str, Mapping[str, Any]],
    cases: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Report observed pairwise/targeted 3-way semantic combinations.

    This deliberately reports combinations separately from scalar coverage
    gaps.  Entity/intent compatibility means a naive Cartesian product would
    label many nonsensical combinations as failures; the report therefore
    exposes the expected cross-product size and observed tuples while keeping
    the raw cases as the reproducible oracle for future constraint refinement.
    """
    result: dict[str, Any] = {}
    for name, dimension_names in _COVERING_ARRAYS.items():
        known = [
            tuple(str(value) for value in dimensions.get(dimension, {}).get("known", ()))
            for dimension in dimension_names
        ]
        observed: set[tuple[str, ...]] = set()
        for case in cases:
            scenario = case.get("scenario") if isinstance(case.get("scenario"), Mapping) else {}
            values: list[str] = []
            valid = True
            for dimension in dimension_names:
                coverage = dimensions.get(dimension, {})
                known_values = set(str(value) for value in coverage.get("known", ()))
                if dimension.startswith("semantic_"):
                    frame = scenario.get("scenario_frame")
                    field = {
                        "semantic_entity_types": "entity_type",
                        "semantic_intents": "intent",
                        "semantic_authority_states": "expected_authority",
                    }.get(dimension)
                    value = frame.get(field) if isinstance(frame, Mapping) and field else None
                elif dimension == "reference_strategies":
                    frame = scenario.get("scenario_frame")
                    value = frame.get("expected_reference_resolution") if isinstance(frame, Mapping) else None
                else:
                    scenario_field = {
                        "approval_branches": "approval",
                        "execution_results": "execution_result",
                        "verification_results": "verification_result",
                        "post_result_states": "post_result_state",
                        "failure_classes": "failure_class",
                        "network_scope_states": "network_scope",
                        "address_states": "address_state",
                        "asset_identity_strengths": "asset_identity_strength",
                    }.get(dimension, dimension.removesuffix("s"))
                    value = scenario.get(scenario_field)
                    if value is None and dimension == "domains":
                        value = scenario.get("domain")
                    if value is None and dimension == "cross_domain_pairs":
                        value = scenario.get("cross_domain_pair")
                if isinstance(value, (list, tuple, set)):
                    value = next(iter(value), None)
                value = str(value) if value is not None else ""
                if not value or (known_values and value not in known_values):
                    valid = False
                    break
                values.append(value)
            if valid:
                observed.add(tuple(values))
        total = 1
        for values in known:
            total *= len(values)
        result[name] = {
            "dimensions": list(dimension_names),
            "expected_cross_product": total,
            "observed": len(observed),
            "coverage_percent": round((len(observed) / total) * 100, 2) if total else 0.0,
            "sample_uncovered": [
                list(candidate)
                for candidate in _missing_combination_sample(known, observed, limit=20)
            ],
        }
    return result


def _missing_combination_sample(
    dimensions: list[tuple[str, ...]],
    observed: set[tuple[str, ...]],
    *,
    limit: int,
) -> list[tuple[str, ...]]:
    """Return a bounded deterministic sample without materializing huge gaps."""
    import itertools

    missing: list[tuple[str, ...]] = []
    for candidate in itertools.product(*dimensions):
        if candidate not in observed:
            missing.append(candidate)
            if len(missing) >= limit:
                break
    return missing


def capture_failure_regressions(
    path: str | Path,
    cases: Iterable[Mapping[str, Any]],
    scores: Iterable[Mapping[str, Any]],
    *,
    include_prompts: bool = True,
) -> dict[str, Any]:
    """Persist synthetic failure reproducers without capturing live owner text."""
    target = Path(path)
    try:
        prior = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"schema_version": 1, "cases": []}
    except (OSError, json.JSONDecodeError):
        prior = {"schema_version": 1, "cases": []}
    prior_cases = prior.get("cases", []) if isinstance(prior, Mapping) else []
    existing = {str(item.get("id")): item for item in prior_cases if isinstance(item, Mapping)}
    captured = 0
    for case, score in zip(cases, scores):
        if score.get("functional_pass") and score.get("architectural_pass"):
            continue
        source = str(case.get("source") or "")
        failure_classes = set(score.get("failure_classes") or ())
        failure_classes.update(
            str(name) for name in score.get("failures", ())
            if str(name) in _FAILURE_TAXONOMY
        )
        failure_classes.update(
            _CHECK_FAILURE_CLASSES[name]
            for name in score.get("failures", ())
            if name in _CHECK_FAILURE_CLASSES
        )
        scenario_failure = (case.get("scenario") or {}).get("failure_class")
        if scenario_failure in _FAILURE_TAXONOMY:
            failure_classes.add(str(scenario_failure))
        entry = {
            "id": f"regression-{digest(case.get('id'))}",
            "case_id": case.get("id"), "prompt_digest": digest(case.get("prompt")),
            "family": case.get("family"), "expected": dict(case.get("expected") or {}),
            "scenario": dict(case.get("scenario") or {}),
            "failure_classes": sorted(failure_classes),
            "source": source,
            "seed": case.get("seed"), "variant_id": case.get("variant_id"),
            "fixture_id": case.get("fixture_id"),
            "run_id": case.get("run_id"),
            "run_metadata": dict(case.get("run_metadata") or {}),
        }
        if include_prompts and not source.startswith("live"):
            entry["prompt"] = case.get("prompt")
            entry["variants"] = _semantic_regression_variants(str(case.get("prompt") or ""))
        if entry["id"] not in existing:
            existing[entry["id"]] = entry
            captured += 1
    payload = {"schema_version": 1, "cases": list(existing.values())}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(target), "captured": captured, "total": len(payload["cases"])}


def append_history(path: str | Path, result: Mapping[str, Any]) -> dict[str, Any]:
    """Persist a sanitized per-commit trend record for regression comparison."""
    target = Path(path)
    try:
        history = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"schema_version": 1, "runs": []}
    except (OSError, json.JSONDecodeError):
        history = {"schema_version": 1, "runs": []}
    summary = dict(result.get("summary") or {})
    run_metadata = result.get("run_metadata") if isinstance(result.get("run_metadata"), Mapping) else {}
    entry = {
        "timestamp": time.time(),
        "commit": run_metadata.get("source_commit") or os.environ.get("HADES_SOURCE_REFERENCE") or "working-tree",
        "source_dirty": bool(run_metadata.get("source_dirty", False)),
        "model": result.get("model"), "mode": result.get("mode"), "seed": result.get("seed"),
        "summary": summary, "coverage_gap_count": (result.get("coverage") or {}).get("coverage_gap_count"),
    }
    history.setdefault("runs", []).append(entry)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return entry


def _metric(metrics: Mapping[str, Any], *names: str, default: float = 0) -> float:
    for name in names:
        value = metrics.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return default


def delivery_observation(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Project transport delivery invariants without comparing answer prose.

    Event identity and lifecycle ordering are the evidence. Repeated text is
    deliberately not treated as a duplicate because a user may legitimately
    receive the same words in distinct turns.
    """
    values = [dict(event) for event in events]
    replacements = [event for event in values if event.get("type") == "response_replace"]
    deltas = [event for event in values if "delta" in event]
    replace_positions = [index for index, event in enumerate(values) if event.get("type") == "response_replace"]
    stale_delta_after_replace = any(
        index > replace_positions[-1] and "delta" in event
        for index, event in enumerate(values)
    ) if replace_positions else False
    event_ids = [str(event.get("event_id") or event.get("id")) for event in values
                 if event.get("event_id") is not None or event.get("id") is not None]
    return {
        "delta_count": len(deltas),
        "response_replace_count": len(replacements),
        "duplicate_finalization": len(replacements) > 1,
        "stale_delta_after_replace": stale_delta_after_replace,
        "duplicate_event_id": bool(event_ids and len(event_ids) != len(set(event_ids))),
        "event_id_count": len(event_ids),
        "delivery_identity": digest(tuple(event_ids)) if event_ids else None,
    }


def authoritative_answer_text(events: Iterable[Mapping[str, Any]]) -> str:
    """Render the evaluator's view of one answer using lifecycle semantics.

    ``response_replace`` is a server-authorized replacement of previously
    streamed model deltas, not an additional answer.  Prefer its latest
    content when present; otherwise concatenate ordinary deltas.  This is
    delivery-state handling, deliberately not arbitrary text de-duplication.
    """
    values = [dict(event) for event in events]
    replacements = [
        event for event in values
        if event.get("type") == "response_replace"
        and isinstance(event.get("content"), str)
    ]
    if replacements:
        return str(replacements[-1].get("content") or "")
    return "".join(str(event.get("delta") or "") for event in values)


def _reference_expectation(case: Mapping[str, Any]) -> str | None:
    """Return an explicit reference oracle, never an inference from prose."""
    expected = case.get("expected")
    if isinstance(expected, Mapping):
        value = expected.get("reference_resolution")
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    scenario = case.get("scenario")
    if isinstance(scenario, Mapping):
        value = scenario.get("reference_expectation")
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def normalize_events(events: Iterable[Mapping[str, Any]], case: Mapping[str, Any], *, elapsed: float = 0) -> dict[str, Any]:
    events = [dict(event) for event in events]
    metrics = next((event.get("data", {}) for event in reversed(events)
                    if event.get("type") == "metrics" and isinstance(event.get("data"), Mapping)), {})
    text = authoritative_answer_text(events)
    tool_events = [event for event in events if event.get("type") == "tool_start"]
    tool_outputs = [event for event in events if event.get("type") == "tool_output"]
    tool_names = [str(event.get("tool") or "") for event in tool_events]
    saved = [str(event.get("id")) for event in events if event.get("type") == "message_saved" and event.get("id")]
    burden = metrics.get("model_burden") if isinstance(metrics, Mapping) else {}
    labels = burden.get("labels", {}) if isinstance(burden, Mapping) else {}
    decision_calls = int(_metric(metrics, "aci_bounded_action_decision_count", default=_metric(labels.get("model", {}) if isinstance(labels, Mapping) else {}, "bounded_action_decision")))
    failed_actions = sum(event.get("exit_code") not in (None, 0) for event in tool_outputs)
    duplicate_delivery = max(0, len(saved) - len(set(saved))) if saved else 0
    intent = metrics.get("aci_intent") if isinstance(metrics.get("aci_intent"), Mapping) else {}
    reference = metrics.get("aci_reference_resolution") if isinstance(metrics.get("aci_reference_resolution"), Mapping) else {}
    aci_trace = metrics.get("aci_trace") if isinstance(metrics.get("aci_trace"), Mapping) else {}
    # The runtime owns the lifecycle trace; the evaluator only normalizes it
    # and fills in delivery/answer observations that are visible at the SSE
    # boundary.  This keeps grading trace-level invariants separate from prose
    # success while avoiding a second orchestration model in the benchmark.
    aci_trace = dict(aci_trace)
    aci_trace.update({
        "answer_present": bool(text.strip()),
        "duplicate_response": int(duplicate_delivery),
        "internal_leakage": bool(_INTERNAL.search(text)),
        "latency_seconds": round(float(elapsed), 4),
    })
    expected_reference = _reference_expectation(case)
    reference = dict(reference)
    if expected_reference:
        reference["expected_status"] = expected_reference
    delivery = delivery_observation(events)
    return {
        "schema_version": SCHEMA_VERSION, "case_id": case["id"], "source": case["source"],
        "family": case["family"], "prompt_digest": digest(case["prompt"]),
        "scenario": {
            "seed": case.get("seed"), "run_id": case.get("run_id"),
            "scenario_id": case.get("id"), "variant_id": case.get("variant_id"),
            "fixture_id": case.get("fixture_id"),
            "model": (case.get("run_metadata") or {}).get("model"),
            "model_digest": (case.get("run_metadata") or {}).get("model_digest"),
            "source_commit": (case.get("run_metadata") or {}).get("source_commit"),
            "deployed_source": (case.get("run_metadata") or {}).get("deployed_source"),
            "config_fingerprint": (case.get("run_metadata") or {}).get("config_fingerprint"),
        },
        "assistant_answer": {"present": bool(text.strip()), "chars": len(text),
                             "internal_leak": bool(_INTERNAL.search(text)), "secret_seen": bool(_SECRET.search(text))},
        "trajectory": {"tool_calls": len(tool_events), "failed_actions": int(failed_actions),
                       "tool_names": tool_names,
                       "fallbacks": sum(event.get("type") == "fallback" for event in events),
                       "duplicate_delivery": int(duplicate_delivery),
                       "message_saved_count": len(saved), "message_saved_unique": len(set(saved)),
                       "intent": dict(intent), "reference": dict(reference),
                       "action_candidates": list(aci_trace.get("action_candidates") or []),
                       "selected_action": aci_trace.get("selected_action"),
                       "post_result_state": aci_trace.get("post_result_state"),
                       "completion_state": aci_trace.get("completion_state"),
                       "aci_trace": aci_trace},
        "contract_observations": {
            "required_tools": all(str(item) in tool_names for item in (case.get("expected") or {}).get("required_tools", [])),
            "forbidden_tools": all(str(item) not in tool_names for item in (case.get("expected") or {}).get("forbidden_tools", [])),
            "refused": bool(_REFUSAL.search(text)),
            "response_excludes": all(str(item).casefold() not in text.casefold() for item in (case.get("expected") or {}).get("response_excludes", [])),
            "recovered": bool(sum(event.get("type") == "fallback" for event in events) or (failed_actions and any(event.get("exit_code") == 0 for event in tool_outputs))),
        },
        "metrics": {"model_calls": int(_metric(metrics, "model_calls")),
                    "decision_calls": decision_calls,
                    "tool_index_lookups": int(_metric(metrics, "tool_index_lookup_count")),
                    "failed_actions": int(failed_actions),
                    "context_hydrations": int(_metric(metrics, "context_hydration_count", "context_hydrations", default=0)),
                    "continuation_rounds": max(0, int(_metric(metrics, "agent_rounds", "rounds", default=0)) - 1),
                    "prompt_tokens": int(_metric(metrics, "input_tokens", "request_context_tokens")),
                    "completion_tokens": int(_metric(metrics, "output_tokens")),
                    "latency_seconds": round(float(elapsed), 4)},
        "runtime": {"completion": bool(metrics.get("aci_completion_contract_satisfied")),
                    "fallback": bool(metrics.get("aci_model_fallback")),
                    "intent": dict(intent), "reference": dict(reference),
                    "aci_trace": aci_trace},
        "delivery": delivery,
    }


def _check_limit(value: int | float, expected: Any) -> bool:
    return expected is None or not isinstance(expected, (int, float)) or value <= expected


def score_case(case: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any]:
    expected = dict(case.get("expected") or {})
    trajectory = record["trajectory"]
    metrics = record["metrics"]
    runtime = record["runtime"]
    observations = record.get("contract_observations", {})
    intent = trajectory.get("intent") or runtime.get("intent") or {}
    expected_concept = _CANONICAL_CONCEPT_ALIASES.get(
        str(expected.get("concept") or ""), expected.get("concept")
    )
    expected_concepts = {
        _CANONICAL_CONCEPT_ALIASES.get(str(value), value)
        for value in (expected.get("concepts") or ())
    }
    if expected_concept:
        expected_concepts.add(expected_concept)
    checks: dict[str, bool] = {
        "answer_present": bool(record["assistant_answer"]["present"]),
        "no_internal_leak": not bool(record["assistant_answer"]["internal_leak"]),
        "no_secret": not bool(record["assistant_answer"]["secret_seen"]),
        "concept": not expected_concept or intent.get("domain_concept") in expected_concepts,
        "operation": not expected.get("operation") or intent.get("operation_class") == expected.get("operation"),
        "decision_budget": _check_limit(metrics["decision_calls"], expected.get("max_decision_calls")),
        "model_budget": _check_limit(metrics["model_calls"], expected.get("max_model_calls")),
        "tool_index_budget": _check_limit(metrics["tool_index_lookups"], expected.get("max_tool_index_lookups")),
        "failed_action_budget": _check_limit(trajectory["failed_actions"], expected.get("max_failed_actions")),
        "context_budget": _check_limit(metrics["context_hydrations"], expected.get("max_context_hydrations", 2)),
        "completion": expected.get("completion") is not True or bool(runtime.get("completion")),
        "fallback": expected.get("fallback") is not True or bool(runtime.get("fallback")),
        "required_tools": all(observations.get("required_tools", True) for _ in expected.get("required_tools", [])),
        "forbidden_tools": observations.get("forbidden_tools", True),
        "must_refuse": not expected.get("must_refuse") or bool(observations.get("refused")),
        "response_excludes": observations.get("response_excludes", True),
        "recovery": not expected.get("requires_recovery") or bool(observations.get("recovered")),
        "exactly_once": trajectory["duplicate_delivery"] == 0,
    }
    delivery = record.get("delivery") if isinstance(record.get("delivery"), Mapping) else {}
    if delivery:
        checks["no_duplicate_finalization"] = not bool(delivery.get("duplicate_finalization"))
        checks["no_stale_delta_after_replace"] = not bool(delivery.get("stale_delta_after_replace"))
    transport = record.get("transport")
    if isinstance(transport, Mapping):
        checks["transport_completion"] = bool(transport.get("transport_completion"))
        checks["terminal_event_count"] = transport.get("terminal_event_count") == 1
        checks["no_duplicate_event_id"] = not bool(transport.get("duplicate_event_id"))
    # Semantic cases carry a frame oracle.  Grade the trace against that
    # oracle when the runtime emitted the corresponding canonical fields;
    # otherwise a fluent answer must not mask a wrong/missing Action path.
    oracle = expected.get("semantic_oracle")
    trace = trajectory.get("aci_trace") if isinstance(trajectory.get("aci_trace"), Mapping) else {}
    if isinstance(oracle, Mapping):
        oracle_domain = str(oracle.get("expected_domain") or "").strip()
        if oracle_domain:
            checks["semantic_domain"] = str(intent.get("domain_concept") or "") == _CANONICAL_CONCEPT_ALIASES.get(oracle_domain, oracle_domain)
        oracle_action_spec = str((case.get("scenario") or {}).get("action_spec") or "").strip()
        selected = trace.get("selected_action") if isinstance(trace.get("selected_action"), Mapping) else {}
        if oracle_action_spec:
            actual_capability = str(
                selected.get("capability_id") or selected.get("capability") or ""
            ).strip()
            if not actual_capability:
                # Selected-action traces historically expose the transport
                # binding. Resolve that binding through the same registry used
                # by the runtime; never compare provider names heuristically.
                try:
                    from src.capability_registry import capability_for_tool
                    capability = capability_for_tool(str(selected.get("binding") or ""))
                    actual_capability = str(getattr(capability, "capability_id", "") or "")
                except Exception:
                    actual_capability = ""
            actual_action_spec = f"{actual_capability}:{selected.get('action_id') or ''}"
            # A semantic oracle that names an ActionSpec requires an actual
            # selected Action. A fluent answer with no canonical selection is
            # a semantic failure, not a passing prose response.
            if (case.get("scenario") or {}).get("synthetic_capability_available") is False:
                # A known registry Action without a transport binding is a
                # capability-gap case, not permission to route it through a
                # neighboring read-only fixture. It passes this semantic
                # check only when the runtime fails closed without executing
                # any tool.
                checks["semantic_action"] = not selected and trajectory["tool_calls"] == 0
            else:
                checks["semantic_action"] = bool(selected) and actual_action_spec == oracle_action_spec
        oracle_grounding = str(oracle.get("expected_grounding") or "").strip()
        actual_grounding = str(trace.get("grounding") or "").strip()
        if oracle_grounding:
            # Missing grounding metadata is missing evidence, not an implicit
            # pass. This prevents prose-only records from satisfying a frame
            # that explicitly requires a canonical Result or qualified state.
            checks["semantic_grounding"] = bool(actual_grounding) and actual_grounding == oracle_grounding
        oracle_completion = str(oracle.get("expected_completion") or "").strip()
        actual_completion = str(trace.get("completion_state") or trajectory.get("completion_state") or "").strip()
        if oracle_completion:
            checks["semantic_completion"] = bool(actual_completion) and actual_completion in {oracle_completion, "COMPLETE" if oracle_completion == "COMPLETE_AFTER_ANSWER" else oracle_completion}
    # Imported/frozen cases without a ScenarioFrame retain their established
    # scoring contract; semantic checks are opt-in per case.
    for semantic_key in (
        "semantic_domain", "semantic_action", "semantic_grounding",
        "semantic_completion",
    ):
        checks.setdefault(semantic_key, True)
    if expected.get("max_tool_calls") is not None:
        checks["tool_budget"] = trajectory["tool_calls"] <= int(expected["max_tool_calls"])
    functional_keys = ("answer_present", "no_internal_leak", "no_secret", "concept", "operation", "completion", "fallback", "required_tools", "forbidden_tools", "must_refuse", "response_excludes", "recovery", "semantic_domain", "semantic_action", "semantic_grounding", "semantic_completion")
    architectural_keys = ("decision_budget", "model_budget", "tool_index_budget", "failed_action_budget", "context_budget", "exactly_once")
    if delivery:
        architectural_keys += ("no_duplicate_finalization", "no_stale_delta_after_replace")
    if isinstance(transport, Mapping):
        architectural_keys += ("transport_completion", "terminal_event_count", "no_duplicate_event_id")
    functional = all(checks[key] for key in functional_keys)
    architectural = all(checks[key] for key in architectural_keys)
    if "tool_budget" in checks:
        architectural = architectural and checks["tool_budget"]
    failures = [name for name, passed in checks.items() if not passed]
    failure_classes = {
        _CHECK_FAILURE_CLASSES[name] for name in failures
        if name in _CHECK_FAILURE_CLASSES
    }
    scenario_failure = (case.get("scenario") or {}).get("failure_class")
    if scenario_failure in _FAILURE_TAXONOMY and failures:
        failure_classes.add(str(scenario_failure))
    return {"case_id": case["id"], "family": case["family"], "functional_pass": functional,
            "architectural_pass": architectural, "outcome": "PASS" if functional and architectural else ("FUNCTIONAL_PASS" if functional else "FAIL"),
            "checks": checks, "failures": failures, "failure_classes": sorted(failure_classes)}


def summarize(records: Iterable[Mapping[str, Any]], scores: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records, scores = list(records), list(scores)
    def mean(name: str) -> float:
        values = [r["metrics"][name] for r in records if isinstance(r.get("metrics", {}).get(name), (int, float))]
        return round(sum(values) / len(values), 4) if values else 0.0
    latencies = sorted(float(r["metrics"]["latency_seconds"]) for r in records)
    p95 = latencies[max(0, math.ceil(len(latencies) * .95) - 1)] if latencies else 0.0
    functional = sum(bool(s["functional_pass"]) for s in scores)
    architectural = sum(bool(s["architectural_pass"]) for s in scores)
    security = sum(not r["assistant_answer"]["secret_seen"] and not r["assistant_answer"]["internal_leak"] for r in records)
    clusters = Counter(
        failure for score in scores
        for failure in (score.get("failure_classes") or score.get("failures", []))
    )
    concepts = [r["trajectory"].get("intent", {}).get("domain_concept") for r in records]
    # Qualified cases carry an explicit expected status. Older ad-hoc test
    # records have no oracle, so retain their historical attempted-only
    # denominator for compatibility while reporting the unqualified count.
    qualified_refs = [
        r["trajectory"].get("reference", {})
        for r in records
        if r["trajectory"].get("reference", {}).get("expected_status")
    ]
    legacy_refs = [
        r["trajectory"].get("reference", {}).get("status")
        for r in records
        if not r["trajectory"].get("reference", {}).get("expected_status")
        and r["trajectory"].get("reference", {}).get(
            "attempted",
            r["trajectory"].get("reference", {}).get("status") not in {None, "NOT_REFERENCE"},
        )
    ]
    refs = qualified_refs or legacy_refs
    reference_accuracy = (
        sum(str(item.get("status") or "").upper() == str(item.get("expected_status") or "").upper() for item in qualified_refs)
        / len(qualified_refs)
        if qualified_refs else
        sum(item == "RESOLVED" for item in legacy_refs) / len(legacy_refs)
        if legacy_refs else 0.0
    )
    repair_candidates = [
        {"failure": failure, "architecture_layer": _REPAIR_LAYERS.get(failure, "evaluation_contract"),
         "auto_apply": False, "requires_owner_approval": True}
        for failure, _count in clusters.most_common(10)
    ]
    return {"functional_success": functional, "architectural_success": architectural,
            "security_success": security, "scenario_count": len(records),
            "functional_rate": round(functional / len(records), 4) if records else 0.0,
            "architectural_rate": round(architectural / len(records), 4) if records else 0.0,
            "security_rate": round(security / len(records), 4) if records else 0.0,
            "domain_reference_accuracy": round(sum(bool(x) and x != "UNKNOWN" for x in concepts) / len(concepts), 4) if concepts else 0.0,
            "reference_case_count": len(refs),
            "qualified_reference_case_count": len(qualified_refs),
            "unqualified_reference_attempt_count": len(legacy_refs),
            "reference_resolution_accuracy": round(reference_accuracy, 4),
            "duplicate_rate": round(sum(r["trajectory"]["duplicate_delivery"] > 0 for r in records) / len(records), 4) if records else 0.0,
            "model_calls_per_task": mean("model_calls"), "decision_calls_per_task": mean("decision_calls"),
            "tool_index_lookups_per_task": mean("tool_index_lookups"), "failed_actions_per_task": mean("failed_actions"),
            "prompt_tokens_per_task": mean("prompt_tokens"), "completion_tokens_per_task": mean("completion_tokens"),
            "context_hydrations_per_task": mean("context_hydrations"), "continuation_rounds_per_task": mean("continuation_rounds"),
            "median_latency_seconds": latencies[len(latencies) // 2] if latencies else 0.0,
            "p95_latency_seconds": p95, "top_failure_clusters": clusters.most_common(10),
            "repair_controls": {"enabled": True, "auto_apply": False,
                                 "requires_owner_approval": True,
                                 "candidates": repair_candidates}}


def cluster_failures(cases: Iterable[Mapping[str, Any]], scores: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Cluster failures by semantic trace evidence, never by prompt text.

    A single broken projection should produce one actionable work item even
    when many language variants exercise it.  Case IDs remain available for
    exact replay while prompts and answers stay out of the cluster artifact.
    """
    clusters: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for case, score in zip(cases, scores):
        if score.get("functional_pass") and score.get("architectural_pass"):
            continue
        scenario = case.get("scenario") if isinstance(case.get("scenario"), Mapping) else {}
        frame = scenario.get("scenario_frame") if isinstance(scenario.get("scenario_frame"), Mapping) else {}
        failure_classes = tuple(sorted(str(value) for value in (score.get("failure_classes") or score.get("failures") or ()))) or ("UNCLASSIFIED",)
        # The leading class is the primary root-cause work queue key; the
        # remaining classes are retained as co-occurring evidence.
        key = (failure_classes[0], str(frame.get("expected_domain") or scenario.get("domain") or "UNKNOWN"), str(frame.get("intent") or scenario.get("intent") or "UNKNOWN"), str(frame.get("expected_action_class") or "UNKNOWN"))
        item = clusters.setdefault(key, {
            "root_cause": key[0], "domain": key[1], "intent": key[2],
            "action_class": key[3], "count": 0, "case_ids": [],
            "co_occurring_failure_classes": set(), "families": set(),
        })
        item["count"] += 1
        item["case_ids"].append(case.get("id"))
        item["co_occurring_failure_classes"].update(failure_classes)
        item["families"].add(case.get("family"))
    result = []
    for item in clusters.values():
        result.append({
            **item,
            "co_occurring_failure_classes": sorted(item["co_occurring_failure_classes"]),
            "families": sorted(str(value) for value in item["families"] if value),
        })
    return sorted(result, key=lambda item: (-int(item["count"]), str(item["root_cause"]), str(item["domain"])))


def report(contract: Mapping[str, Any], cases: list[Mapping[str, Any]], records: list[Mapping[str, Any]], *, model: str, mode: str, seed: int) -> dict[str, Any]:
    scores = [score_case(case, record) for case, record in zip(cases, records)]
    coverage = coverage_audit(cases)
    return {"schema_version": SCHEMA_VERSION, "contract": contract["name"], "model": model,
            "mode": mode, "seed": seed, "contract_summary": contract_summary(contract, cases),
            "summary": {**summarize(records, scores), "coverage_gap_count": coverage["coverage_gap_count"]},
            "coverage": coverage, "failure_clusters": cluster_failures(cases, scores),
            "scores": scores, "records": records}
