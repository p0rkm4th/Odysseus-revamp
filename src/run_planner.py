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
from src.tool_bindings import binding_for_tool
from core.work_models import WorkAction, WorkGoal, WorkLock, WorkRun
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
        "execution_requirements": dict(spec.execution_requirements or {}),
        "execution_location": spec.execution_location,
        "executor_key": spec.executor_key,
        "execution_path": _execution_path(spec, action),
    }


def _execution_path(spec: ActionSpec, action: dict[str, Any]) -> dict[str, Any]:
    """Describe the registered execution boundary without invoking it.

    ToolBindings are optional for application-owned projections such as Work
    and routing.  When a binding is declared or the ActionSpec names a
    registered transport, however, the preview must expose the exact binding
    and validation must fail closed on mismatches.
    """
    declared = str(action.get("tool_binding_name") or "").strip()
    executor = str(spec.executor_key or "").strip()
    binding = binding_for_tool(declared or executor) if (declared or executor) else None
    binding_name = declared or (binding.transport_name if binding else None)
    if declared and binding is None:
        return {"available": False, "binding": declared, "executor_key": executor or None, "reason": "binding_not_registered"}
    if binding and executor and binding.executor_key != executor:
        return {"available": False, "binding": binding.transport_name, "executor_key": executor, "reason": "executor_binding_mismatch"}
    if binding and binding.capability_id != "":
        return {
            "available": True,
            "binding": binding.transport_name,
            "executor_key": binding.executor_key,
            "execution_location": binding.execution_location,
            "target_scope": binding.target_scope,
            "direct_container_access": binding.requires_direct_container_access,
        }
    if executor:
        # No ToolBinding means this remains an application-owned path.  The
        # executor key is still visible for policy/observability, but is not
        # mistaken for a host or external authority boundary.
        return {"available": True, "binding": None, "executor_key": executor, "execution_location": spec.execution_location, "application_owned": True}
    return {"available": True, "binding": None, "executor_key": None, "execution_location": spec.execution_location, "application_owned": True}


