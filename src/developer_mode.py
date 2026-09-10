"""Owner-granted, expiring workspace developer execution."""
from __future__ import annotations
from datetime import datetime, timedelta
import os, re, subprocess
from core.local_intelligence_models import DeveloperLease
from src.work_engine import WorkEngine, ident, now
from src.execution_profiles import bubblewrap_argv, use_execution_profile
from core.platform_compat import kill_process_tree
# Developer execution runs inside the Odysseus container.  The host checkout is
# bind-mounted at this container path by Compose; using the host pathname here
# makes leases valid in source tests but fail at runtime when the path is not
# present in the container namespace.
# Containers mount the checkout at /app.  The local systemd owner runtime uses
# the host checkout directly, so it supplies HADES_WORKSPACE explicitly.  Keep
# /app as the portable/container default and accept it as a legacy alias only
# when the configured host workspace is different.
WORKSPACE = os.path.realpath(os.getenv("HADES_WORKSPACE") or "/app")
WORKSPACE_UID = int(os.getenv("HADES_WORKSPACE_UID", "1000"))
WORKSPACE_GID = int(os.getenv("HADES_WORKSPACE_GID", "1000"))
_DENY = re.compile(r"(?:^|[;&|\s])(sudo|su|doas|docker|podman|nsenter|chroot|mount)(?:$|[\s;&|])|/var/run/docker.sock|--privileged", re.I)
def _clean_workspace(value):
    requested = str(value or WORKSPACE)
    if requested == "/app" and WORKSPACE != "/app":
        requested = WORKSPACE
    path = os.path.realpath(requested)
    if path != WORKSPACE: raise ValueError("workspace_yolo is limited to the canonical workspace")
    if not os.path.isdir(path): raise ValueError("workspace does not exist")
    return path
def _serialize(row): return {c.name:(getattr(row,c.name).isoformat() if isinstance(getattr(row,c.name),datetime) else getattr(row,c.name)) for c in row.__table__.columns}
def grant(db, owner, *, workspace=WORKSPACE, duration_seconds=1800, run_id=None, session_id=None, network_policy="normal"):
    workspace = _clean_workspace(workspace); seconds=min(max(int(duration_seconds),60),8*3600)
    network_policy = str(network_policy or "normal").strip().lower()
    if network_policy not in {"normal", "sandboxed_network"}:
        raise ValueError("network_policy must be normal or sandboxed_network")
    row=DeveloperLease(id=ident("lease"),owner=owner,workspace=workspace,expires_at=now()+timedelta(seconds=seconds),run_id=run_id,session_id=session_id,network_policy=network_policy)
    db.add(row); db.commit(); db.refresh(row); return _serialize(row)
def active(db, owner, lease_id):
    row=db.query(DeveloperLease).filter_by(id=lease_id,owner=owner).one_or_none()
    return row if row and not row.revoked_at and row.expires_at > now() else None
def latest_active(db, owner):
    """Return the newest active lease belonging to this authenticated owner."""
    return (db.query(DeveloperLease)
            .filter(
                DeveloperLease.owner == owner,
                DeveloperLease.revoked_at.is_(None),
                DeveloperLease.expires_at > now(),
            )
            .order_by(DeveloperLease.granted_at.desc())
            .first())
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

def _workspace_environment(workspace):
    """Build the minimal environment allowed for model-owned workspace shell.

    The application environment can contain provider credentials and other
    process secrets.  A normal YOLO lease still needs a predictable PATH and
    workspace identity, but it must not inherit arbitrary service variables.
    Hardcore YOLO already starts with an empty environment inside bubblewrap.
    """
    env = {
        "PATH": os.getenv("PATH") or "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": workspace,
        "PWD": workspace,
        "TERM": os.getenv("TERM") or "xterm-256color",
    }
    for key in ("LANG", "LC_ALL", "LC_CTYPE"):
        value = os.getenv(key)
        if value:
            env[key] = value
    return env

def _run_bounded(argv, *, cwd, env, drop_user=False):
    """Run a developer command in its own process group and reap descendants."""
    # ``capture_output`` belongs to subprocess.run; Popen requires explicit
    # pipes. Keep both streams bounded by communicate/return slicing below.
    kwargs = {
        "cwd": cwd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "start_new_session": True,
    }
    if drop_user:
        kwargs["preexec_fn"] = _drop_to_workspace_user
    proc = subprocess.Popen(argv, env=env, **kwargs)
    try:
        stdout, stderr = proc.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        kill_process_tree(proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        return subprocess.CompletedProcess(argv, 124, stdout, stderr)
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)

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
        command_argv = ["/bin/bash", "-lc", command]
        if row.network_policy == "sandboxed_network":
            # The source workspace is read-only; all writes are ephemeral.
            # Network access is intentionally explicit in the persisted lease,
            # and the route remains owner-authenticated and lease-bound.
            with use_execution_profile("hardcore_yolo"):
                proc = _run_bounded(bubblewrap_argv(row.workspace, command_argv), cwd="/", env={})
        else:
            proc = _run_bounded(command_argv, cwd=row.workspace, env=_workspace_environment(row.workspace), drop_user=True)
    except Exception:
        if action:
            WorkEngine(db).set_run_status(owner, row.run_id, "failed", {"error_summary": "workspace command failed before completion"})
        raise
    if action:
        WorkEngine(db).complete_action(owner, action["id"], {"result_reference": f"yolo://{row.id}/{action['id']}"})
    return {"lease_id":lease_id,"action_id":action["id"] if action else None,"workspace":row.workspace,"network_policy":row.network_policy,"returncode":proc.returncode,"stdout":proc.stdout[-20000:],"stderr":proc.stderr[-10000:],"audited":True,"uid":65534 if row.network_policy == "sandboxed_network" else WORKSPACE_UID,"root":False}
