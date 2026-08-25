"""Owner-granted, expiring workspace developer execution."""
from __future__ import annotations
from datetime import datetime, timedelta
import os, re, subprocess
from core.local_intelligence_models import DeveloperLease
from src.work_engine import WorkEngine, ident, now
# Developer execution runs inside the Odysseus container.  The host checkout is
# bind-mounted at this container path by Compose; using the host pathname here
# makes leases valid in source tests but fail at runtime when the path is not
# present in the container namespace.
WORKSPACE = "/app"
WORKSPACE_UID = int(os.getenv("HADES_WORKSPACE_UID", "1000"))
WORKSPACE_GID = int(os.getenv("HADES_WORKSPACE_GID", "1000"))
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
def _drop_to_workspace_user():
    """Run YOLO subprocesses as the normal workspace owner, never container root."""
    if os.getuid() == WORKSPACE_UID and os.getgid() == WORKSPACE_GID:
        return
    if os.getuid() != 0:
        raise ValueError("workspace_yolo requires the configured non-root workspace user")
    os.setgroups([WORKSPACE_GID])
    os.setgid(WORKSPACE_GID)
    os.setuid(WORKSPACE_UID)
def execute(db, owner, lease_id, command):
    row=active(db,owner,lease_id)
    if not row: raise ValueError("workspace_yolo lease is expired, revoked, or unknown")
    command=str(command or "").strip()
    if not command: raise ValueError("command is required")
    if _DENY.search(command): raise ValueError("workspace_yolo blocks root/admin/container escape commands")
    action = None
    if row.run_id:
        action = WorkEngine(db).create_action(owner, row.run_id, {
            "capability_id": "developer.workspace_shell",
            "action_id": "execute",
            "tool_binding_name": "workspace_yolo_shell",
            "effect_class": "developer_workspace",
            "normalized_input": {"command": command},
            "status": "approved",
        })
    try:
        proc=subprocess.run(["/bin/bash","-lc",command],cwd=row.workspace,capture_output=True,text=True,timeout=300,env={**os.environ,"PWD":row.workspace,"HOME":row.workspace},preexec_fn=_drop_to_workspace_user)
    except Exception:
        if action:
            WorkEngine(db).set_run_status(owner, row.run_id, "failed", {"error_summary": "workspace command failed before completion"})
        raise
    if action:
        WorkEngine(db).complete_action(owner, action["id"], {"result_reference": f"yolo://{row.id}/{action['id']}"})
    return {"lease_id":lease_id,"action_id":action["id"] if action else None,"workspace":row.workspace,"returncode":proc.returncode,"stdout":proc.stdout[-20000:],"stderr":proc.stderr[-10000:],"audited":True,"uid":WORKSPACE_UID,"root":False}