class RunPlanner:
    def __init__(self, db):
        self.db = db
        self.work = WorkEngine(db)

    def _run(self, owner: str, run_id: str) -> WorkRun:
        return self.db.query(WorkRun).filter_by(owner=owner, id=run_id).one_or_none() or (_ for _ in ()).throw(WorkError("run not found"))

    def _actions(self, run: WorkRun) -> list[dict[str, Any]]:
        persisted = self.db.query(WorkAction).filter_by(run_id=run.id).order_by(WorkAction.sequence, WorkAction.id).all()
        persisted_rows = [serialize(row) for row in persisted]
        plan = run.plan if isinstance(run.plan, list) else []
        projected = []
        persisted_sequences = {int(item.get("sequence") or 0) for item in persisted_rows}
        for index, item in enumerate(plan, 1):
            if not isinstance(item, dict):
                continue
            sequence = int(item.get("sequence") or index)
            # Persisted Actions are authoritative for their sequence.  Keep
            # later declared plan steps visible even before they are
            # materialized, otherwise a completed first step makes the
            # planner falsely report the Run complete/no-next-step.
            if sequence in persisted_sequences:
                continue
            projected.append(dict(item, sequence=sequence, status=item.get("status") or "proposed"))
        return sorted(persisted_rows + projected, key=lambda item: (int(item.get("sequence") or 0), str(item.get("id") or "")))

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
        targets: list[str] = []
        effect_classes: list[str] = []
        capability_health: list[dict[str, Any]] = []
        reversibility: list[dict[str, Any]] = []
        prechecks: list[dict[str, Any]] = []
        for action in actions:
            capability, spec = self._spec(action)
            if spec is None:
                item = {"sequence": action.get("sequence"), "capability_id": action.get("capability_id"), "action_id": action.get("action_id"), "known": False, "validation_status": "unknown_action"}
                compiled.append(item)
                capability_health.append({"capability_id": action.get("capability_id"), "status": "unavailable", "reason": "action_spec_missing"})
                continue
            contract = _contract(spec, action)
            sequence = action.get("sequence")
            recorded = [
                checkpoint for checkpoint in (run.checkpoints or [])
                if isinstance(checkpoint, dict)
                and checkpoint.get("kind") == "precheck"
                and (checkpoint.get("sequence") is None or checkpoint.get("sequence") == sequence)
                and (checkpoint.get("action_id") in {None, *contract["precheck_actions"]})
            ]
            required_prechecks = []
            for precheck_action in contract["precheck_actions"]:
                matches = [entry for entry in recorded if entry.get("action_id") == precheck_action]
                required_prechecks.append({
                    "action_id": precheck_action,
                    "recorded": matches,
                    "satisfied": any(entry.get("status") in {"passed", "succeeded", "success", "verified"} or entry.get("success") is True for entry in matches),
                })
            if required_prechecks:
                prechecks.append({"sequence": sequence, "action_id": spec.action_id, "required": required_prechecks})
            item = {"sequence": sequence, "action_id": action.get("id"), "operation": spec.action_id, "capability_id": capability.capability_id, "known": True, "status": action.get("status"), "input": action.get("normalized_input") or {}, "contract": contract, "prechecks": required_prechecks}
            if action.get("approval_reference"):
                item["approval_reference"] = action["approval_reference"]
            if spec.approval is not ApprovalMode.NONE:
                approvals.append({"sequence": action.get("sequence"), "action_id": spec.action_id, "mode": spec.approval.value, "reference": action.get("approval_reference"), "status": "bound" if action.get("approval_reference") else "required"})
            reads.extend(x for x in contract["reads"] if x not in reads)
            writes.extend(x for x in contract["writes"] if x not in writes)
            resources.extend(x for x in contract["target_resources"] + contract["locks"] if x not in resources)
            targets.extend(x for x in contract["target_resources"] if x not in targets)
            if contract["effect_class"] not in effect_classes:
                effect_classes.append(contract["effect_class"])
            capability_health.append({"capability_id": capability.capability_id, "status": "available", "actions": [spec.action_id]})
            reversibility.append({"sequence": action.get("sequence"), "action_id": spec.action_id, "reversible": contract["reversible"], "compensatable": contract["compensatable"], "irreversible": contract["irreversible"], "compensation": contract["compensating_action"] or contract["rollback_capability"] or None})
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
            "actions": compiled, "targets": targets, "target_entities": targets, "reads": reads, "writes": writes,
            "resources": resources, "assumptions": assumptions,
            "knowledge_gaps": gaps, "unknowns": gaps, "effect_classes": effect_classes,
            "capability_health": capability_health, "reversibility": reversibility,
            "risk": risks, "blast_radius": [], "approvals": approvals,
            "locks": lock_state, "blast_radius": blast_radius, "verification": run.verification or {}, "prechecks": prechecks,
            "lifecycle_state": run.lifecycle_state, "plan_revision": run.revision,
        }

    def validate(self, owner: str, run_id: str, *, focus_sequence: int | None = None) -> dict[str, Any]:
        """Validate a compiled Run, optionally focusing execution checks.

        Full validation remains the default for previews and plan gates. A
        trusted executor may focus validation on the current persisted Action
        so future declared steps do not block the present step with their
        not-yet-due approval or precheck requirements.
        """
        preview = self.compile(owner, run_id)
        failures: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        run = self._run(owner, run_id)
        actions = self._actions(run)
        mission_allowed = None
        if run.goal_id:
            goal = self.db.query(WorkGoal).filter_by(owner=owner, id=run.goal_id).one_or_none()
            constraints = (goal.constraints or {}) if goal and isinstance(goal.constraints, dict) else {}
            if str(constraints.get("operating_mode") or "").lower() == "mission":
                configured = constraints.get("allowed_capabilities")
                mission_allowed = {str(item) for item in configured if str(item).strip()} if isinstance(configured, list) else set()
        for item, action in zip(preview["actions"], actions):
            is_focus = focus_sequence is None or int(action.get("sequence") or 0) == int(focus_sequence)
            if not item.get("known"):
                failures.append({"code": "unknown_action_spec", "sequence": action.get("sequence"), "message": "ActionSpec is not registered"})
                continue
            contract = item["contract"]
            normalized_input = action.get("normalized_input")
            if normalized_input is not None and not isinstance(normalized_input, dict):
                failures.append({"code": "invalid_action_input", "sequence": action.get("sequence"), "message": "normalized action input must be an object"})
            execution_path = contract.get("execution_path") or {}
            if not execution_path.get("available", False):
                failures.append({"code": "execution_path_unavailable", "sequence": action.get("sequence"), "message": "declared ActionSpec execution path is unavailable", "path": execution_path})
            if contract["target_scope"] and not contract["target_resources"]:
                failures.append({"code": "target_required", "sequence": action.get("sequence"), "message": "scoped action requires a canonical target resource"})
            if mission_allowed and str(action.get("capability_id") or "") not in mission_allowed:
                failures.append({"code": "mission_capability_restricted", "sequence": action.get("sequence"), "capability_id": action.get("capability_id"), "message": "Run Action capability is not allowed by its Mission"})
            if contract["precheck_actions"]:
                capability, _ = self._spec(action)
                for requirement in item.get("prechecks", []):
                    precheck_action = str(requirement.get("action_id") or "")
                    if capability is None or precheck_action not in capability.actions:
                        failures.append({"code": "precheck_action_missing", "sequence": action.get("sequence"), "action_id": precheck_action, "message": "declared precheck ActionSpec is not registered"})
                    elif is_focus and not requirement.get("satisfied"):
                        failures.append({"code": "precheck_required", "sequence": action.get("sequence"), "action_id": precheck_action, "message": "declared precheck has not produced successful evidence"})
            requirements = contract.get("execution_requirements") or {}
            if requirements:
                from src.execution_nodes import ExecutionNodeService
                selection = ExecutionNodeService(self.db).select(owner, requirements)
                if not selection.get("eligible"):
                    failures.append({"code": "execution_node_unavailable", "sequence": action.get("sequence"), "message": "no eligible execution node satisfies the ActionSpec requirements", "requirements": requirements, "rejected": selection.get("rejected", [])})
            if contract["target_scope"] == "private_network":
                invalid = [r for r in contract["target_resources"] if not _private_network_resource(r)]
                if invalid:
                    failures.append({"code": "scope_invalid", "sequence": action.get("sequence"), "message": "private-network action has an out-of-scope resource", "resources": invalid})
            if is_focus and contract["approval"] != "none" and not action.get("approval_reference") and action.get("status") not in {"approved", "completed"}:
                failures.append({"code": "approval_required", "sequence": action.get("sequence"), "message": "exact or normal approval is not bound"})
            if contract["approval"] == "exact" and action.get("approval_reference") and not action.get("sealed_input_digest"):
                failures.append({"code": "approval_digest_missing", "sequence": action.get("sequence"), "message": "exact approval is not bound to a sealed action-input digest"})
            if contract["risk_level"] in {"high", "critical"} and not contract["verification"]:
                failures.append({"code": "verification_required", "sequence": action.get("sequence"), "message": "higher-risk action has no verification contract"})
            if contract["compensatable"] and not contract["compensating_action"]:
                failures.append({"code": "compensation_missing", "sequence": action.get("sequence"), "message": "action claims compensation without a compensation contract"})
            if is_focus and action.get("id"):
                conflicts = self.work.lock_conflicts(owner, action["id"])
                if conflicts:
                    failures.append({"code": "lock_conflict", "sequence": action.get("sequence"), "message": "declared resources are currently locked", "locks": conflicts})
            for gap in preview["knowledge_gaps"]:
                requirement = gap.get("requirement") or {}
                if is_focus and requirement in contract["preconditions"]:
                    failures.append({"code": "knowledge_gap", "sequence": action.get("sequence"), "message": "required state is stale or unknown", "gap": gap})
            if contract["irreversible"]:
                warnings.append({"code": "irreversible", "sequence": action.get("sequence"), "message": "action cannot be undone"})
        return {"valid": not failures, "failures": failures, "warnings": warnings, "preview": preview}

    def next_step(self, owner: str, run_id: str) -> dict[str, Any]:
        """Project the next durable Run step without advancing or authorizing it.

        This is intentionally a resolver, not an executor.  It gives chat and
        the UI one model-independent answer to ``what happens next?`` while
        preserving exact approval, verification, and owner-scope boundaries.
        """
        run = self._run(owner, run_id)
        actions = self._actions(run)
        base = {"run_id": run.id, "lifecycle_state": run.lifecycle_state, "run_status": run.status}
        if run.status == "completed" and run.lifecycle_state == "succeeded":
            return base | {"status": "COMPLETE", "action": None, "reason": "run reached verified terminal success", "safe_auto_continue": False, "authority_required": False}
        if run.status in {"failed", "cancelled"} or run.lifecycle_state in {"failed", "cancelled", "execution_ambiguous", "partial_unknown_state"} or (run.continuation_state or {}).get("execution_ambiguous"):
            return base | {"status": "BLOCKED", "action": None, "reason": run.error_summary or "run is not safely continuable", "safe_auto_continue": False, "authority_required": False}
        if run.status == "awaiting_input" or run.lifecycle_state == "waiting_input":
            return base | {"status": "WAITING_INPUT", "action": None, "reason": run.current_step or "operator input is required", "safe_auto_continue": False, "authority_required": False}
        if run.lifecycle_state in {"verifying", "compensating"}:
            return base | {"status": "VERIFYING", "action": None, "reason": run.current_step or "postcondition verification is required", "safe_auto_continue": False, "authority_required": False}

        # Persisted actions are authoritative; plan entries are projected by
        # _actions when a Run has not materialized its actions yet.
        pending = [action for action in actions if action.get("status") not in {"completed", "failed", "rejected", "cancelled", "expired"}]
        if not pending:
            if actions and all(action.get("status") == "completed" for action in actions):
                return base | {"status": "COMPLETE", "action": None, "reason": "all declared Run actions completed", "safe_auto_continue": False, "authority_required": False}
            if not actions:
                return base | {"status": "NO_PLAN", "action": None, "reason": "Run has no declared actions", "safe_auto_continue": False, "authority_required": False}
            return base | {"status": "BLOCKED", "action": None, "reason": "Run contains a failed or rejected action", "safe_auto_continue": False, "authority_required": False}

        action = sorted(pending, key=lambda item: (int(item.get("sequence") or 0), str(item.get("id") or "")))[0]
        action_status = str(action.get("status") or "proposed")
        sequence = action.get("sequence")
        projected = {"id": action.get("id"), "sequence": action.get("sequence"), "capability_id": action.get("capability_id"), "action_id": action.get("action_id"), "status": action_status, "target_resources": list(action.get("target_resources") or []), "normalized_input": action.get("normalized_input") or {}}
        if action_status == "awaiting_approval" or run.status == "awaiting_approval" or run.lifecycle_state == "waiting_approval":
            return base | {"status": "WAITING_APPROVAL", "action": projected, "reason": "exact action authority is required", "safe_auto_continue": False, "authority_required": True}
        if action_status == "executing":
            return base | {"status": "IN_PROGRESS", "action": projected, "reason": "action is already executing", "safe_auto_continue": False, "authority_required": False}
        if action_status == "approved":
            # An approved Action has already crossed its authority boundary.
            # Revalidate the exact persisted contract before allowing the
            # shared loop to advance it automatically; this never grants or
            # reuses approval and still fails closed on stale prerequisites.
            validation = self.validate(owner, run_id, focus_sequence=sequence)
            failures = [failure for failure in validation["failures"] if failure.get("sequence") == sequence]
            if failures:
                return base | {"status": "BLOCKED", "action": projected, "reason": "approved Action cannot pass current Run validation", "safe_auto_continue": False, "authority_required": False, "validation": {"failures": failures, "warnings": validation["warnings"]}}
            capability = capability_for_id(str(action.get("capability_id") or ""))
            spec = capability.actions.get(str(action.get("action_id") or "")) if capability else None
            authority_bound = bool(
                spec and (
                    spec.approval.value == "none"
                    or (action.get("approval_reference") and action.get("sealed_input_digest"))
                )
            )
            return base | {"status": "READY", "action": projected, "reason": "exactly approved Action is ready for the trusted executor", "safe_auto_continue": authority_bound, "authority_required": False, "validation": {"failures": [], "warnings": validation["warnings"]}}

        validation = self.validate(owner, run_id)
        failures = [failure for failure in validation["failures"] if failure.get("sequence") == sequence]
        if failures:
            approval_only = all(failure.get("code") == "approval_required" for failure in failures)
            if approval_only:
                return base | {"status": "WAITING_APPROVAL", "action": projected, "reason": "exact action authority is required", "safe_auto_continue": False, "authority_required": True, "validation": {"failures": failures, "warnings": validation["warnings"]}}
            return base | {"status": "BLOCKED", "action": projected, "reason": "next Action cannot pass Run validation", "safe_auto_continue": False, "authority_required": False, "validation": {"failures": failures, "warnings": validation["warnings"]}}
        contract = next((item.get("contract") for item in validation["preview"]["actions"] if item.get("sequence") == sequence), {})
        capability = capability_for_id(str(action.get("capability_id") or ""))
        spec = capability.actions.get(str(action.get("action_id") or "")) if capability else None
        binding = binding_for_tool(str(spec.executor_key or "")) if spec and spec.executor_key else None
        if binding is not None:
            projected["tool_binding_name"] = binding.transport_name
        read_only = contract.get("approval") == "none" and not contract.get("writes") and contract.get("effect_class") in {"read_private", "read_only", "read", "internal"}
        return base | {"status": "READY", "action": projected, "reason": "next declared Action is valid", "safe_auto_continue": bool(read_only), "authority_required": False, "validation": {"failures": [], "warnings": validation["warnings"]}}
