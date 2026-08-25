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
from core.work_models import WorkAction, WorkRun
from src.capability_registry import ApprovalMode, action_for_tool
from src.tool_bindings import binding_for_tool
from src.work_engine import WorkEngine, WorkError


_WORK_DOMAINS = frozenset({"homelab", "network_ops"})


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


def ensure_agent_run(
    owner: str,
    session_id: str,
    query: str,
    *,
    model_endpoint: str | None = None,
    model_name: str | None = None,
    intent: dict[str, Any] | None = None,
    continuation: bool = False,
) -> str | None:
    """Return or create the active owner/session run for actionable homelab work."""
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
        if active is not None and (continuation or domains.intersection(_WORK_DOMAINS)):
            return active.id
        if not domains.intersection(_WORK_DOMAINS):
            return None
        work = WorkEngine(db)
        run = work.create_run(owner, {
            "session_id": session_id,
            "domain": "network_ops" if "network_ops" in domains else "homelab",
            "requested_by": owner,
            "model_endpoint": model_endpoint,
            "model_name": model_name,
            "intent": {
                "source": "chat_agent",
                "query": str(query or "")[:4000],
                "domains": sorted(domains.intersection(_WORK_DOMAINS)),
            },
            "assumptions": [{
                "kind": "scope",
                "value": "private IPv4 discovery remains bounded by ActionSpec and broker policy",
            }],
            "continuation_state": {"source": "chat_agent", "session_id": session_id},
        })
        work.transition_run(owner, run["id"], "planning", {"current_step": "intent routed to canonical capability"})
        work.transition_run(owner, run["id"], "ready", {"current_step": "awaiting canonical action selection"})
        return run["id"]


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
            "target_resources": list(spec.target_resources),
            "preconditions": list(spec.preconditions),
            "locks": list(spec.locks),
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
        failed = bool(result.get("error")) or result.get("exit_code") not in (None, 0)
        if failed:
            action.status = "failed"
            action.error = str(result.get("error") or result.get("output") or "action failed")[:500]
            action.revision += 1
            work.event(owner, "action.failed", run_id=action.run_id, action_id=action.id, payload={"reason": action.error})
            db.commit()
            return {"action_id": action.id, "status": "failed"}
        safe_data = result.get("data")
        try:
            encoded = json.dumps(safe_data, ensure_ascii=False, default=str)
            safe_data = json.loads(encoded[:100000]) if len(encoded) <= 100000 else {"truncated": True}
        except (TypeError, ValueError):
            safe_data = None
        return work.complete_action(owner, action.id, {
            "result_reference": f"agent-tool://{action.id}",
            "result": {
                "result_type": "agent_binding_result",
                "reference": f"agent-tool://{action.id}",
                "domain_reference": safe_data,
                "metadata": {"tool_binding": action.tool_binding_name, "action": action.action_id},
                "provenance": {"source": "canonical ToolBinding", "run_id": action.run_id},
            },
        })


def mark_run_waiting(owner: str, run_id: str, *, step: str) -> None:
    with SessionLocal() as db:
        run = db.query(WorkRun).filter_by(id=str(run_id), owner=str(owner)).one_or_none()
        if run is None or run.status in {"completed", "failed", "cancelled"}:
            return
        work = WorkEngine(db)
        work.set_run_status(owner, run.id, "running", {"lifecycle_state": "planning", "current_step": step})
