"""Hades Agent Cognition Interface projections.

This module contains ephemeral, model-facing contracts only.  It deliberately
does not persist truth, execute Actions, or grant authority: canonical Run,
ActionSpec, policy, approval, and Result code remain authoritative.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import hashlib
import json
from typing import Any, Mapping, Sequence


class DecisionMode(StrEnum):
    ACTION = "ACTION"
    ANSWER = "ANSWER"
    NEED_CONTEXT = "NEED_CONTEXT"
    CLARIFY = "CLARIFY"
    BLOCKED = "BLOCKED"


class PostResultState(StrEnum):
    COMPLETE_AFTER_ANSWER = "COMPLETE_AFTER_ANSWER"
    CONTINUE_DETERMINISTICALLY = "CONTINUE_DETERMINISTICALLY"
    NEEDS_BOUNDED_REASONING = "NEEDS_BOUNDED_REASONING"
    NEEDS_CONTEXT = "NEEDS_CONTEXT"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    BLOCKED = "BLOCKED"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"


class TurnDisposition(StrEnum):
    """One semantic disposition for the current turn, not authority."""

    ANSWER = "ANSWER"
    EXECUTE_DIRECT = "EXECUTE_DIRECT"
    DECIDE = "DECIDE"
    CONTINUE = "CONTINUE"
    REQUEST_CONTEXT = "REQUEST_CONTEXT"
    CLARIFY = "CLARIFY"
    AWAIT_APPROVAL = "AWAIT_APPROVAL"
    BLOCK = "BLOCK"
    MODEL_FALLBACK = "MODEL_FALLBACK"


class RelevanceTier(StrEnum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


@dataclass(frozen=True)
class CompletionContract:
    """Framework-owned completion requirements, not a model assertion."""

    kind: str
    required: tuple[str, ...] = ()
    predicates: tuple[str, ...] = ()
    fuzzy: bool = False


@dataclass(frozen=True)
class ObjectiveSpec:
    objective_id: str
    owner: str
    domain: str
    summary: str
    target_refs: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    desired_output: str = ""
    completion: CompletionContract = field(default_factory=lambda: CompletionContract("answer"))
    status: str = "active"
    source_turn: str | None = None
    version: int = 1


@dataclass(frozen=True)
class WorkingSet:
    """Derived state assembled from canonical records for one inference step."""

    objective: Mapping[str, Any]
    active_run: Mapping[str, Any] | None = None
    run_phase: str | None = None
    completed_steps: tuple[str, ...] = ()
    pending_steps: tuple[str, ...] = ()
    active_entities: tuple[Mapping[str, Any], ...] = ()
    resolved_references: tuple[str, ...] = ()
    current_state: Mapping[str, Any] = field(default_factory=dict)
    important_historical_state: Mapping[str, Any] = field(default_factory=dict)
    relevant_memory: tuple[Mapping[str, Any], ...] = ()
    recent_results: tuple[Mapping[str, Any], ...] = ()
    knowns: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    candidate_operation_context: Mapping[str, Any] = field(default_factory=dict)
    authority_constraints: tuple[str, ...] = ()
    environment_constraints: tuple[str, ...] = ()
    completion: Mapping[str, Any] = field(default_factory=dict)
    state_fingerprint: str = ""

    def with_fingerprint(self) -> "WorkingSet":
        payload = asdict(self)
        payload.pop("state_fingerprint", None)
        return WorkingSet(**{**payload, "state_fingerprint": state_fingerprint(payload)})

    def tiered(self) -> dict[str, dict[str, Any]]:
        """Return a compact projection with T0/T1 protected from low-value data."""
        return {
            RelevanceTier.T0.value: {
                "objective": self.objective,
                "active_run": self.active_run,
                "run_phase": self.run_phase,
                "pending_steps": list(self.pending_steps),
                "resolved_references": list(self.resolved_references),
                "recent_results": list(self.recent_results),
                "completion": self.completion,
                "state_fingerprint": self.state_fingerprint,
            },
            RelevanceTier.T1.value: {
                "active_entities": list(self.active_entities),
                "current_state": self.current_state,
                "knowns": list(self.knowns),
                "unknowns": list(self.unknowns),
                "contradictions": list(self.contradictions),
            },
            RelevanceTier.T2.value: {
                "important_historical_state": self.important_historical_state,
                "relevant_memory": list(self.relevant_memory),
            },
            RelevanceTier.T3.value: {"candidate_operation_context": self.candidate_operation_context},
        }


@dataclass(frozen=True)
class ActionCard:
    choice: str
    action_id: str
    label: str
    purpose: str
    when_to_use: str = ""
    preconditions: tuple[str, ...] = ()
    effect: str = "read only"
    approval: str = "none"
    expected_result: str = ""
    negative_semantics: tuple[str, ...] = ()
    risk: str = "low"


@dataclass(frozen=True)
class AgentTaskPacket:
    task_type: str
    objective: Mapping[str, Any]
    progress: Mapping[str, Any]
    entities: tuple[Mapping[str, Any], ...]
    current_state: Mapping[str, Any]
    evidence: tuple[Mapping[str, Any], ...]
    knowns: tuple[str, ...]
    unknowns: tuple[str, ...]
    decisions: tuple[str, ...]
    action_cards: tuple[ActionCard, ...]
    constraints: tuple[str, ...]
    completion: Mapping[str, Any]
    output_contract: str
    state_fingerprint: str

    def model_projection(self) -> dict[str, Any]:
        data = asdict(self)
        # The model receives opaque choices and semantics. Canonical action IDs
        # stay in the server-side choice map and are never a machine authority
        # exposed by the model protocol.
        data["action_cards"] = [
            {key: value for key, value in asdict(card).items() if key != "action_id"}
            for card in self.action_cards
        ]
        return data


@dataclass(frozen=True)
class DecisionContract:
    decision: DecisionMode
    choice: str | None = None
    context_type: str | None = None
    ambiguity_class: str | None = None
    rationale: str | None = None
    state_fingerprint: str | None = None
    answer: str | None = None

    def validate(self, packet: AgentTaskPacket) -> tuple[bool, str | None]:
        if packet.state_fingerprint and self.state_fingerprint != packet.state_fingerprint:
            return False, "stale_state_fingerprint"
        if self.decision is DecisionMode.ACTION:
            choices = {card.choice for card in packet.action_cards}
            if self.choice not in choices:
                return False, "choice_not_in_packet"
        elif self.decision is DecisionMode.NEED_CONTEXT:
            allowed = set(packet.progress.get("allowed_context", ()))
            if not self.context_type or self.context_type not in allowed:
                return False, "context_type_not_allowed"
        elif self.decision is DecisionMode.CLARIFY and not self.ambiguity_class:
            return False, "missing_ambiguity_class"
        return True, None


@dataclass(frozen=True)
class ResultProjection:
    status: str
    observations: tuple[str, ...] = ()
    deltas: tuple[str, ...] = ()
    objective_relevance: tuple[str, ...] = ()
    epistemic_type: str = "OBSERVED"
    freshness: str = "unknown"
    missing_evidence: tuple[str, ...] = ()
    canonical_refs: tuple[str, ...] = ()
    detail_level: str = "L0"


@dataclass(frozen=True)
class ACIProfile:
    name: str = "standard"
    target_context_tokens: int = 6000
    max_action_cards: int = 5
    max_context_expansions: int = 2
    max_decision_repairs: int = 1
    strict_decision_json: bool = True
    progressive_results: bool = True


@dataclass(frozen=True)
class ContextEnvelope:
    architecture_max_context: int = 0
    provider_configured_max_context: int = 0
    runtime_allocated_context: int = 0
    hardware_recommended_context: int = 0
    user_configured_limit: int = 0
    aci_profile_target: int = 6000
    requested_input_budget: int = 0
    reserved_output_budget: int = 1024

    @classmethod
    def from_runtime_profile(cls, profile: Any, *, user_configured_limit: int = 0,
                             aci_profile_target: int = 6000,
                             requested_input_budget: int = 0,
                             reserved_output_budget: int = 1024) -> "ContextEnvelope":
        """Project runtime evidence into the model-facing context budget.

        Architecture maximum is retained as evidence, never treated as the
        desired allocation. Unknown limits stay zero and therefore do not
        create a false hard bound.
        """
        return cls(
            architecture_max_context=max(0, int(getattr(profile, "architecture_max_context", 0) or 0)),
            provider_configured_max_context=max(0, int(getattr(profile, "provider_configured_max_context", 0) or 0)),
            runtime_allocated_context=max(0, int(getattr(profile, "runtime_allocated_context", 0) or 0)),
            hardware_recommended_context=max(0, int(getattr(profile, "hardware_recommended_context", 0) or 0)),
            user_configured_limit=max(0, int(user_configured_limit or 0)),
            aci_profile_target=max(1, int(aci_profile_target or 6000)),
            requested_input_budget=max(0, int(requested_input_budget or 0)),
            reserved_output_budget=max(0, int(reserved_output_budget or 0)),
        )

    @property
    def effective_context(self) -> int:
        limits = [value for value in (
            self.architecture_max_context,
            self.provider_configured_max_context,
            self.runtime_allocated_context,
            self.hardware_recommended_context,
            self.user_configured_limit,
        ) if value > 0]
        hard = min(limits) if limits else 0
        target = self.requested_input_budget or self.aci_profile_target
        return max(0, min(target + self.reserved_output_budget, hard) if hard else target + self.reserved_output_budget)


def state_fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()[:24]


def hard_filter_actions(actions: Sequence[Mapping[str, Any]], *, domain: str | None = None,
                        operation_class: str | None = None, entity_type: str | None = None,
                        healthy_dependencies: set[str] | None = None,
                        allowed_actions: set[str] | None = None) -> list[Mapping[str, Any]]:
    """Filter candidates before ranking; policy/approval still run downstream."""
    result = []
    healthy_dependencies = healthy_dependencies or set()
    for action in actions:
        if allowed_actions is not None and action.get("action_id") not in allowed_actions:
            continue
        if domain and action.get("domain") not in (None, domain):
            continue
        if operation_class and action.get("operation_class") not in (None, operation_class):
            continue
        if entity_type and action.get("entity_type") not in (None, entity_type):
            continue
        required = set(action.get("required_dependencies", ()))
        if required - healthy_dependencies:
            continue
        if action.get("applicable") is False or action.get("policy_allowed") is False:
            continue
        result.append(action)
    return result


def adaptive_shortlist(actions: Sequence[Mapping[str, Any]], confidence: str = "medium", *, limit: int | None = None) -> list[Mapping[str, Any]]:
    sizes = {"high": 3, "medium": 6, "low": 8}
    count = limit or sizes.get(confidence, sizes["medium"])
    return list(actions[:max(0, count)])


def parse_decision_json(value: Any, packet: AgentTaskPacket) -> tuple[DecisionContract | None, str | None]:
    """Parse the sole machine protocol; no tool IDs or arbitrary names accepted."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None, "malformed_json"
    if not isinstance(value, Mapping):
        return None, "decision_not_object"
    try:
        decision_mode = DecisionMode(str(value.get("decision", "")).upper())
        supplied_choice = value.get("choice")
        packet_choices = {card.choice for card in packet.action_cards}
        # A weak model sometimes labels a clarification as ACTION while
        # supplying no packet choice (or inventing ``ask_user``). Treating the
        # accompanying explanation as CLARIFY is safe; accepting the invented
        # choice would not be. This is a semantic repair, never an execution
        # repair.
        if (
            decision_mode is DecisionMode.ACTION
            and supplied_choice not in packet_choices
            and (value.get("answer") or value.get("rationale"))
        ):
            decision_mode = DecisionMode.CLARIFY
        elif (
            decision_mode is DecisionMode.NEED_CONTEXT
            and value.get("context_type") not in set(packet.progress.get("allowed_context", ()))
            and (value.get("answer") or value.get("rationale"))
        ):
            # Do not let a weak model smuggle an arbitrary retrieval category
            # into the control plane. Preserve its explanation as a bounded
            # clarification instead.
            decision_mode = DecisionMode.CLARIFY
        decision = DecisionContract(
            decision=decision_mode,
            choice=supplied_choice,
            context_type=value.get("context_type"),
            ambiguity_class=(value.get("ambiguity_class") or ("unspecified" if decision_mode is DecisionMode.CLARIFY else None)),
            rationale=str(value.get("rationale"))[:240] if value.get("rationale") else None,
            # The server binds a live model response to the packet it just
            # issued. Requiring a small model to copy a 24-character digest is
            # unnecessary failure surface; a supplied digest is still checked
            # strictly for replay/stale-trace validation.
            state_fingerprint=value.get("state_fingerprint") or packet.state_fingerprint,
            answer=str(value.get("answer"))[:12000] if value.get("answer") else None,
        )
    except (ValueError, TypeError):
        return None, "invalid_decision_mode"
    valid, reason = decision.validate(packet)
    return (decision, None) if valid else (None, reason)


