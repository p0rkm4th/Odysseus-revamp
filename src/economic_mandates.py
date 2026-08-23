"""Fail-closed policy primitives for supervised economic work.

This module deliberately has no database, network, scheduler, or tool dependencies.
It describes authority; it does not perform an action.  Callers must validate a
mandate again immediately before use and separately obtain any required approval.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


ECONOMIC_POLICY_VERSION = "economic-mandate-v1"
MAX_MANDATE_LIFETIME_SECONDS = 31 * 24 * 60 * 60


class AutonomyTier(str, Enum):
    """Closed, immutable authority tiers.  New tiers require a policy release."""

    OFF = "off"
    OBSERVE = "observe"
    PREPARE = "prepare"
    BOUNDED_EXECUTION = "bounded_execution"


class EconomicAction(str, Enum):
    RESEARCH_OPPORTUNITY = "research_opportunity"
    MONITOR_OPPORTUNITY = "monitor_opportunity"
    RECONCILE_PAYMENT_READ_ONLY = "reconcile_payment_read_only"
    DRAFT_PROPOSAL = "draft_proposal"
    DRAFT_DELIVERABLE = "draft_deliverable"
    SUBMIT_PROPOSAL = "submit_proposal"
    SEND_MESSAGE = "send_message"
    PUBLISH_CONTENT = "publish_content"
    DELIVER_WORK = "deliver_work"
    SIGN_CONTRACT = "sign_contract"
    ACCEPT_TERMS = "accept_terms"
    PURCHASE = "purchase"
    TRANSFER_FUNDS = "transfer_funds"
    CHANGE_PAYOUT = "change_payout"
    PERFORM_IDENTITY_VERIFICATION = "perform_identity_verification"
    BYPASS_CAPTCHA = "bypass_captcha"
    FILE_TAX = "file_tax"
    MASS_OUTREACH = "mass_outreach"
    CREATE_DECEPTIVE_CONTENT = "create_deceptive_content"
    USE_FAKE_CREDENTIALS = "use_fake_credentials"


class ActionDisposition(str, Enum):
    AUTONOMOUS = "autonomous"
    ALWAYS_APPROVAL = "always_approval"
    FORBIDDEN = "forbidden"


_OBSERVE_ACTIONS = frozenset({
    EconomicAction.RESEARCH_OPPORTUNITY,
    EconomicAction.MONITOR_OPPORTUNITY,
    EconomicAction.RECONCILE_PAYMENT_READ_ONLY,
})
_PREPARE_ACTIONS = frozenset({
    EconomicAction.DRAFT_PROPOSAL,
    EconomicAction.DRAFT_DELIVERABLE,
})
_ALWAYS_APPROVAL_ACTIONS = frozenset({
    EconomicAction.SUBMIT_PROPOSAL,
    EconomicAction.SEND_MESSAGE,
    EconomicAction.PUBLISH_CONTENT,
    EconomicAction.DELIVER_WORK,
})
_FORBIDDEN_ACTIONS = frozenset({
    EconomicAction.SIGN_CONTRACT,
    EconomicAction.ACCEPT_TERMS,
    EconomicAction.PURCHASE,
    EconomicAction.TRANSFER_FUNDS,
    EconomicAction.CHANGE_PAYOUT,
    EconomicAction.PERFORM_IDENTITY_VERIFICATION,
    EconomicAction.BYPASS_CAPTCHA,
    EconomicAction.FILE_TAX,
    EconomicAction.MASS_OUTREACH,
    EconomicAction.CREATE_DECEPTIVE_CONTENT,
    EconomicAction.USE_FAKE_CREDENTIALS,
})


def classify_economic_action(action: EconomicAction | str) -> ActionDisposition:
    """Classify a closed-set action; unknown values fail closed as forbidden."""
    try:
        normalized = action if isinstance(action, EconomicAction) else EconomicAction(str(action))
    except (TypeError, ValueError):
        return ActionDisposition.FORBIDDEN
    if normalized in _FORBIDDEN_ACTIONS:
        return ActionDisposition.FORBIDDEN
    if normalized in _ALWAYS_APPROVAL_ACTIONS:
        return ActionDisposition.ALWAYS_APPROVAL
    return ActionDisposition.AUTONOMOUS


@dataclass(frozen=True)
class BudgetLimits:
    external_actions: int = 0
    messages: int = 0
    submissions: int = 0
    gross_spend_minor: int = 0
    committed_value_minor: int = 0

    def __post_init__(self) -> None:
        for name, value in self.as_dict().items():
            if type(value) is not int or value < 0:  # bool is intentionally rejected
                raise ValueError(f"budget limit {name} must be a non-negative integer")

    def as_dict(self) -> dict[str, int]:
        return {
            "committed_value_minor": self.committed_value_minor,
            "external_actions": self.external_actions,
            "gross_spend_minor": self.gross_spend_minor,
            "messages": self.messages,
            "submissions": self.submissions,
        }


@dataclass(frozen=True)
class BudgetUsage:
    external_actions: int = 0
    messages: int = 0
    submissions: int = 0
    gross_spend_minor: int = 0
    committed_value_minor: int = 0

    def __post_init__(self) -> None:
        for name, value in self.as_dict().items():
            if type(value) is not int or value < 0:
                raise ValueError(f"budget usage {name} must be a non-negative integer")

    def as_dict(self) -> dict[str, int]:
        return {
            "committed_value_minor": self.committed_value_minor,
            "external_actions": self.external_actions,
            "gross_spend_minor": self.gross_spend_minor,
            "messages": self.messages,
            "submissions": self.submissions,
        }


@dataclass(frozen=True)
class EconomicMandate:
    mandate_id: str
    owner: str
    autonomy_tier: AutonomyTier = AutonomyTier.OFF
    allowed_actions: tuple[EconomicAction, ...] = ()
    budgets: BudgetLimits = BudgetLimits()
    issued_at: int = 0
    expires_at: int = 0
    policy_version: str = ECONOMIC_POLICY_VERSION

    @classmethod
    def create(
        cls,
        *,
        mandate_id: str,
        owner: str,
        autonomy_tier: AutonomyTier | str = AutonomyTier.OFF,
        allowed_actions: Iterable[EconomicAction | str] = (),
        budgets: BudgetLimits | None = None,
        issued_at: int,
        expires_at: int,
        policy_version: str = ECONOMIC_POLICY_VERSION,
    ) -> "EconomicMandate":
        try:
            tier = autonomy_tier if isinstance(autonomy_tier, AutonomyTier) else AutonomyTier(autonomy_tier)
            actions = tuple(sorted(
                {a if isinstance(a, EconomicAction) else EconomicAction(str(a)) for a in allowed_actions},
                key=lambda item: item.value,
            ))
        except (TypeError, ValueError) as exc:
            raise ValueError("mandate contains an unknown tier or action") from exc
        mandate = cls(
            mandate_id=str(mandate_id).strip(), owner=str(owner).strip(),
            autonomy_tier=tier, allowed_actions=actions,
            budgets=budgets or BudgetLimits(), issued_at=issued_at,
            expires_at=expires_at, policy_version=str(policy_version),
        )
        validate_mandate(mandate)
        return mandate

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "allowed_actions": [action.value for action in self.allowed_actions],
            "autonomy_tier": self.autonomy_tier.value,
            "budgets": self.budgets.as_dict(),
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "mandate_id": self.mandate_id,
            "owner": self.owner,
            "policy_version": self.policy_version,
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def validate_mandate(mandate: EconomicMandate, *, now: int | None = None) -> None:
    if not isinstance(mandate, EconomicMandate):
        raise ValueError("economic mandate is required")
    if not mandate.owner or mandate.owner != mandate.owner.strip():
        raise ValueError("mandate owner is required")
    if not mandate.mandate_id:
        raise ValueError("mandate id is required")
    if mandate.policy_version != ECONOMIC_POLICY_VERSION:
        raise ValueError("mandate policy version is unsupported")
    if type(mandate.issued_at) is not int or type(mandate.expires_at) is not int:
        raise ValueError("mandate timestamps must be integer Unix seconds")
    if mandate.issued_at <= 0 or mandate.expires_at <= mandate.issued_at:
        raise ValueError("mandate expiry must be after issuance")
    if mandate.expires_at - mandate.issued_at > MAX_MANDATE_LIFETIME_SECONDS:
        raise ValueError("mandate lifetime exceeds policy maximum")
    if now is not None and mandate.expires_at <= now:
        raise ValueError("mandate is expired")
    if not isinstance(mandate.autonomy_tier, AutonomyTier):
        raise ValueError("mandate autonomy tier is invalid")
    if not isinstance(mandate.budgets, BudgetLimits):
        raise ValueError("mandate budgets are invalid")
    if (
        not isinstance(mandate.allowed_actions, tuple)
        or not all(isinstance(action, EconomicAction) for action in mandate.allowed_actions)
        or tuple(sorted(set(mandate.allowed_actions), key=lambda item: item.value))
        != mandate.allowed_actions
    ):
        raise ValueError("mandate actions must be known, unique, and canonical")
    if any(classify_economic_action(action) is ActionDisposition.FORBIDDEN for action in mandate.allowed_actions):
        raise ValueError("mandate cannot grant a forbidden action")


@dataclass(frozen=True)
class EconomicRuntimeControls:
    """Runtime revocation state.  The kill switch is engaged by default."""

    kill_switch_engaged: bool = True
    revoked_mandate_digests: frozenset[str] = frozenset()


@dataclass(frozen=True)
class EconomicPolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str
    mandate_digest: str = ""
    policy_version: str = ECONOMIC_POLICY_VERSION


_TIER_RANK = {
    AutonomyTier.OFF: 0,
    AutonomyTier.OBSERVE: 1,
    AutonomyTier.PREPARE: 2,
    AutonomyTier.BOUNDED_EXECUTION: 3,
}


def _required_tier(action: EconomicAction) -> AutonomyTier:
    if action in _OBSERVE_ACTIONS:
        return AutonomyTier.OBSERVE
    if action in _PREPARE_ACTIONS:
        return AutonomyTier.PREPARE
    return AutonomyTier.BOUNDED_EXECUTION


def evaluate_economic_action(
    mandate: EconomicMandate | None,
    action: EconomicAction | str,
    *,
    usage_after_action: BudgetUsage,
    controls: EconomicRuntimeControls | None = None,
    owner: str,
    now: int | None = None,
) -> EconomicPolicyDecision:
    """Evaluate authority without performing or approving an external action."""
    runtime = controls or EconomicRuntimeControls()
    if not isinstance(runtime, EconomicRuntimeControls):
        return EconomicPolicyDecision(False, False, "economic runtime controls are invalid")
    if (
        type(runtime.kill_switch_engaged) is not bool
        or not isinstance(runtime.revoked_mandate_digests, frozenset)
        or not all(isinstance(item, str) for item in runtime.revoked_mandate_digests)
    ):
        return EconomicPolicyDecision(False, False, "economic runtime controls are invalid")
    if mandate is None:
        return EconomicPolicyDecision(False, False, "economic mode is not configured")
    try:
        validate_mandate(mandate, now=int(time.time()) if now is None else now)
    except (TypeError, ValueError) as exc:
        return EconomicPolicyDecision(False, False, str(exc))
    digest = mandate.digest
    if runtime.kill_switch_engaged:
        return EconomicPolicyDecision(False, False, "economic kill switch is engaged", digest)
    if digest in runtime.revoked_mandate_digests:
        return EconomicPolicyDecision(False, False, "economic mandate is revoked", digest)
    if not isinstance(owner, str) or not owner or owner.strip() != mandate.owner:
        return EconomicPolicyDecision(False, False, "economic mandate owner mismatch", digest)
    try:
        normalized = action if isinstance(action, EconomicAction) else EconomicAction(str(action))
    except (TypeError, ValueError):
        return EconomicPolicyDecision(False, False, "unknown economic action", digest)
    disposition = classify_economic_action(normalized)
    if disposition is ActionDisposition.FORBIDDEN:
        return EconomicPolicyDecision(False, False, "economic action is forbidden", digest)
    if normalized not in mandate.allowed_actions:
        return EconomicPolicyDecision(False, False, "economic action is outside the mandate", digest)
    if _TIER_RANK[mandate.autonomy_tier] < _TIER_RANK[_required_tier(normalized)]:
        return EconomicPolicyDecision(False, False, "mandate autonomy tier is insufficient", digest)
    if not isinstance(usage_after_action, BudgetUsage):
        return EconomicPolicyDecision(False, False, "projected budget usage is invalid", digest)
    exceeded = [
        name for name, value in usage_after_action.as_dict().items()
        if value > mandate.budgets.as_dict()[name]
    ]
    if exceeded:
        return EconomicPolicyDecision(
            False, False, f"economic budget exceeded: {', '.join(sorted(exceeded))}", digest,
        )
    if disposition is ActionDisposition.ALWAYS_APPROVAL:
        return EconomicPolicyDecision(False, True, "exact user approval is required", digest)
    return EconomicPolicyDecision(True, False, "economic action is within the active mandate", digest)
