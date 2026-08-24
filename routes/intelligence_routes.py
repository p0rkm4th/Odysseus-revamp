"""Authenticated local-model, routing, developer lease, and Network APIs."""
from __future__ import annotations
import asyncio
import hashlib, ipaddress
from fastapi import APIRouter, Body, HTTPException, Request
from core.database import SessionLocal
from src.auth_helpers import require_user
from src.owner_identity import effective_storage_owner
from src import local_intelligence
from src import developer_mode
from src.network_projection import map_projection
from src.capability_dependencies import capability_health, supported_capabilities
from src.persistent_agent import PersistentAgent
from core.persistent_agent_models import Episode, Lesson, Monitor, Notification
from datetime import datetime, timezone, timedelta

def setup_intelligence_routes(*, session_factory=SessionLocal):
    router=APIRouter(tags=["local-intelligence"])
    def owner(request):
        value=effective_storage_owner(require_user(request))
        if not value: raise HTTPException(401,"authenticated owner required")
        return value
    @router.get("/api/intelligence/profiles")
    async def profiles(request: Request):
        value = owner(request)
        return {"profiles":local_intelligence.profiles(),"default":"strong-default","owner":value}
    @router.post("/api/intelligence/route")
    async def route(request: Request,payload:dict=Body(...)):
        value=owner(request); result=local_intelligence.route_request(payload.get("text",""),requested_profile=payload.get("profile"),execution_profile=payload.get("execution_profile","host")); result["owner"]=value; return result
    @router.post("/api/intelligence/infer")
    async def infer(request: Request,payload:dict=Body(...)):
        owner(request); profile=str(payload.get("profile") or "hades-local-test")
        try:return await asyncio.to_thread(local_intelligence.infer,profile,payload.get("messages") or [])
        except Exception as exc: raise HTTPException(502,"local model inference unavailable") from exc
    @router.get("/api/intelligence/capabilities")
    async def capabilities(request: Request):
        value = owner(request)
        return {
            "owner": value,
            "capabilities": [capability_health(name) for name in supported_capabilities()],
            "registry": "bounded_first_class_only",
        }
    @router.get("/api/hades/status")
    async def hades_status(request: Request):
        value = owner(request)
        with session_factory() as db:
            return PersistentAgent(db).self_context(value)
    @router.get("/api/hades/self")
    async def hades_self(request: Request):
        value = owner(request)
        with session_factory() as db:
            return PersistentAgent(db).self_context(value)
    @router.get("/api/hades/runtime")
    async def hades_runtime(request: Request):
        value = owner(request)
        with session_factory() as db:
            return PersistentAgent(db).runtime_snapshot(value)
    @router.get("/api/hades/episodes")
    async def hades_episodes(request: Request, limit: int = 50):
        value = owner(request)
        with session_factory() as db:
            rows = db.query(Episode).filter_by(owner=value).order_by(Episode.ended_at.desc()).limit(min(max(limit, 1), 100)).all()
            return {"episodes": [{c.name: (getattr(row,c.name).isoformat() if hasattr(getattr(row,c.name), 'isoformat') else getattr(row,c.name)) for c in row.__table__.columns} for row in rows]}
    @router.post("/api/hades/episodes/from-event", status_code=201)
    async def hades_episode_from_event(request: Request, payload: dict = Body(...)):
        value = owner(request)
        with session_factory() as db:
            try: return PersistentAgent(db).episode_from_event(value, str(payload.get("event_id") or ""))
            except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    @router.get("/api/hades/lessons")
    async def hades_lessons(request: Request, status: str | None = None):
        value = owner(request)
        with session_factory() as db:
            query = db.query(Lesson).filter_by(owner=value)
            if status: query = query.filter_by(status=status)
            rows = query.order_by(Lesson.updated_at.desc()).limit(100).all()
            return {"lessons": [{c.name: (getattr(row,c.name).isoformat() if hasattr(getattr(row,c.name), 'isoformat') else getattr(row,c.name)) for c in row.__table__.columns} for row in rows]}
    @router.post("/api/hades/lessons", status_code=201)
    async def hades_lesson_create(request: Request, payload: dict = Body(...)):
        value = owner(request)
        with session_factory() as db:
            return PersistentAgent(db).propose_lesson(value, str(payload.get("statement") or ""), domain=str(payload.get("domain") or "general"), evidence_episode_refs=payload.get("evidence_episode_refs"), confidence=payload.get("confidence", 50), scope_context=payload.get("scope_context"))
    @router.post("/api/hades/lessons/{lesson_id}/decision")
    async def hades_lesson_decision(request: Request, lesson_id: str, payload: dict = Body(...)):
        value = owner(request); decision = str(payload.get("status") or "").lower()
        if decision not in {"confirmed", "rejected", "superseded"}: raise HTTPException(400, "invalid lesson decision")
        with session_factory() as db:
            row = db.query(Lesson).filter_by(owner=value, id=lesson_id).one_or_none()
            if row is None: raise HTTPException(404, "lesson not found")
            if decision == "confirmed" and not row.evidence_episode_refs: raise HTTPException(400, "lesson confirmation requires evidence episode references")
            row.status = decision; row.last_confirmed = datetime.now(timezone.utc).replace(tzinfo=None) if decision == "confirmed" else row.last_confirmed; db.commit()
            return {c.name: (getattr(row,c.name).isoformat() if hasattr(getattr(row,c.name), 'isoformat') else getattr(row,c.name)) for c in row.__table__.columns}
    @router.get("/api/hades/monitors")
    async def hades_monitors(request: Request):
        value = owner(request)
        with session_factory() as db:
            rows = db.query(Monitor).filter_by(owner=value).order_by(Monitor.updated_at.desc()).all()
            return {"monitors": [{c.name: (getattr(row,c.name).isoformat() if hasattr(getattr(row,c.name), 'isoformat') else getattr(row,c.name)) for c in row.__table__.columns} for row in rows]}
    @router.post("/api/hades/monitors", status_code=201)
    async def hades_monitor_create(request: Request, payload: dict = Body(...)):
        value = owner(request)
        with session_factory() as db:
            try: return PersistentAgent(db).create_monitor(value, payload)
            except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    @router.post("/api/hades/monitors/evaluate")
    async def hades_monitor_evaluate(request: Request):
        value = owner(request)
        with session_factory() as db: return {"notifications": PersistentAgent(db).evaluate_monitors(value)}
    @router.post("/api/hades/commitments/evaluate")
    async def hades_commitments_evaluate(request: Request):
        value = owner(request)
        with session_factory() as db: return PersistentAgent(db).evaluate_commitments(value)
    @router.get("/api/hades/notifications")
    async def hades_notifications(request: Request, unread: bool = False):
        value = owner(request)
        with session_factory() as db:
            query = db.query(Notification).filter_by(owner=value)
            if unread: query = query.filter(Notification.read_at == None)
            rows = query.order_by(Notification.created_at.desc()).limit(100).all()
            return {"notifications": [{c.name: (getattr(row,c.name).isoformat() if hasattr(getattr(row,c.name), 'isoformat') else getattr(row,c.name)) for c in row.__table__.columns} for row in rows]}
    @router.get("/api/hades/attention")
    async def hades_attention(request: Request):
        value = owner(request)
        with session_factory() as db:
            return PersistentAgent(db).attention(value)
    @router.get("/api/hades/brief")
    async def hades_brief(request: Request, period: str = "day", horizon_hours: int = 48):
        value = owner(request)
        if period not in {"day", "week"}: raise HTTPException(400, "period must be day or week")
        with session_factory() as db:
            try: return PersistentAgent(db).operating_brief(value, period=period, horizon_hours=horizon_hours)
            except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    @router.post("/api/hades/notifications/{notification_id}/read")
    async def hades_notification_read(request: Request, notification_id: str):
        value = owner(request)
        with session_factory() as db:
            row = db.query(Notification).filter_by(owner=value, id=notification_id).one_or_none()
            if row is None: raise HTTPException(404, "notification not found")
            row.read_at = datetime.now(timezone.utc).replace(tzinfo=None); row.delivery_state = "read"; db.commit()
            return {"ok": True, "id": row.id}
    @router.get("/api/hades/while-away")
    async def hades_while_away(request: Request, since: str | None = None):
        value = owner(request)
        with session_factory() as db:
            agent = PersistentAgent(db)
            instance = agent.instance(value)
            if since:
                try: marker = datetime.fromisoformat(since.replace("Z", "+00:00")); marker = marker.astimezone(timezone.utc).replace(tzinfo=None) if marker.tzinfo else marker
                except ValueError as exc: raise HTTPException(400, "since must be ISO-8601") from exc
            else:
                marker = instance.last_seen_at or (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1))
            result = agent.digest(value, marker)
            instance.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None); db.commit()
            return result | {"marked_seen_at": instance.last_seen_at.isoformat()}
    @router.get("/api/developer/yolo/status")
    async def yolo_status(request: Request,lease_id: str|None=None):
        value=owner(request)
        with session_factory() as db:
            row=developer_mode.active(db,value,lease_id) if lease_id else None
            return {"active":bool(row),"profile":"workspace_yolo","workspace":developer_mode.WORKSPACE,"root":False,"docker":False,"lease":developer_mode._serialize(row) if row else None}
    @router.post("/api/developer/yolo/grant")
    async def yolo_grant(request: Request,payload:dict=Body(...)):
        value=owner(request)
        with session_factory() as db:
            return developer_mode.grant(db,value,workspace=payload.get("workspace"),duration_seconds=payload.get("duration_seconds",1800),run_id=payload.get("run_id"),session_id=payload.get("session_id"))
    @router.post("/api/developer/yolo/revoke")
    async def yolo_revoke(request: Request,payload:dict=Body(...)):
        value=owner(request)
        with session_factory() as db:return {"revoked":developer_mode.revoke(db,value,str(payload.get("lease_id") or ""))}
    @router.post("/api/developer/yolo/shell")
    async def yolo_shell(request: Request,payload:dict=Body(...)):
        value=owner(request)
        with session_factory() as db:
            try:return developer_mode.execute(db,value,str(payload.get("lease_id") or ""),payload.get("command"))
            except ValueError as exc: raise HTTPException(403,str(exc)) from exc
    @router.get("/api/network/map")
    async def network_map(request: Request): owner(request); return await asyncio.to_thread(map_projection)
    @router.post("/api/network/discovery/plan")
    async def discovery_plan(request: Request, payload: dict = Body(...)):
        value=owner(request)
        try:
            network=ipaddress.ip_network(str(payload.get("cidr") or ""), strict=True)
            if not network.is_private or network.num_addresses > 256: raise ValueError
        except ValueError as exc: raise HTTPException(400,"discovery requires a canonical private IPv4 CIDR of at most 256 addresses") from exc
        digest=hashlib.sha256(f"{value}|{network}|nmap_ping_scan".encode()).hexdigest()
        return {"kind":"plan","owner":value,"cidr":str(network),"scanner":"nmap_ping_scan","operation_digest":digest,"requires_exact_approval":True,"bounded":True,"mutation":"none","message":"Plan only; execution must use the existing privileged Homelab path."}
    return router