def classify_post_result(result: Any, *, canonical_read: bool = False,
                         unresolved_required_information: bool = False,
                         deterministic_next_step: bool = False) -> PostResultState:
    """Classify the control-plane transition after one canonical Result.

    Success alone never proves arbitrary Objective completion.  The terminal
    transition is deliberately narrow: an exact resolved canonical read with
    sufficient evidence needs only answer synthesis, not another Action choice.
    """
    if not isinstance(result, Mapping):
        return PostResultState.BLOCKED
    if result.get("approval_required"):
        return PostResultState.NEEDS_APPROVAL
    if result.get("blocked") or result.get("error") or result.get("success") is False:
        return PostResultState.BLOCKED
    if result.get("exit_code") not in (None, 0):
        return PostResultState.BLOCKED
    if unresolved_required_information:
        return PostResultState.NEEDS_CONTEXT
    if deterministic_next_step:
        return PostResultState.CONTINUE_DETERMINISTICALLY
    if canonical_read:
        return PostResultState.COMPLETE_AFTER_ANSWER
    return PostResultState.NEEDS_BOUNDED_REASONING


def model_burden(*, framework: int, model: int, labels: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Small explicit metric separating framework-resolvable work from cognition."""
    total = framework + model
    return {"framework": framework, "model": model, "total": total,
            "model_ratio": round(model / total, 4) if total else 0.0,
            "labels": dict(labels or {})}
