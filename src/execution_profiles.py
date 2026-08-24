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
    if profile.subprocess_backend == "bubblewrap":
        missing = [name for name in ("bwrap", "prlimit") if shutil.which(name) is None]
        if missing:
            return "The isolated workspace backend is unavailable; missing: " + ", ".join(missing) + "."
    return None


def bubblewrap_argv(workspace: str, command: list[str]) -> list[str]:
    """Build a minimal, networkless bubblewrap process invocation."""
    if active_execution_profile().subprocess_backend != "bubblewrap":
        return command
    if not workspace or not os.path.isdir(workspace):
        raise RuntimeError("isolated workspace execution requires a valid workspace")
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("isolated workspace execution requires bubblewrap")
    prlimit = shutil.which("prlimit")
    if not prlimit:
        raise RuntimeError("isolated workspace execution requires prlimit")

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
    argv.extend((
        "--bind", workspace, workspace,
        "--chdir", workspace,
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
