"""Canonical owner-scoped Career service and provider normalization boundary."""
from __future__ import annotations
import hashlib
import json
from typing import Any, Mapping
from core.career_models import CareerProfile, JobApplication, JobInterview, JobOpportunity, JobSearch
from src.career_providers import provider_status, providers
from src.work_engine import WorkError, ident, serialize


class CareerService:
    def __init__(self, db):
        self.db = db

    def _owner(self, owner):
        if not str(owner or "").strip():
            raise WorkError("career owner is required")
        return str(owner)

    def overview(self, owner):
        owner = self._owner(owner)
        profile = self.db.query(CareerProfile).filter_by(owner=owner).first()
        searches = self.db.query(JobSearch).filter_by(owner=owner).order_by(JobSearch.updated_at.desc()).limit(50).all()
        opportunities = self.db.query(JobOpportunity).filter_by(owner=owner).order_by(JobOpportunity.updated_at.desc()).limit(100).all()
        applications = self.db.query(JobApplication).filter_by(owner=owner).order_by(JobApplication.updated_at.desc()).limit(100).all()
        interviews = self.db.query(JobInterview).filter_by(owner=owner).order_by(JobInterview.updated_at.desc()).limit(100).all()
        status = "SUCCESS" if any((profile, searches, opportunities, applications, interviews)) else "EMPTY_RESULT"
        return {"status": status, "provider": provider_status(), "profile": serialize(profile) if profile else None,
                "searches": [serialize(x) for x in searches], "opportunities": [serialize(x) for x in opportunities],
                "applications": [serialize(x) for x in applications], "interviews": [serialize(x) for x in interviews]}

    def read(self, owner, action, payload=None):
        owner = self._owner(owner); payload = payload or {}
        if action in {"overview", "state"}: return self.overview(owner)
        if action == "saved_opportunities":
            rows = self.db.query(JobOpportunity).filter_by(owner=owner, state="saved").order_by(JobOpportunity.updated_at.desc()).all()
            return {"status": "SUCCESS" if rows else "EMPTY_RESULT", "opportunities": [serialize(x) for x in rows]}
        if action == "applications":
            rows = self.db.query(JobApplication).filter_by(owner=owner).order_by(JobApplication.updated_at.desc()).all()
            return {"status": "SUCCESS" if rows else "EMPTY_RESULT", "applications": [serialize(x) for x in rows]}
        if action == "follow_ups":
            rows = self.db.query(JobApplication).filter(JobApplication.owner == owner, JobApplication.follow_up_at.isnot(None)).order_by(JobApplication.follow_up_at.asc()).all()
            return {"status": "SUCCESS" if rows else "EMPTY_RESULT", "applications": [serialize(x) for x in rows]}
        if action == "interviews":
            rows = self.db.query(JobInterview).filter_by(owner=owner).order_by(JobInterview.starts_at.asc()).all()
            return {"status": "SUCCESS" if rows else "EMPTY_RESULT", "interviews": [serialize(x) for x in rows]}
        if action == "provider_status": return {"status": "SUCCESS", "provider": provider_status()}
        raise WorkError("unsupported Career read action")

    def normalize_opportunity(self, owner, data: Mapping[str, Any], provider_id: str):
        owner = self._owner(owner)
        title = str(data.get("title") or "").strip()
        employer = str(data.get("employer") or data.get("company") or "").strip()
        external_id = str(data.get("external_id") or data.get("url") or "").strip()
        if not title or not external_id: raise WorkError("provider opportunity requires title and stable external identity")
        dedup = hashlib.sha256(f"{provider_id}|{external_id}".encode()).hexdigest()
        row = self.db.query(JobOpportunity).filter_by(owner=owner, dedup_key=dedup).one_or_none()
        if row is None:
            row = JobOpportunity(id=ident("job"), owner=owner, dedup_key=dedup, title=title[:500], employer=employer[:500], location=str(data.get("location") or "")[:500], description=str(data.get("description") or "")[:20000], normalized=dict(data), provider_refs=[{"provider": provider_id, "external_id": external_id}], source=provider_id)
            self.db.add(row)
        else:
            row.title, row.employer, row.location, row.description, row.normalized = title[:500], employer[:500], str(data.get("location") or "")[:500], str(data.get("description") or "")[:20000], dict(data)
        self.db.commit(); self.db.refresh(row)
        return serialize(row)
