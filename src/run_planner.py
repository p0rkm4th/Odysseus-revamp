"""Deterministic Run preview and validation projections.

This module is deliberately a projection over WorkEngine and the canonical
capability registry.  It does not execute actions, grant authority, or create
another plan/action store.
"""
from __future__ import annotations

from dataclasses import asdict
import ipaddress
from typing import Any

from src.capability_registry import ActionSpec, ApprovalMode, capability_for_id
from core.work_models import WorkAction, WorkLock, WorkRun
from src.work_engine import WorkEngine, WorkError, serialize


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _private_network_resource(value: Any) -> bool:
    text = str(value or "")
    if not text.startswith("network:"):
        return False
    name = text[8:]
    if name in {"private_scope", "private", "loopback"}:
        return True
    try:
        return ipaddress.ip_network(name, strict=False).is_private
    except ValueError:
        return False


def _contract(spec: ActionSpec, action: dict[str, Any] | None = None) -> dict[str, Any]:
    action = action or {}
    return {
        "effects": list(spec.effects),
        "reads": list(spec.reads),
        "writes": list(spec.writes),
        "effect_class": action.get("effect_class") or (spec.effects[0] if spec.effects else "internal"),
        "target_scope": spec.target_scope,
        "target_resources": list(action.get("target_resources") or spec.target_resources),
        "preconditions": list(action.get("preconditions") or spec.preconditions),
        "locks": list(action.get("locks") or spec.locks),
        "risk_level": action.get("risk_level") or spec.risk_level,
        "blast_radius": list(spec.blast_radius),
        "approval": spec.approval.value,
        "expected_cost": dict(spec.expected_cost or {}),
        "expected_downtime": dict(spec.expected_downtime or {}),
        "idempotency": action.get("idempotency") or spec.idempotency,
        "retry_policy": dict(action.get("retry_policy") or spec.retry_policy or {}),
        "timeout_seconds": action.get("timeout_seconds") or spec.timeout_seconds,
        "rollback_capability": action.get("rollback_capability") or spec.rollback_capability,
        "compensating_action": action.get("compensating_action") or spec.compensating_action,
        "reversible": spec.reversible,
        "compensatable": spec.compensatable,
        "irreversible": spec.irreversible,
        "state_invalidations": list(spec.state_invalidations),
        "postconditions": list(action.get("postconditions") or spec.postconditions),
        "verification": list(action.get("verification") or spec.verification),
        "precheck_actions": list(spec.precheck_actions),
        "execution_location": spec.execution_location,
        "executor_key": spec.executor_key,
    }


