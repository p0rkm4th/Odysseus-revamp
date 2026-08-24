"""Owner-granted, expiring workspace developer execution."""
from __future__ import annotations
from datetime import datetime, timedelta
import os, re, subprocess
from core.local_intelligence_models import DeveloperLease
from src.work_engine import ident, now
WORKSPACE = "/home/scootz/Odysseus/odysseus"
_DENY = re.compile(r"(?:^|[;&|\s])(sudo|su|doas|docker|podman|nsenter|chroot|mount)(?:$|[\s;&|])|/var/run/docker.sock|--privileged", re.I)
def _clean_workspace(value):
    path = os.path.realpath(str(value or WORKSPACE))
    if path != WORKSPACE: raise ValueError("workspace_yolo is limited to the canonical workspace")
    if not os.path.isdir(path): raise ValueError("workspace does not exist")
    return path
def _serialize(row): return {c.name:(getattr(row,c.name).isoformat() if isinstance(getattr(row,c.name),datetime) else getattr(row,c.name)) for c in row.__table__.columns}
def grant(db, owner, *, workspace=WORKSPACE, duration_seconds=1800, run_id=None, session_id=None):
    workspace = _clean_workspace(workspace); seconds=min(max(int(duration_seconds),60),8*3600)
    row=DeveloperLease(id=ident("lease"),owner=owner,workspace=workspace,expires_at=now()+timedelta(seconds=seconds),run_id=run_id,session_id=session_id)
    db.add(row); db.commit(); db.refresh(row); return _serialize(row)
def active(db, owner, lease_id):
    row=db.query(DeveloperLease).filter_by(id=lease_id,owner=owner).one_or_none()
    return row if row and not row.revoked_at and row.expires_at > now() else None
def revoke(db, owner, lease_id):
    row=active(db,owner,lease_id)
    if not row:return False
    row.revoked_at=now();row.revision+=1;db.commit();return True
def execute(db, owner, lease_id, command):
    row=active(db,owner,lease_id)
    if not row: raise ValueError("workspace_yolo lease is expired, revoked, or unknown")
    command=str(command or "").strip()
    if not command: raise ValueError("command is required")
    if _DENY.search(command): raise ValueError("workspace_yolo blocks root/admin/container escape commands")
    proc=subprocess.run(["/bin/bash","-lc",command],cwd=row.workspace,capture_output=True,text=True,timeout=300,env={**os.environ,"PWD":row.workspace})
    return {"lease_id":lease_id,"workspace":row.workspace,"returncode":proc.returncode,"stdout":proc.stdout[-20000:],"stderr":proc.stderr[-10000:],"audited":True}
