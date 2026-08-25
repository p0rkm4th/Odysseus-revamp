"""Durable Work projections for first-class agent binding execution.

The chat agent still owns its streaming loop and legacy tool transport. This
module is the compatibility seam that gives registered ActionSpec/ToolBinding
operations a durable owner/session Work trajectory without duplicating their
executor. It never grants authority or accepts model-supplied executors.
"""

from __future__ import annotations

import json
from typing import Any

from core.database import SessionLocal
from core.work_models import WorkAction, WorkResult, WorkRun
from src.capability_registry import ApprovalMode, action_for_tool, capability_for_id
from src.tool_bindings import binding_for_tool
from src.work_engine import WorkEngine, WorkError, now


# These are domains whose canonical ActionSpecs are already executable through
# the shared chat/work bridge.  Keeping this list here is an adapter boundary,
# not a second registry: capability/action/binding metadata remains the source
# of authority.
_WORK_DOMAINS = frozenset({
    "homelab", "network_ops", "asset_inventory", "security_audit", "osint",
    "memory", "work", "household", "setup", "career",
    "communications",
})


def _payload(content: Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        value = dict(content)
    else:
        try:
            value = json.loads(str(content or "{}"))
        except (TypeError, ValueError):
            return None
    return value if isinstance(value, dict) else None


def _action_contract(tool_name: str, content: Any):
    binding = binding_for_tool(str(tool_name or ""))
    spec = action_for_tool(str(tool_name or ""), content)
    if binding is None or spec is None or not spec.known:
        return None, None, None
    return binding, spec, _payload(content)


def _required_prechecks(run: WorkRun, spec) -> list[str]:
    required = [str(item) for item in (spec.precheck_actions or ()) if str(item).strip()]
    if not required:
        return []
    checkpoints = [item for item in (run.checkpoints or []) if isinstance(item, dict) and item.get("kind") == "precheck"]
    return [
        action_id for action_id in required
        if not any(
            item.get("action_id") == action_id
            and (item.get("success") is True or item.get("status") in {"passed", "succeeded", "success", "verified"})
            for item in checkpoints
        )
    ]


def _continuation_state(run: WorkRun, *, action_id: str | None = None, phase: str | None = None, **extra) -> dict[str, Any]:
    """Persist the small server-owned continuation pointer for one Run."""
    state = dict(run.continuation_state or {})
    if action_id is not None:
        state["pending_action_id"] = action_id
    elif "pending_action_id" in state:
        state["pending_action_id"] = None
    if phase is not None:
        state["phase"] = phase
    state.update({key: value for key, value in extra.items() if value is not None})
    return state


def _state_invalidations(action: WorkAction, spec) -> list[dict[str, Any]]:
    """Translate declarative invalidation tokens into scoped claim keys."""
    payload = action.normalized_input if isinstance(action.normalized_input, dict) else {}
    if action.action_id == "execute_service_restart":
        service = str(payload.get("service") or "").strip()
        if not service:
            return []
        return [{"subject_ref": f"service:{service}", "predicate": token.split(".", 1)[-1]} for token in spec.state_invalidations]
    if action.action_id == "execute_network_discovery":
        cidr = str(payload.get("cidr") or "private_scope").strip()
        return [{"subject_ref": f"network:{cidr}", "predicate": token.split(".", 1)[-1]} for token in spec.state_invalidations]
    if action.action_id == "execute_network_service_enumeration":
        return [{"subject_ref": "network:private_scope", "predicate": token.split(".", 1)[-1]} for token in spec.state_invalidations]
    if action.action_id == "execute_diagnostic_install":
        capability = str(payload.get("capability") or "diagnostic_packages").strip()
        return [{"subject_ref": f"capability:{capability}", "predicate": token.split(".", 1)[-1]} for token in spec.state_invalidations]
    return []


def ensure_agent_run(
    owner: str,
    session_id: str,
    query: str,
    *,
    model_endpoint: str | None = None,
    model_name: str | None = None,
    intent: dict[str, Any] | None = None,
    continuation: bool = False,
    completion_criteria: dict[str, Any] | None = None,
) -> str | None:
    """Return or create the active owner/session Run for bridged agent work."""
    owner = str(owner or "").strip()
    session_id = str(session_id or "").strip()
    if not owner or not session_id:
        return None
    domains = set((intent or {}).get("domains") or ())
    with SessionLocal() as db:
        active = (
            db.query(WorkRun)
            .filter(
                WorkRun.owner == owner,
                WorkRun.session_id == session_id,
                WorkRun.domain.in_(tuple(_WORK_DOMAINS)),
                WorkRun.status.in_(("queued", "running", "awaiting_approval", "awaiting_input", "suspended")),
            )
            .order_by(WorkRun.updated_at.desc())
            .first()
        )
        if active is not None and (
            continuation or active.domain in domains.intersection(_WORK_DOMAINS)
        ):
            requested_model = str(model_name or "").strip() or None
            requested_endpoint = str(model_endpoint or "").strip() or None
            if requested_model or requested_endpoint:
                previous_model = str(active.model_name or "").strip() or None
                previous_endpoint = str(active.model_endpoint or "").strip() or None
                if (requested_model and requested_model != previous_model) or (
                    requested_endpoint and requested_endpoint != previous_endpoint
                ):
                    state = dict(active.continuation_state or {})
                    history = [
                        item for item in (state.get("model_history") or [])
                        if isinstance(item, dict)
                    ]
                    if not history and (previous_model or previous_endpoint):
                        history.append({
                            "model_name": previous_model,
                            "model_endpoint": previous_endpoint,
                            "role": "initial",
                        })
                    history.append({
                        "model_name": requested_model or previous_model,
                        "model_endpoint": requested_endpoint or previous_endpoint,
                        "role": "continuation",
                        "recorded_at": now().isoformat(),
                    })
                    active.model_name = requested_model or previous_model
                    active.model_endpoint = requested_endpoint or previous_endpoint
                    active.continuation_state = {
                        **state,
                        "model_history": history[-20:],
                        "active_model": {
                            "model_name": active.model_name,
                            "model_endpoint": active.model_endpoint,
                        },
                    }
                    active.revision += 1
                    WorkEngine(db).event(
                        owner,
                        "run.model_switched",
                        run_id=active.id,
                        payload={
                            "from_model": previous_model,
                            "to_model": active.model_name,
                            "from_endpoint": previous_endpoint,
                            "to_endpoint": active.model_endpoint,
                        },
                    )
                    db.commit()
            return active.id
        bridged_domains = domains.intersection(_WORK_DOMAINS)
        if not bridged_domains:
            return None
        semantic_domain = str((intent or {}).get("domain_concept") or "").strip().lower()
        domain_name = {
            "technical_asset": "asset_inventory",
            "security_finding": "security_audit",
            "osint_case": "osint",
            "household_item": "household",
            "job_opportunity": "career",
            "job_application": "career",
            "interview": "career",
        }.get(semantic_domain, "")
        if domain_name not in bridged_domains:
            domain_name = "network_ops" if "network_ops" in bridged_domains else sorted(bridged_domains)[0]
        is_read = str((intent or {}).get("operation_class") or "").upper() == "READ"
        work = WorkEngine(db)
        run = work.create_run(owner, {
            "session_id": session_id,
            "domain": domain_name,
            "requested_by": owner,
            "model_endpoint": model_endpoint,
            "model_name": model_name,
            "intent": {
                "source": "chat_agent",
                "query": str(query or "")[:4000],
                "domains": sorted(bridged_domains),
                "domain_concept": (intent or {}).get("domain_concept"),
                "operation_class": (intent or {}).get("operation_class"),
            },
            "completion_criteria": completion_criteria or {
                "objective": str(query or "")[:4000],
                "deliverable": "canonical read result" if is_read else "canonical network/homelab result",
                "completion_mode": "single_verified_read" if is_read else "verified_run_terminal_state",
            },
            "assumptions": ([{
                "kind": "scope",
                "value": "private IPv4 discovery remains bounded by ActionSpec and broker policy",
            }] if "network_ops" in bridged_domains else []),
            "continuation_state": {
                "source": "chat_agent",
                "session_id": session_id,
                "model_history": ([{
                    "model_name": model_name,
                    "model_endpoint": model_endpoint,
                    "role": "initial",
                }] if model_name or model_endpoint else []),
                "active_model": {
                    "model_name": model_name,
                    "model_endpoint": model_endpoint,
                } if model_name or model_endpoint else {},
            },
        })
        work.transition_run(owner, run["id"], "planning", {"current_step": "intent routed to canonical capability"})
        work.transition_run(owner, run["id"], "ready", {"current_step": "awaiting canonical action selection"})
        return run["id"]


def record_agent_model_observation(
    owner: str,
    run_id: str,
    *,
    model_name: str | None = None,
    model_endpoint: str | None = None,
) -> dict[str, Any] | None:
    """Persist the provider that actually served a durable agent round.

    The requested route and the serving route can differ when foreground
    fallback is used.  Keep that fact on the owner-scoped Run so continuation
    and model swapping operate on observed provenance rather than stale
    request metadata.  This records metadata only; it grants no capability
    and does not alter the compiled plan or approval state.
    """
    owner = str(owner or "").strip()
    run_id = str(run_id or "").strip()
    observed_model = str(model_name or "").strip() or None
    observed_endpoint = str(model_endpoint or "").strip() or None
    if not owner or not run_id or not (observed_model or observed_endpoint):
        return None
    with SessionLocal() as db:
        run = db.query(WorkRun).filter_by(id=run_id, owner=owner).one_or_none()
        if run is None:
            return None
        current_model = str(run.model_name or "").strip() or None
        current_endpoint = str(run.model_endpoint or "").strip() or None
        if observed_model == current_model and observed_endpoint == current_endpoint:
            return {
                "run_id": run.id,
                "model_name": current_model,
                "model_endpoint": current_endpoint,
                "changed": False,
            }
        state = dict(run.continuation_state or {})
        history = [
            item for item in (state.get("model_history") or [])
            if isinstance(item, dict)
        ]
        if not history and (current_model or current_endpoint):
            history.append({
                "model_name": current_model,
                "model_endpoint": current_endpoint,
                "role": "initial",
            })
        history.append({
            "model_name": observed_model or current_model,
            "model_endpoint": observed_endpoint or current_endpoint,
            "role": "observed",
            "recorded_at": now().isoformat(),
        })
        run.model_name = observed_model or current_model
        run.model_endpoint = observed_endpoint or current_endpoint
        run.continuation_state = {
            **state,
            "model_history": history[-20:],
            "active_model": {
                "model_name": run.model_name,
                "model_endpoint": run.model_endpoint,
            },
        }
        run.revision += 1
        WorkEngine(db).event(
            owner,
            "run.model_observed",
            run_id=run.id,
            payload={
                "from_model": current_model,
                "to_model": run.model_name,
                "from_endpoint": current_endpoint,
                "to_endpoint": run.model_endpoint,
            },
        )
        db.commit()
        return {
            "run_id": run.id,
            "model_name": run.model_name,
            "model_endpoint": run.model_endpoint,
            "changed": True,
        }


def assess_agent_run(owner: str, run_id: str) -> dict[str, Any] | None:
    """Expose the shared durable completion decision to chat/UI adapters."""
    with SessionLocal() as db:
        run = db.query(WorkRun).filter_by(id=str(run_id), owner=str(owner)).one_or_none()
        if run is None:
            return None
        return WorkEngine(db).assess_deliverable_completion(owner, run.id)


def continuation_run_projection(owner: str, run_id: str) -> dict[str, Any] | None:
    """Return the minimal owner-scoped Run projection needed by continuation.

    This is read-only state for the semantic resolver. It deliberately omits
    result payloads and never changes lifecycle, approval, or Action state.
    """
    with SessionLocal() as db:
        run = db.query(WorkRun).filter_by(id=str(run_id), owner=str(owner)).one_or_none()
        if run is None:
            return None
        actions = (
            db.query(WorkAction)
            .filter_by(run_id=run.id)
            .order_by(WorkAction.sequence.asc(), WorkAction.id.asc())
            .all()
        )
        results = (
            db.query(WorkResult)
            .filter_by(run_id=run.id, owner=owner)
            .order_by(WorkResult.created_at.asc(), WorkResult.id.asc())
            .all()
        )
        references = []
        for result in results:
            data = result.domain_reference if isinstance(result.domain_reference, dict) else {}
            for item in data.get("canonical_refs", data.get("entity_refs", [])):
                if isinstance(item, dict) and str(item.get("ref") or item.get("id") or "").strip():
                    references.append({
                        "ref": str(item.get("ref") or item.get("id"))[:500],
                        "concept": str(item.get("concept") or "").strip()[:80] or None,
                    })
            if isinstance(data.get("refs"), list):
                for ref in data["refs"]:
                    if isinstance(ref, str) and ref.strip():
                        references.append({"ref": ref.strip()[:500]})
        projection = {
            "id": run.id,
            "owner": run.owner,
            "status": run.status,
            "lifecycle_state": run.lifecycle_state,
            "continuation_state": dict(run.continuation_state or {}),
            "reference_context": {
                "entities": references[-100:],
                "last": references[-1] if references else None,
            },
            "actions": [
                {"id": action.id, "status": action.status, "sequence": action.sequence}
                for action in actions
            ],
        }
        # Reuse the canonical durable planner for continuation decisions.  It
        # is observational here: no Action is materialized, approved, or
        # executed.  If a malformed/incomplete Run cannot be projected, keep
        # continuation fail-closed instead of inventing a next step.
        try:
            from src.run_planner import RunPlanner
            projection["next_step"] = RunPlanner(db).next_step(owner, run.id)
        except Exception as exc:
            projection["next_step"] = {
                "status": "UNAVAILABLE",
                "reason": "durable next-step projection unavailable",
                "error_class": type(exc).__name__,
            }
        return projection


def safe_auto_continuation(
    owner: str,
    run_id: str,
    *,
    allowed_tools: set[str] | None = None,
    disabled_tools: set[str] | None = None,
) -> dict[str, Any] | None:
    """Project one already-safe read-only Run step for automatic execution.

    This is intentionally narrower than continuation resolution.  It may only
    return the next Action when the canonical planner has established that it
    is READY, read-only, approval-free, and bound to a currently available
    ToolBinding.  It never creates an Action, advances a Run, or widens scope.
    The caller still executes the returned binding through the normal policy
    and executor path.
    """
    projection = continuation_run_projection(owner, run_id)
    if not isinstance(projection, dict):
        return None
    next_step = projection.get("next_step")
    if not isinstance(next_step, dict):
        return None
    if next_step.get("status") != "READY" or next_step.get("safe_auto_continue") is not True:
        return None
    action = next_step.get("action")
    if not isinstance(action, dict):
        return None
    binding = str(action.get("tool_binding_name") or "").strip()
    action_id = str(action.get("action_id") or "").strip()
    if not binding or not action_id:
        return None
    if allowed_tools is not None and binding not in allowed_tools:
        return None
    if disabled_tools and binding in disabled_tools:
        return None
    payload = action.get("normalized_input")
    if not isinstance(payload, dict):
        payload = {}
    payload = dict(payload)
    payload.setdefault("action", action_id)
    target_resources = [
        str(item).strip()
        for item in (action.get("target_resources") or [])
        if str(item).strip()
    ]
    if target_resources:
        # Internal metadata lets prepare_action preserve the compiled plan's
        # exact scope without asking the model to know the executor schema.
        payload["_hades_target_resources"] = target_resources
    return {
        "run_id": str(run_id),
        "tool": binding,
        "action_id": action_id,
        "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        "target_resources": target_resources,
    }


def prepare_action(
    owner: str,
    run_id: str,
    tool_name: str,
    content: Any,
    *,
    approval_reference: str | None = None,
) -> str | None:
    """Persist or recover a bound ActionSpec action for one agent tool block."""
    binding, spec, payload = _action_contract(tool_name, content)
    if binding is None or spec is None or payload is None:
        return None
    with SessionLocal() as db:
        work = WorkEngine(db)
        run = db.query(WorkRun).filter_by(id=str(run_id), owner=str(owner)).one_or_none()
        if run is None:
            return None
        capability = capability_for_id(binding.capability_id)
        registered_spec = capability.actions.get(spec.action_id) if capability else None
        if registered_spec is not None:
            missing = _required_prechecks(run, registered_spec)
            if missing:
                work.set_run_status(
                    owner, run.id, "awaiting_input",
                    {"lifecycle_state": "waiting_input", "current_step": f"precheck required: {', '.join(missing)}"},
                )
                return None
        if spec.action_id in {"plan_network_service_enumeration", "execute_network_service_enumeration"} and not payload.get("targets"):
            discovery = (
                db.query(WorkResult)
                .join(WorkAction, WorkAction.id == WorkResult.action_id)
                .filter(
                    WorkResult.owner == owner, WorkResult.run_id == run.id,
                    WorkAction.action_id == "execute_network_discovery",
                )
                .order_by(WorkResult.created_at.desc())
                .first()
            )
            data = discovery.domain_reference if discovery and isinstance(discovery.domain_reference, dict) else {}
            candidates = data.get("asset_draft_candidates") or []
            # A discovered CMDB draft may represent a multi-homed host.  The
            # service-enumeration Action must inherit the complete discovered
            # target set, not an arbitrary first address per candidate.
            targets: list[str] = []
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                addresses = item.get("ip_addresses") or []
                if isinstance(addresses, str):
                    addresses = [addresses]
                for address in addresses:
                    target = str(address or "").strip()
                    if target and target not in targets:
                        targets.append(target)
                    if len(targets) >= 256:
                        break
                if len(targets) >= 256:
                    break
            if targets:
                payload["targets"] = targets
        planned_resources = payload.pop("_hades_target_resources", None)
        target_resources = list(spec.target_resources)
        if isinstance(planned_resources, list):
            for resource in planned_resources:
                value = str(resource or "").strip()
                if value and value not in target_resources:
                    target_resources.append(value)
        locks = list(spec.locks)
        if spec.action_id == "execute_service_restart":
            service = str(payload.get("service") or "").strip()
            if service:
                target_resources.append(f"service:{service}")
                locks.append(f"service:{service}")
        if spec.action_id == "execute_diagnostic_install":
            capability_name = str(payload.get("capability") or "diagnostic_packages").strip()
            target_resources.append(f"capability:{capability_name}")
        if approval_reference:
            existing = (
                db.query(WorkAction)
                .filter_by(run_id=run.id, approval_reference=str(approval_reference))
                .first()
            )
            if existing is not None:
                return existing.id
        status = "awaiting_approval" if spec.approval is ApprovalMode.EXACT and approval_reference else "proposed"
        action = work.create_action(owner, run.id, {
            "capability_id": binding.capability_id,
            "action_id": spec.action_id,
            "tool_binding_name": binding.transport_name,
            "effect_class": spec.effects[0] if spec.effects else "internal",
            "normalized_input": payload,
            "target_resources": target_resources,
            "preconditions": list(spec.preconditions),
            "locks": locks,
            "risk_level": spec.risk_level,
            "retry_policy": dict(spec.retry_policy or {}),
            "timeout_seconds": spec.timeout_seconds,
            "rollback_capability": spec.rollback_capability,
            "compensating_action": spec.compensating_action,
            "postconditions": list(spec.postconditions),
            "verification": list(spec.verification),
            "status": status,
            "approval_reference": approval_reference,
        })
        work.set_run_status(owner, run.id, "awaiting_approval" if status == "awaiting_approval" else "running", {
            "lifecycle_state": "waiting_approval" if status == "awaiting_approval" else "planning",
            "current_step": f"canonical action: {spec.action_id}",
            "continuation_state": _continuation_state(
                run, action_id=action["id"],
                phase="AWAITING_APPROVAL" if status == "awaiting_approval" else "PROPOSED",
            ),
        })
        return action["id"]


def bind_approval(owner: str, action_id: str, approval_reference: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        return WorkEngine(db).bind_approval(owner, action_id, approval_reference)


def resume_approval(owner: str, action_id: str, approval_reference: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        return WorkEngine(db).resume_approved_action(owner, action_id, approval_reference)


def record_result(owner: str, action_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
    """Persist a bounded structured result projection; never persist raw output here."""
    if not isinstance(result, dict):
        return None
    with SessionLocal() as db:
        action = (
            db.query(WorkAction)
            .join(WorkRun)
            .filter(WorkAction.id == str(action_id), WorkRun.owner == str(owner))
            .one_or_none()
        )
        if action is None:
            return None
        work = WorkEngine(db)
        run = db.query(WorkRun).filter_by(id=action.run_id, owner=str(owner)).one()
        criteria = run.completion_criteria if isinstance(run.completion_criteria, dict) else {}
        single_read = action.effect_class == "read_private" and criteria.get("completion_mode") in {"single_verified_read", "single_read"}
        failed = bool(result.get("error")) or result.get("exit_code") not in (None, 0)
        if failed:
            if result.get("execution_ambiguous") and str(action.action_id or "").startswith("execute_"):
                # A broker may have completed while the durable CMDB/world
                # projection failed. Preserve the unknown outcome and retain
                # the run's safety state until independent evidence resolves
                # it; never collapse this into an ordinary execution failure.
                return work.mark_action_ambiguous(
                    owner,
                    action.id,
                    reason=str(result.get("persistence_error") or result.get("error") or "post-action state is unknown"),
                )
            action.status = "failed"
            action.error = str(result.get("error") or result.get("output") or "action failed")[:500]
            action.revision += 1
            work.event(owner, "action.failed", run_id=action.run_id, action_id=action.id, payload={"reason": action.error})
            db.commit()
            # A failed consequential binding must not leave its durable Run
            # advertising a still-planning operation. This is a lifecycle
            # projection only; the existing executor remains authoritative for
            # policy, approval, broker execution, and any ambiguity signal.
            if str(action.action_id or "").startswith("execute_"):
                work.verified_execution_step(
                    owner, action.run_id, "failed",
                    reason="bound ActionSpec execution failed",
                    failure_class="execution_failed",
                )
            elif single_read:
                work.fail_read_deliverable(owner, action.run_id, reason=action.error)
            return {"action_id": action.id, "status": "failed"}
        safe_data = result.get("data")
        try:
            encoded = json.dumps(safe_data, ensure_ascii=False, default=str)
            safe_data = json.loads(encoded[:100000]) if len(encoded) <= 100000 else {"truncated": True}
        except (TypeError, ValueError):
            safe_data = None
        completed = work.complete_action(owner, action.id, {
            "result_reference": f"agent-tool://{action.id}",
            "result": {
                "result_type": "agent_binding_result",
                "reference": f"agent-tool://{action.id}",
                "domain_reference": safe_data,
                "metadata": {"tool_binding": action.tool_binding_name, "action": action.action_id},
                "provenance": {"source": "canonical ToolBinding", "run_id": action.run_id},
            },
        })
        canonical_status = str((safe_data or {}).get("status") or "").upper() if isinstance(safe_data, dict) else ""
        if single_read and canonical_status in {"DEGRADED", "UNAVAILABLE", "FAILED", "INVALID_RESULT"}:
            # The binding returned a durable Result, but the canonical read
            # did not produce usable truth. Preserve that Result for evidence
            # while keeping the Run out of the succeeded state; a provider
            # outage must never become an empty or successful read.
            completed["read_completion"] = work.fail_read_deliverable(
                owner, action.run_id,
                reason=(safe_data or {}).get("reason") or (safe_data or {}).get("error") or f"canonical read returned {canonical_status}",
            )
            return completed
        # Keep the durable continuation pointer honest. A completed read is
        # terminal for its Run; a consequential result moves the Run into
        # verification and must remain resumable by the shared lifecycle.
        refreshed_run = db.query(WorkRun).filter_by(id=action.run_id, owner=str(owner)).one()
        if str(action.action_id or "").startswith("execute_"):
            refreshed_run.continuation_state = _continuation_state(
                refreshed_run, action_id=action.id, phase="VERIFYING",
            )
        else:
            refreshed_run.continuation_state = _continuation_state(
                refreshed_run, action_id=None, phase="COMPLETE",
            )
        db.commit()
        if str(action.action_id or "").startswith("plan_"):
            # A successful plan is durable precheck evidence for a later
            # consequential action in the same Run. Keep only structured
            # references, never raw provider output, in the checkpoint.
            work.record_precheck(owner, action.run_id, {
                "action_id": action.action_id,
                "status": "passed",
                "success": True,
                "result_reference": f"agent-tool://{action.id}",
                "operation_digest": safe_data.get("operation_digest") if isinstance(safe_data, dict) else None,
            })
        # A result proves that the binding returned; it does not prove the
        # desired postcondition. Consequential Actions therefore advance the
        # same canonical lifecycle to VERIFYING and remain incomplete until a
        # verifier records success (or explicit compensation/failure).
        if str(action.action_id or "").startswith("execute_"):
            if action.status == "completed":
                work.verified_execution_step(
                    owner, action.run_id, "ready",
                    reason="approval and bound result recorded",
                )
            lifecycle = work.verified_execution_step(
                owner, action.run_id, "executing",
                reason="bound ActionSpec returned; verification required",
            )
            capability = capability_for_id(action.capability_id)
            registered_spec = capability.actions.get(action.action_id) if capability else None
            invalidations = _state_invalidations(action, registered_spec) if registered_spec else []
            if invalidations:
                work.invalidate_state(
                    owner, action.run_id, invalidations,
                    reason="consequential action completed; current observations require refresh",
                )
            lifecycle = work.verified_execution_step(
                owner, action.run_id, "verifying",
                reason="post-action verification required",
            )
            completed["run_lifecycle_state"] = lifecycle["lifecycle_state"]
        elif single_read:
            completed["read_completion"] = work.complete_read_deliverable(
                owner, action.run_id, action.id, result=safe_data,
            )
        return completed


def verify_bound_action(owner: str, action_id: str) -> dict[str, Any] | None:
    """Run the deterministic verifier for a completed bound action.

    This first verifier is intentionally narrow: network discovery can be
    verified from the structured result only after the canonical CMDB writer
    reports both required projection postconditions. It never interprets
    model prose or treats a broker exit code as desired-state success.
    """
    with SessionLocal() as db:
        action = (
            db.query(WorkAction)
            .join(WorkRun)
            .filter(WorkAction.id == str(action_id), WorkRun.owner == str(owner))
            .one_or_none()
        )
        if action is None or not str(action.action_id or "").startswith("execute_"):
            return None
        if action.status != "completed":
            return {"verified": False, "reason": "action is not completed"}
        result = db.query(WorkResult).filter_by(action_id=action.id, run_id=action.run_id, owner=str(owner)).one_or_none()
        if result is None:
            return {"verified": False, "reason": "structured action result is missing"}
        data = result.domain_reference if isinstance(result.domain_reference, dict) else {}
        required = tuple(action.verification or ())
        if action.action_id == "execute_network_discovery":
            checks = {
                "observations_persisted": data.get("observations_recorded") is True,
                "network_map_reconciled": data.get("network_map_reconciled") is True,
            }
            missing = [name for name in required if not checks.get(name, False)]
            work = WorkEngine(db)
            if missing:
                outcome = work.complete_verification(
                    str(owner), action.run_id, success=False,
                    details={"checks": checks, "missing": missing, "verifier": "network_discovery_projection"},
                )
                return {"verified": False, "checks": checks, "missing": missing, "run_lifecycle_state": outcome["lifecycle_state"]}
            outcome = work.complete_verification(
                str(owner), action.run_id, success=True,
                details={"checks": checks, "observation_count": data.get("observation_count", 0), "verifier": "network_discovery_projection"},
            )
            return {"verified": True, "checks": checks, "run_lifecycle_state": outcome["lifecycle_state"]}
        if action.action_id == "execute_network_service_enumeration":
            checks = {
                "service_observations_persisted": data.get("observations_recorded") is True,
                "network_map_reconciled": data.get("network_map_reconciled") is True,
            }
            missing = [name for name in required if not checks.get(name, False)]
            work = WorkEngine(db)
            outcome = work.complete_verification(
                str(owner), action.run_id, success=not missing,
                details={"checks": checks, "missing": missing, "observation_count": data.get("observation_count", 0), "verifier": "network_service_observation"},
            )
            return {"verified": not missing, "checks": checks, "missing": missing, "run_lifecycle_state": outcome["lifecycle_state"]}
        if action.action_id == "execute_service_restart":
            checks = {
                "service_active": data.get("success") is True
                and data.get("verification_exit_code") == 0
                and str(data.get("verification_output") or "").strip() == "active",
            }
            missing = [name for name in required if not checks.get(name, False)]
            work = WorkEngine(db)
            if missing:
                outcome = work.complete_verification(
                    str(owner), action.run_id, success=False,
                    details={"checks": checks, "missing": missing, "verifier": "service_restart_status"},
                )
                return {"verified": False, "checks": checks, "missing": missing, "run_lifecycle_state": outcome["lifecycle_state"]}
            outcome = work.complete_verification(
                str(owner), action.run_id, success=True,
                details={"checks": checks, "service": (action.normalized_input or {}).get("service"), "verifier": "service_restart_status"},
            )
            return {"verified": True, "checks": checks, "run_lifecycle_state": outcome["lifecycle_state"]}
        if action.action_id == "execute_diagnostic_install":
            broker_result = data.get("broker_result") if isinstance(data.get("broker_result"), dict) else {}
            verification = broker_result.get("verification") if isinstance(broker_result.get("verification"), dict) else {}
            checks = {
                "prerequisites_verified": data.get("verified_prerequisites") is True
                and verification.get("ok") is True,
            }
            missing = [name for name in required if not checks.get(name, False)]
            work = WorkEngine(db)
            if missing:
                outcome = work.complete_verification(
                    str(owner), action.run_id, success=False,
                    details={"checks": checks, "missing": missing, "verifier": "diagnostic_executable_verification"},
                )
                return {"verified": False, "checks": checks, "missing": missing, "run_lifecycle_state": outcome["lifecycle_state"]}
            outcome = work.complete_verification(
                str(owner), action.run_id, success=True,
                details={"checks": checks, "capability": (action.normalized_input or {}).get("capability"), "verifier": "diagnostic_executable_verification"},
            )
            return {"verified": True, "checks": checks, "run_lifecycle_state": outcome["lifecycle_state"]}
        return {"verified": False, "reason": "no deterministic verifier registered"}


def mark_run_waiting(owner: str, run_id: str, *, step: str) -> None:
    with SessionLocal() as db:
        run = db.query(WorkRun).filter_by(id=str(run_id), owner=str(owner)).one_or_none()
        if run is None or run.status in {"completed", "failed", "cancelled"}:
            return
        work = WorkEngine(db)
        work.set_run_status(owner, run.id, "running", {"lifecycle_state": "planning", "current_step": step})
