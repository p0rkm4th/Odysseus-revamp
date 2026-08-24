"""Fail-closed delegated capability grant service."""
from datetime import timedelta
from core.delegated_grant_models import DelegatedCapabilityGrant
from core.work_models import WorkAction, WorkRun
from src.work_engine import WorkError, ident, now, parse_dt, serialize


class DelegatedGrantService:
    def __init__(self, db): self.db = db

    def _action(self, owner, action_id):
        row = self.db.query(WorkAction).join(WorkRun).filter(WorkAction.id == action_id, WorkRun.owner == owner).one_or_none()
        if row is None: raise WorkError("action not found")
        return row

    def issue(self, owner, action_id, data):
        action = self._action(owner, action_id); run = self.db.query(WorkRun).filter_by(owner=owner, id=action.run_id).one()
        approval = str(data.get("approval_reference") or "")
        digest = str(data.get("sealed_input_digest") or "")
        if not action.approval_reference or approval != action.approval_reference: raise WorkError("grant requires the exact action approval")
        if not digest or digest != action.sealed_input_digest: raise WorkError("grant digest does not match the sealed action input")
        expires = parse_dt(data.get("expires_at"))
        if expires is None or expires <= now(): raise WorkError("grant expiry must be in the future")
        max_calls = int(data.get("max_calls", 1))
        if max_calls < 1 or max_calls > 10: raise WorkError("grant max_calls must be between 1 and 10")
        row = DelegatedCapabilityGrant(id=ident("grant"), owner=owner, run_id=run.id, action_id=action.id, capability_id=action.capability_id, target_resources=list(action.target_resources or []), parameter_constraints=data.get("parameter_constraints") or {}, sealed_input_digest=digest, approval_reference=approval, max_calls=max_calls, expires_at=expires)
        self.db.add(row); self.db.commit(); self.db.refresh(row); return serialize(row)

    def list(self, owner, *, active_only=False, limit=200):
        query = self.db.query(DelegatedCapabilityGrant).filter_by(owner=owner)
        if active_only: query = query.filter(DelegatedCapabilityGrant.revoked_at == None, DelegatedCapabilityGrant.expires_at > now())
        return [serialize(row) for row in query.order_by(DelegatedCapabilityGrant.created_at.desc()).limit(max(1, min(int(limit), 500))).all()]

    def consume(self, owner, grant_id, data):
        row = self.db.query(DelegatedCapabilityGrant).filter_by(owner=owner, id=grant_id).one_or_none()
        if row is None: raise WorkError("grant not found")
        if row.revoked_at is not None: raise WorkError("grant is revoked")
        if row.expires_at <= now(): raise WorkError("grant is expired")
        if row.consumed_calls >= row.max_calls: raise WorkError("grant call limit exceeded")
        for key in ("run_id", "action_id", "capability_id", "sealed_input_digest"):
            if str(data.get(key) or "") != str(getattr(row, key)): raise WorkError("grant scope mismatch")
        target = data.get("target_resource")
        if target and target not in (row.target_resources or []): raise WorkError("grant target scope mismatch")
        row.consumed_calls += 1; row.consumed_at = now(); self.db.commit(); self.db.refresh(row)
        return {"grant": serialize(row), "authorized": True, "authority_unchanged": True}

    def revoke(self, owner, grant_id):
        row = self.db.query(DelegatedCapabilityGrant).filter_by(owner=owner, id=grant_id).one_or_none()
        if row is None: raise WorkError("grant not found")
        row.revoked_at = now(); self.db.commit(); self.db.refresh(row); return serialize(row)