class RunPlanner:
    def __init__(self, db):
        self.db = db
        self.work = WorkEngine(db)

    def _run(self, owner: str, run_id: str) -> WorkRun:
        return self.db.query(WorkRun).filter_by(owner=owner, id=run_id).one_or_none() or (_ for _ in ()).throw(WorkError("run not found"))

    def _actions(self, run: WorkRun) -> list[dict[str, Any]]:
        persisted = self.db.query(WorkAction).filter_by(run_id=run.id).order_by(WorkAction.sequence, WorkAction.id).all()
        if persisted:
            return [serialize(row) for row in persisted]
        plan = run.plan if isinstance(run.plan, list) else []
        return [dict(item, sequence=index) for index, item in enumerate(plan, 1) if isinstance(item, dict)]

    def _spec(self, action: dict[str, Any]) -> tuple[Any, ActionSpec | None]:
        capability = capability_for_id(str(action.get("capability_id") or ""))
        return capability, capability.actions.get(str(action.get("action_id") or "")) if capability else None

    def compile(self, owner: str, run_id: str) -> dict[str, Any]:
        run = self._run(owner, run_id)
        actions = self._actions(run)
        compiled: list[dict[str, Any]] = []
        reads: list[str] = []
        writes: list[str] = []
        resources: list[str] = []
        approvals: list[dict[str, Any]] = []
        assumptions = list(run.assumptions or []) if isinstance(run.assumptions, list) else []
        unknowns: list[dict[str, Any]] = []
        risks: list[str] = []
        for action in actions:
            capability, spec = self._spec(action)
            if spec is None:
                item = {"sequence": action.get("sequence"), "capability_id": action.get("capability_id"), "action_id": action.get("action_id"), "known": False, "validation_status": "unknown_action"}
                compiled.append(item)
                continue
            contract = _contract(spec, action)
            item = {"sequence": action.get("sequence"), "action_id": action.get("id"), "operation": spec.action_id, "capability_id": capability.capability_id, "known": True, "status": action.get("status"), "input": action.get("normalized_input") or {}, "contract": contract}
            if action.get("approval_reference"):
                item["approval_reference"] = action["approval_reference"]
            if spec.approval is not ApprovalMode.NONE:
                approvals.append({"sequence": action.get("sequence"), "action_id": spec.action_id, "mode": spec.approval.value, "reference": action.get("approval_reference"), "status": "bound" if action.get("approval_reference") else "required"})
            reads.extend(x for x in contract["reads"] if x not in reads)
            writes.extend(x for x in contract["writes"] if x not in writes)
            resources.extend(x for x in contract["target_resources"] + contract["locks"] if x not in resources)
            if contract["risk_level"] not in risks:
                risks.append(contract["risk_level"])
            compiled.append(item)
        gaps = []
        required = []
        for item in compiled:
            required.extend(x for x in item.get("contract", {}).get("preconditions", []) if isinstance(x, dict))
        if required:
            gap_result = self.work.knowledge_gaps(owner, required)
            gaps = gap_result.get("stale", []) + gap_result.get("unknown", [])
        blast_radius = []
        if resources:
            from src.world_model import WorldModelService
            world = WorldModelService(self.db)
            seen_focus = set()
            for resource in resources[:50]:
                focus = str(resource)
                if focus in seen_focus: continue
                seen_focus.add(focus)
                projection = world.blast_radius(owner, focus, limit=100)
                if projection.get("confirmed") or projection.get("likely") or projection.get("unknown"):
                    blast_radius.append(projection)
        lock_state = []
        for lock in self.db.query(WorkLock).filter_by(owner=owner, released_at=None).all():
            lock_state.append(serialize(lock))
        return {
            "preview_version": 1, "run_id": run.id, "owner": owner,
            "objective": run.intent or {}, "domain": run.domain,
            "actions": compiled, "reads": reads, "writes": writes,
            "resources": resources, "assumptions": assumptions,
            "knowledge_gaps": gaps, "unknowns": gaps,
            "risk": risks, "blast_radius": [], "approvals": approvals,
            "locks": lock_state, "blast_radius": blast_radius, "verification": run.verification or {},
            "lifecycle_state": run.lifecycle_state, "plan_revision": run.revision,
        }

    def validate(self, owner: str, run_id: str) -> dict[str, Any]:
        preview = self.compile(owner, run_id)
        failures: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        run = self._run(owner, run_id)
        actions = self._actions(run)
        for item, action in zip(preview["actions"], actions):
            if not item.get("known"):
                failures.append({"code": "unknown_action_spec", "sequence": action.get("sequence"), "message": "ActionSpec is not registered"})
                continue
            contract = item["contract"]
            if contract["target_scope"] == "private_network":
                invalid = [r for r in contract["target_resources"] if not _private_network_resource(r)]
                if invalid:
                    failures.append({"code": "scope_invalid", "sequence": action.get("sequence"), "message": "private-network action has an out-of-scope resource", "resources": invalid})
            if contract["approval"] != "none" and not action.get("approval_reference") and action.get("status") not in {"approved", "completed"}:
                failures.append({"code": "approval_required", "sequence": action.get("sequence"), "message": "exact or normal approval is not bound"})
            if contract["risk_level"] in {"high", "critical"} and not contract["verification"]:
                failures.append({"code": "verification_required", "sequence": action.get("sequence"), "message": "higher-risk action has no verification contract"})
            if contract["compensatable"] and not contract["compensating_action"]:
                failures.append({"code": "compensation_missing", "sequence": action.get("sequence"), "message": "action claims compensation without a compensation contract"})
            for gap in preview["knowledge_gaps"]:
                requirement = gap.get("requirement") or {}
                if requirement in contract["preconditions"]:
                    failures.append({"code": "knowledge_gap", "sequence": action.get("sequence"), "message": "required state is stale or unknown", "gap": gap})
            if contract["irreversible"]:
                warnings.append({"code": "irreversible", "sequence": action.get("sequence"), "message": "action cannot be undone"})
        return {"valid": not failures, "failures": failures, "warnings": warnings, "preview": preview}
