"""Enforceable execution profiles for agent tool dispatch and subprocesses."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
import os
import shutil
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from src.tool_capabilities import ToolCapabilities, ToolEffect


@dataclass(frozen=True)
class ExecutionProfile:
    name: str
    allowed_effects: frozenset[ToolEffect] | None
    subprocess_backend: str
    requires_workspace: bool = False
    allowed_tools: frozenset[str] | None = None
    operator_mode: bool = False


_PROFILES = {
    # Compatibility profile. Existing authorization, approval, owner, path,
    # and taint gates still apply, but code execution is a host process.
    "host": ExecutionProfile("host", None, "host"),
    # Explicit full-host operator mode. It permits every classified effect,
    # including network and administrative actions, while unknown tools still
    # fail closed. Authentication, tool policy, and approval gates remain.
    "privileged_host": ExecutionProfile(
        "privileged_host", None, "host", operator_mode=True,
    ),
    "isolated_workspace": ExecutionProfile(
        "isolated_workspace",
        frozenset({
            ToolEffect.READ_PUBLIC,
            ToolEffect.READ_WORKSPACE,
            ToolEffect.WRITE_WORKSPACE,
            ToolEffect.EXECUTE_CODE,
            ToolEffect.USER_INTERACTION,
        }),
        "bubblewrap",
        requires_workspace=True,
        allowed_tools=frozenset({
            "apply_patch", "ask_user", "bash", "edit_file", "get_workspace",
            "glob", "grep", "ls", "python", "read_file", "update_plan",
            "write_file",
        }),
    ),
    "workspace_yolo": ExecutionProfile(
        "workspace_yolo", frozenset({ToolEffect.READ_WORKSPACE, ToolEffect.WRITE_WORKSPACE, ToolEffect.EXECUTE_CODE, ToolEffect.USER_INTERACTION}), "host", requires_workspace=True,
    ),
    # Explicitly separate network-enabled disposable execution from the
    # historical host-backed workspace_yolo profile.  The host workspace is
    # mounted read-only; writes happen only in an ephemeral sandbox mount.
    # Selecting this profile is not authorization by itself: the normal exact
    # approval and owner/tool gates must still admit the command.
    "hardcore_yolo": ExecutionProfile(
        "hardcore_yolo",
        frozenset({
            ToolEffect.READ_PUBLIC,
            ToolEffect.READ_WORKSPACE,
            ToolEffect.WRITE_WORKSPACE,
            ToolEffect.EXECUTE_CODE,
            ToolEffect.NETWORK_EGRESS,
            ToolEffect.USER_INTERACTION,
        }),
        "bubblewrap_network",
        requires_workspace=True,
        allowed_tools=frozenset({
            "bash", "python", "get_workspace", "glob", "grep", "ls", "read_file",
        }),
    ),
}
EXECUTION_PROFILES = MappingProxyType(_PROFILES)

_active_profile: contextvars.ContextVar[ExecutionProfile] = contextvars.ContextVar(
    "agent_execution_profile", default=EXECUTION_PROFILES["host"]
)


def resolve_execution_profile(requested: str | None) -> ExecutionProfile:
    name = (requested or "host").strip().casefold().replace("-", "_")
    try:
        return EXECUTION_PROFILES[name]
    except KeyError as exc:
        choices = ", ".join(EXECUTION_PROFILES)
        raise ValueError(f"unknown execution profile {requested!r}; choose {choices}") from exc


def active_execution_profile() -> ExecutionProfile:
    return _active_profile.get()


@contextmanager
def use_execution_profile(requested: str | ExecutionProfile):
    """Temporarily bind an explicitly selected profile to one tool action.

    Capability bindings use this only after the outer ActionSpec approval gate
    has admitted the action.  The binding is task-local and is always reset,
    so a privileged host operation cannot leak into a later turn.
    """
    profile = requested if isinstance(requested, ExecutionProfile) else resolve_execution_profile(requested)
    token = _active_profile.set(profile)
    try:
        yield profile
    finally:
        _active_profile.reset(token)


def profile_block_reason(
    profile: ExecutionProfile, capabilities: ToolCapabilities, workspace: str | None,
    tool_name: Any = None,
) -> str | None:
    if profile.requires_workspace and not workspace:
        return f"Execution profile '{profile.name}' requires a valid workspace."
    if not capabilities.known:
        return f"Execution profile '{profile.name}' blocks unknown tools."
    if profile.allowed_tools is not None and tool_name not in profile.allowed_tools:
        return f"Execution profile '{profile.name}' does not allow tool '{tool_name}'."
    if profile.allowed_effects is not None:
        denied = capabilities.effects - profile.allowed_effects
        if denied:
            names = ", ".join(sorted(effect.value for effect in denied))
            return f"Execution profile '{profile.name}' blocks effects: {names}."
    if profile.subprocess_backend in {"bubblewrap", "bubblewrap_network"}:
        missing = [name for name in ("bwrap", "prlimit") if shutil.which(name) is None]
        if missing:
            return "The isolated workspace backend is unavailable; missing: " + ", ".join(missing) + "."
    return None


def bubblewrap_argv(workspace: str, command: list[str]) -> list[str]:
    """Build an isolated subprocess invocation for the active profile.

    ``hardcore_yolo`` intentionally shares the host network namespace only
    after its separate exact-approval path selects that profile.  It never
    mounts the host workspace writable: the agent can inspect source, but any
    files it creates live in the disposable sandbox and disappear with it.
    """
    profile = active_execution_profile()
    if profile.subprocess_backend not in {"bubblewrap", "bubblewrap_network"}:
        return command
    if not workspace or not os.path.isdir(workspace):
        raise RuntimeError("isolated workspace execution requires a valid workspace")
    # Availability is enforced by ``profile_block_reason`` immediately before
    # dispatch.  Keep argv construction pure so callers/tests can inspect the
    # exact bounded command even on hosts that do not ship the optional
    # isolation primitives.  If an unsafe caller bypasses that gate, exec
    # still fails closed with the normal missing-binary error.
    bwrap = shutil.which("bwrap") or "bwrap"
    prlimit = shutil.which("prlimit") or "prlimit"

    if profile.subprocess_backend == "bubblewrap_network":
        argv = [
            bwrap, "--die-with-parent", "--new-session",
            "--unshare-user", "--unshare-pid", "--unshare-ipc",
            "--unshare-uts", "--unshare-cgroup", "--share-net",
            "--uid", "65534", "--gid", "65534",
            "--proc", "/proc", "--dev", "/dev",
            "--tmpfs", "/tmp", "--tmpfs", "/work", "--chmod", "1777", "/work",
        ]
    else:
        argv = [
            bwrap,
            "--die-with-parent", "--new-session", "--unshare-all",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        ]
    # Executables and their dynamic loaders only. Do not mount /etc, /home,
    # application data, credentials, or the host root into the sandbox.
    for path in ("/usr", "/bin", "/lib", "/lib64"):
        if os.path.exists(path):
            argv.extend(("--ro-bind", path, path))
    if profile.subprocess_backend == "bubblewrap_network":
        # Read-only source view; /work is the only writable location and is
        # tmpfs-backed, so host files cannot be deleted or modified.
        argv.extend(("--ro-bind", workspace, "/source", "--chdir", "/work"))
        if os.path.exists("/etc/resolv.conf"):
            argv.extend(("--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf"))
        if os.path.exists("/etc/hosts"):
            argv.extend(("--ro-bind", "/etc/hosts", "/etc/hosts"))
    else:
        argv.extend(("--bind", workspace, workspace, "--chdir", workspace))
    argv.extend((
        "--clearenv",
        "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin",
        "--setenv", "HOME", "/tmp",
        "--setenv", "TMPDIR", "/tmp",
        "--", prlimit,
        "--nproc=128:128",
        "--cpu=300:300",
        "--as=4294967296:4294967296",
        "--fsize=268435456:268435456",
        "--nofile=256:256",
        "--", *command,
    ))
    return argv
