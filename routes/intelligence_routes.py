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
