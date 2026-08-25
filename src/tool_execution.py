"""
tool_execution.py

Tool dispatcher and result formatter for the agent loop.
Routes tool blocks to MCP servers or native implementations.

Extracted from agent_tools.py.
"""

import asyncio
import collections
import contextvars
import json
import logging
import os
import pathlib
import re
import sys
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple



from src.tool_security import (
    BUILTIN_EMAIL_TOOLS,
    email_tool_policy_names,
    is_public_blocked_tool,
    owner_is_admin_or_single_user,
)
from src.tool_capabilities import ToolRunSecurityContext, blocked_tool_result
from src.tool_approvals import ExactToolApproval
from src.tool_policy import ToolPolicy
from src.constants import MAX_OUTPUT_CHARS, MAX_READ_CHARS, MAX_DIFF_LINES, DATA_DIR
from src.tool_utils import _truncate, get_mcp_manager


class _MissingToolSecurityContext:
    pass


class _NoToolSecurityContext:
    """Explicit sentinel for non-agent callers that have no run provenance."""


_MISSING_TOOL_SECURITY_CONTEXT = _MissingToolSecurityContext()
NO_TOOL_SECURITY_CONTEXT = _NoToolSecurityContext()

# Persistent working directory for agent subprocesses.
# Resolves to <repo_root>/data, which is the bind-mounted volume in Docker
# (/app/data) and the local data directory for manual installs.
# Using this as cwd and HOME prevents the agent from silently creating files
# in ephemeral container layers that are lost on the next rebuild.
_AGENT_WORKDIR = DATA_DIR



# ---------------------------------------------------------------------------
# Path confinement for read_file / write_file
# ---------------------------------------------------------------------------
# read_file + write_file are admin-only tools, but the path the agent
# supplies is model-controlled. Prompt-injection in an admin's chat can
# weaponise "read /etc/shadow" or "write ~/.ssh/authorized_keys" without
# the admin noticing.
#
# Policy:
#   1. Sensitive-subpath deny list — checked FIRST. Blocks .ssh,
#      .gnupg, shell rc files, token/env files even if the root above
#      them is on the allowlist.
#   2. Allowlist — only the directories the agent legitimately needs
#      (project data/, system tmp). $HOME is NOT on the default list.
#   3. Opt-in extra roots — admin can add broader roots via the
#      "tool_path_extra_roots" setting (list of path strings).
# ---------------------------------------------------------------------------

_SENSITIVE_BASENAMES: set[str] = {
    ".ssh", ".gnupg", ".gitconfig",
    ".bashrc", ".bash_profile", ".bash_logout",
    ".zshrc", ".zprofile", ".zshenv",
    ".profile", ".tcshrc", ".cshrc",
    ".env", ".netrc",
}

_SENSITIVE_FILE_PATTERNS: tuple[str, ...] = (
    "authorized_keys", "id_rsa", "id_ed25519", "id_ecdsa",
    "known_hosts",
)

# Case-folded views used for matching. On a case-insensitive filesystem
# (Windows, default macOS) ".SSH/AUTHORIZED_KEYS" and ".env" resolve to the
# same protected files as their lowercase forms, so the deny-list has to fold
# case before comparing — the sibling resolver already normcases paths for the
# same reason. casefold (not os.path.normcase) because normcase is a no-op on
# POSIX, which is exactly where the macOS read-exfil path lives.
_SENSITIVE_BASENAMES_CF: frozenset[str] = frozenset(b.casefold() for b in _SENSITIVE_BASENAMES)
_SENSITIVE_FILE_PATTERNS_CF: frozenset[str] = frozenset(p.casefold() for p in _SENSITIVE_FILE_PATTERNS)


def _is_sensitive_path(resolved: str) -> bool:
    """Return True if *resolved* falls under a sensitive directory or
    matches a sensitive filename — regardless of what root it sits under.

    Matching is case-insensitive: on Windows / default macOS a case-variant
    name (``.SSH``, ``AUTHORIZED_KEYS``, ``Id_Rsa``) points at the same file as
    the lowercase form, so a case-sensitive check would let it slip past the
    deny-list in every file tool that relies on it.
    """
    parts = [p.casefold() for p in resolved.split(os.sep)]
    filename = parts[-1] if parts else ""

    # Check if any path component is a sensitive directory.
    for part in parts:
        if part in _SENSITIVE_BASENAMES_CF:
            return True

    # Check filename against known sensitive files.
    return filename in _SENSITIVE_FILE_PATTERNS_CF


def _tool_path_roots() -> list[str]:
    """Return the list of directory roots that read_file / write_file
    may touch. Default: project data/ + system temp dirs. Extra roots
    are loaded from the ``tool_path_extra_roots`` setting.
    """
    roots: list[str] = []

    # Project data directory — the agent's primary workspace.
    from src.constants import DATA_DIR
    roots.append(DATA_DIR)

    # /tmp (and its macOS realpath /private/tmp).
    roots.append("/tmp")
    try:
        private_tmp = os.path.realpath("/tmp")
        if private_tmp != "/tmp":
            roots.append(private_tmp)
    except OSError:
        pass

    # $TMPDIR — per-user temp root on macOS (e.g. /var/folders/.../T/).
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        roots.append(tmpdir)

    # Opt-in extra roots from settings.
    try:
        from src.settings import get_setting
        extra = get_setting("tool_path_extra_roots")
        if isinstance(extra, list):
            roots.extend(str(r) for r in extra if r)
    except Exception:
        pass

    # Deduplicate; resolve symlinks so containment is unambiguous.
    seen: set[str] = set()
    out: list[str] = []
    for r in roots:
        try:
            real = os.path.realpath(r)
        except OSError:
            continue
        if real in seen:
            continue
        seen.add(real)
        out.append(real)
    return out


def _resolve_tool_path(raw_path: str) -> str:
    """Resolve and confine a model-supplied path.

    Order of checks:
      1. Non-empty path.
      2. Sensitive-subpath deny list (blocks .ssh, .gnupg, etc.
         even when the root is on the allowlist).
      3. Allowlist containment (must land under one of the roots).

    Returns the realpath on success. Raises ValueError on rejection.
    Symlinks are resolved before comparison.

    When a workspace is active for this turn, paths are confined to it instead
    of the default allowlist (see _resolve_tool_path_in_workspace).
    """
    ws = get_active_workspace()
    if ws:
        return _resolve_tool_path_in_workspace(ws, raw_path)
    if raw_path is None or not str(raw_path).strip():
        raise ValueError("path is required")
    expanded = os.path.expanduser(str(raw_path).strip())
    resolved = os.path.realpath(expanded)

    if _is_sensitive_path(resolved):
        raise ValueError(
            f"path '{raw_path}' is inside a sensitive directory "
            f"(e.g. .ssh, .gnupg) or matches a sensitive filename"
        )

    for root in _tool_path_roots():
        if resolved == root:
            return resolved
        try:
            common = os.path.commonpath([resolved, root])
        except ValueError:
            continue
        if common == root:
            return resolved
    raise ValueError(
        f"path '{raw_path}' is outside the allowed roots"
    )


def _resolve_tool_path_in_workspace(workspace: str, raw_path: str) -> str:
    """Confine a model-supplied path to the active workspace.

    Layered on top of upstream's path policy: the workspace is the allowed
    root (relative paths resolve under it; paths that escape it are rejected),
    and the sensitive-file deny list (.ssh, .gnupg, id_rsa, …) still applies
    inside it. When no workspace is set, callers use _resolve_tool_path (the
    default data/tmp allowlist) instead.
    """
    if raw_path is None or not str(raw_path).strip():
        raise ValueError("path is required")
    base = os.path.realpath(workspace)
    expanded = os.path.expanduser(str(raw_path).strip())
    candidate = expanded if os.path.isabs(expanded) else os.path.join(base, expanded)
    resolved = os.path.realpath(candidate)
    if _is_sensitive_path(resolved):
        raise ValueError(
            f"path '{raw_path}' is inside a sensitive directory "
            f"(e.g. .ssh, .gnupg) or matches a sensitive filename"
        )
    if resolved != base:
        # normcase so containment holds on case-insensitive filesystems
        # (Windows, default macOS): it lowercases on Windows and is a no-op on
        # POSIX. commonpath raises ValueError across Windows drives (C: vs D:)
        # or mixed abs/rel — both mean "outside", so the except rejects them.
        nbase = os.path.normcase(base)
        try:
            if os.path.commonpath([os.path.normcase(resolved), nbase]) != nbase:
                raise ValueError
        except ValueError:
            raise ValueError(f"path '{raw_path}' is outside the workspace ({workspace})")
    return resolved



# ---------------------------------------------------------------------------
# Active workspace (per-turn, context-local)
# ---------------------------------------------------------------------------
# Set ONCE in execute_tool_block from the request's `workspace`. The path
# resolvers (_resolve_tool_path / _resolve_search_root) and the subprocess cwd
# helper (agent_cwd) read it from here, so confinement is enforced in a single
# place: any tool that resolves paths through these helpers is confined
# automatically and cannot accidentally bypass the workspace. contextvars are
# task-local, so concurrent turns don't leak into each other.
_active_workspace: contextvars.ContextVar = contextvars.ContextVar(
    "agent_active_workspace", default=None
)


def get_active_workspace() -> Optional[str]:
    """The folder the agent is confined to this turn, or None."""
    return _active_workspace.get()


def vet_workspace(raw: str) -> Optional[str]:
    """Validate a requested workspace path at bind time.

    Returns the canonical path, or None when it is unusable: not a real
    directory, or itself a sensitive path (.ssh, .gnupg, ...). The in-workspace
    resolver deny-lists sensitive paths *inside* the workspace, but the
    empty-path search root is the workspace itself, so the root has to be
    vetted before it is ever bound.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    resolved = os.path.realpath(os.path.expanduser(raw))
    if not os.path.isdir(resolved) or _is_sensitive_path(resolved):
        return None
    # Reject filesystem roots: binding / (or a Windows drive/UNC root) as the
    # workspace would make every absolute path "inside" it, collapsing the
    # confinement into host-wide file access. A root is its own dirname, which
    # also covers C:\ and \\server\share without platform-specific lists.
    if os.path.dirname(resolved) == resolved:
        return None
    return resolved


def agent_cwd() -> str:
    """Working directory for agent subprocesses (bash/python/background jobs):
    the active workspace when set, else the persistent data dir."""
    return get_active_workspace() or _AGENT_WORKDIR


def get_mcp_manager():
    from src import agent_tools
    return agent_tools.get_mcp_manager()




def _resolve_search_root(raw_path: str) -> str:
    """Resolve + confine a code-nav path (grep/glob/ls).

    With a workspace active, the workspace folder is the root and a supplied
    path is confined inside it. Otherwise an empty path defaults to the agent's
    primary root (project data dir) and a supplied path is confined by the
    global allowlist + sensitive-file policy.
    """
    raw = (raw_path or "").strip()
    ws = get_active_workspace()
    if ws:
        return os.path.realpath(ws) if not raw else _resolve_tool_path_in_workspace(ws, raw)
    if not raw:
        roots = _tool_path_roots()
        return roots[0] if roots else os.path.realpath(".")
    return _resolve_tool_path(raw)

logger = logging.getLogger(__name__)


_ADMIN_TOOLS = {
    "app_api",
    "manage_endpoints",
    "manage_mcp",
    "manage_webhooks",
    "manage_tokens",
    "manage_settings",
    "download_model",
    "serve_model",
    "serve_preset",
    "stop_served_model",
    "cancel_download",
}


def _owner_is_admin(owner: Optional[str]) -> bool:
    """Mirror route-level admin behavior for agent tool execution."""
    return owner_is_admin_or_single_user(owner)

# ---------------------------------------------------------------------------
# MCP-backed tool helpers
# ---------------------------------------------------------------------------

# Map legacy tool names -> (MCP server_id, MCP tool_name)
_MCP_TOOL_MAP = {
    "bash":           ("bash",       "bash"),
    "python":         ("python",     "python"),
    "read_file":      ("filesystem", "read_file"),
    "write_file":     ("filesystem", "write_file"),
    "web_search":     ("web_search", "web_search"),
    "web_fetch":      ("web_fetch",  "web_fetch"),
    "generate_image": ("image_gen",  "generate_image"),
}
_EMAIL_MCP_OWNER_ARG = "_odysseus_owner"


def _parse_qualified_mcp_args(tool: str, content: str) -> tuple[Dict, Optional[str]]:
    raw = (content or "").strip()
    if not raw:
        return {}, None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        if tool.startswith("mcp__email__"):
            return {}, "Email MCP tool arguments must be a JSON object."
        return {}, None
    if not isinstance(parsed, dict):
        if tool.startswith("mcp__email__"):
            return {}, "Email MCP tool arguments must be a JSON object."
        return {}, None
    return parsed, None


def _parse_generate_image(content: str) -> Dict:
    lines = content.strip().split("\n")
    args = {"prompt": lines[0].strip() if lines else ""}
    for i, key in enumerate(["model", "size", "quality"], 1):
        if len(lines) > i and lines[i].strip():
            args[key] = lines[i].strip()
    return args


def _parse_manage_memory(content: str) -> Dict:
    lines = content.strip().split("\n")
    action = lines[0].strip().lower() if lines else ""
    args = {"action": action}
    if action == "add":
        args["text"] = lines[1].strip() if len(lines) > 1 else ""
        if len(lines) > 2 and lines[2].strip():
            args["category"] = lines[2].strip().lower()
    elif action == "edit":
        args["memory_id"] = lines[1].strip() if len(lines) > 1 else ""
        args["text"] = lines[2].strip() if len(lines) > 2 else ""
    elif action == "delete":
        args["memory_id"] = lines[1].strip() if len(lines) > 1 else ""
    elif action == "search":
        args["text"] = lines[1].strip() if len(lines) > 1 else ""
    elif action == "list":
        if len(lines) > 1 and lines[1].strip():
            args["category"] = lines[1].strip().lower()
    return args


def _parse_write_file(content: str) -> Dict:
    lines = content.split("\n", 1)
    return {"path": lines[0].strip(), "content": lines[1] if len(lines) > 1 else ""}


_MCP_ARG_PARSERS: Dict[str, Callable[[str], Dict[str, str]]] = {
    "bash":           lambda c: {"command": c},
    "python":         lambda c: {"code": c},
    "web_search":     lambda c: {"query": c.split("\n")[0].strip()},
    "web_fetch":      lambda c: {"url": c.split("\n")[0].strip()},
    "read_file":      lambda c: {"path": c.split("\n")[0].strip()},
    "write_file":     _parse_write_file,
    "generate_image": _parse_generate_image,
    "manage_memory":  _parse_manage_memory,
}


# Primary argument key(s) for the legacy line-parsed tools. When a fenced
# block's content is a JSON object carrying one of these keys, it's structured
# inline args (the relaxed parser's ```web_search {"query": "..."}``` shape) —
# use the object directly instead of letting the line-based parsers wrap the
# whole JSON string as the query/url/path/prompt. Keyed off membership only
# (the primary key never changes), so this can't drift; an unrecognized object
# safely falls through to the line-based parser, i.e. the previous behavior.
#
# IMPORTANT — this only covers the MCP path. _build_mcp_args is reached via
# _call_mcp_tool only for _MCP_TOOL_MAP tools (so an entry outside that map is
# dead, as manage_memory was). And of these, only generate_image has a live MCP
# server today; web_search/web_fetch/read_file/write_file have none, so they run
# via _direct_fallback -> TOOL_HANDLERS, whose handlers decode JSON themselves
# (see ReadFileTool/WriteFileTool/WebSearchTool/WebFetchTool). The entries here
# are kept as defense-in-depth for if/when those servers are added. The live
# fix for each server-less tool lives in its handler. test_write_file_inline_
# json_args and test_mcp_json_primary_keys_are_all_live pin both halves.
_MCP_JSON_PRIMARY_KEYS: Dict[str, tuple] = {
    "web_search":     ("query", "queries"),
    "web_fetch":      ("url",),
    "read_file":      ("path",),
    "write_file":     ("path",),
    "generate_image": ("prompt",),
}


def _build_mcp_args(tool: str, content: str) -> Dict:
    """Convert fenced-block text content to structured MCP arguments."""
    primaries = _MCP_JSON_PRIMARY_KEYS.get(tool)
    if primaries and content.strip().startswith("{"):
        try:
            decoded = json.loads(content.strip())
        except (json.JSONDecodeError, TypeError):
            decoded = None
        if isinstance(decoded, dict) and any(k in decoded for k in primaries):
            return decoded
    parser = _MCP_ARG_PARSERS.get(tool)
    return parser(content) if parser else {}


async def _call_mcp_tool(
    tool: str,
    content: str,
    progress_cb: Optional[Callable[[Dict], Awaitable[None]]] = None,
) -> Dict:
    """Route a legacy tool call through the MCP manager, with direct fallbacks."""
    mcp = get_mcp_manager()
    if not mcp:
        return await _direct_fallback(tool, content, progress_cb=progress_cb) or {"error": f"MCP manager not available for tool '{tool}'", "exit_code": 1}

    server_id, tool_name = _MCP_TOOL_MAP[tool]
    qualified = f"mcp__{server_id}__{tool_name}"
    args = _build_mcp_args(tool, content)
    result = await mcp.call_tool(qualified, args)

    # If MCP server not connected, try direct fallback
    if isinstance(result, dict) and result.get("exit_code") == 1 and "not connected" in result.get("error", ""):
        fallback = await _direct_fallback(tool, content, progress_cb=progress_cb)
        if fallback:
            return fallback

    # generate_image runs as a text-only MCP tool, so the saved image URL never
    # reaches the agent loop's structured forwarding (which renders the image via
    # buildImageBubble on result["image_url"]). Lift it out of the tool's stdout so
    # the image renders deterministically — no dependence on the model echoing the
    # URL into its prose (which it mangles/hallucinates).
    if tool == "generate_image":
        _promote_image_fields(result)

    return result


def _promote_image_fields(result: Dict) -> None:
    """Lift the image URL (+ prompt/model/size) from a successful generate_image MCP
    text result into structured fields the agent loop already forwards to
    buildImageBubble. Only acts on a dict result with exit_code 0; matches the
    generated-image URL by pattern (absolute or relative) so it's robust to the
    result's wording."""
    if not isinstance(result, dict) or result.get("exit_code") != 0:
        return
    out = result.get("stdout") or ""
    m = re.search(r'(?:https?://[^\s)\]]+)?/api/generated-image/[A-Za-z0-9._-]+', out)
    if not m:
        return
    result["image_url"] = m.group(0).strip()
    for field, pat in (
        ("image_prompt", r'^Generated image for:\s*(.+)$'),
        ("image_model", r'^model:\s*(.+)$'),
        ("image_size", r'^size:\s*(.+)$'),
    ):
        fm = re.search(pat, out, re.M)
        if fm:
            result[field] = fm.group(1).strip()


_BG_MARKERS = {"#!bg", "#bg", "# bg", "#background", "# background", "@background", "# @background"}


def _split_bg_marker(content: str):
    """If the bash content's first non-empty line is a background marker
    (e.g. `#!bg`), return (True, command_without_marker); else (False, content)."""
    lines = content.split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].strip().lower() in _BG_MARKERS:
        del lines[i]
        return True, "\n".join(lines).strip()
    return False, content


async def _direct_fallback(
    tool: str,
    content: str,
    progress_cb: Optional[Callable[[Dict], Awaitable[None]]] = None,
    session_id: Optional[str] = None,
    owner: Optional[str] = None,
) -> Optional[Dict]:
    _subproc_env = {
        **os.environ,
        "TERM": "xterm-256color",
        "COLUMNS": "120",
        "LINES": "40",
        "HOME": _AGENT_WORKDIR,
    }

    try:
        ctx = {
            "progress_cb": progress_cb,
            "subproc_env": _subproc_env,
            "session_id": session_id,
            "owner": owner,
        }

        from src.agent_tools import TOOL_HANDLERS
        if tool in TOOL_HANDLERS:
            return await TOOL_HANDLERS[tool](content, ctx)

    except Exception as e:
        return {"error": f"{tool}: {e}", "exit_code": 1}

    return None


async def _document_tool_dispatch(
    tool: str,
    content: str,
    session_id: Optional[str] = None,
    owner: Optional[str] = None,
    document_id: Optional[str] = None,
    document_version: Optional[int] = None,
    document_digest: Optional[str] = None,
) -> Optional[Dict]:
    """Route a document tool through TOOL_HANDLERS with the right ctx shape."""
    from src.agent_tools import TOOL_HANDLERS
    ctx = {
        "session_id": session_id,
        "owner": owner,
        "doc_id": document_id,
        "expected_document_version": document_version,
        "expected_document_digest": document_digest,
    }
    if tool in TOOL_HANDLERS:
        return await TOOL_HANDLERS[tool](content, ctx)
    return None


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

async def execute_tool_block(
    block: Any,
    session_id: Optional[str] = None,
    disabled_tools: Optional[set] = None,
    owner: Optional[str] = None,
    progress_cb: Optional[Callable[[Dict], Awaitable[None]]] = None,
    workspace: Optional[str] = None,
    tool_policy: Optional[Any] = None,
    security_context: (
        ToolRunSecurityContext
        | _NoToolSecurityContext
        | _MissingToolSecurityContext
    ) = _MISSING_TOOL_SECURITY_CONTEXT,
    exact_approval: Optional[ExactToolApproval] = None,
    _registered_executor: Optional[Callable[..., Awaitable[Tuple[str, Dict]]]] = None,
) -> Tuple[str, Dict]:
    """Execute a single tool block. Returns (description, result_dict).

    Thin wrapper: bind the per-turn workspace (so the path resolvers + subprocess
    cwd confine to it) for the duration of this call, then delegate. Reset on the
    way out so the binding never leaks to the next tool call.
    """
    if security_context is _MISSING_TOOL_SECURITY_CONTEXT:
        raise TypeError(
            "execute_tool_block requires security_context; pass a "
            "ToolRunSecurityContext or NO_TOOL_SECURITY_CONTEXT explicitly"
        )
    if (
        not isinstance(security_context, ToolRunSecurityContext)
        and security_context is not NO_TOOL_SECURITY_CONTEXT
    ):
        raise TypeError(
            "security_context must be a ToolRunSecurityContext or "
            "NO_TOOL_SECURITY_CONTEXT"
        )

    approval_claimed = False
    if exact_approval is not None:
        if (
            not isinstance(security_context, ToolRunSecurityContext)
            or not security_context.external_untrusted_context_seen
            or not exact_approval.pending.external_untrusted_context_seen
        ):
            return (
                f"{getattr(block, 'tool_type', None)}: BLOCKED",
                {
                    "error": "Exact-action approval requires an armed run security context.",
                    "exit_code": 1,
                    "blocked": True,
                    "policy": "exact_tool_approval",
                },
            )
        if (
            exact_approval.pending.tool_name
            in {"edit_document", "suggest_document", "update_document"}
            and (
                not exact_approval.pending.document_id
                or exact_approval.pending.document_version is None
                or not exact_approval.pending.document_digest
            )
        ):
            return (
                f"{getattr(block, 'tool_type', None)}: BLOCKED",
                {
                    "error": (
                        "The approved document action has no sealed target and "
                        "cannot be executed."
                    ),
                    "exit_code": 1,
                    "blocked": True,
                    "policy": "exact_tool_approval",
                },
            )
        sealed_workspace = exact_approval.pending.workspace
        if sealed_workspace and vet_workspace(sealed_workspace) != sealed_workspace:
            return (
                f"{getattr(block, 'tool_type', None)}: BLOCKED",
                {
                    "error": (
                        "The approved workspace is no longer a valid safe "
                        "directory. Review the action again."
                    ),
                    "exit_code": 1,
                    "blocked": True,
                    "policy": "exact_tool_approval",
                },
            )
        approval_claimed = exact_approval.claim(
            owner=owner,
            session_id=session_id,
            tool_name=getattr(block, "tool_type", None),
            content=getattr(block, "content", None),
            workspace=workspace,
        )
        if not approval_claimed:
            return (
                f"{getattr(block, 'tool_type', None)}: BLOCKED",
                {
                    "error": "The exact-action approval did not match this tool request.",
                    "exit_code": 1,
                    "blocked": True,
                    "policy": "exact_tool_approval",
                },
            )

    if isinstance(security_context, ToolRunSecurityContext) and not approval_claimed:
        decision = security_context.decision_for(
            getattr(block, "tool_type", None),
            getattr(block, "content", None),
        )
        if not decision.allowed:
            logger.warning(
                "External-context policy blocked tool=%r",
                getattr(block, "tool_type", None),
            )
            return blocked_tool_result(
                getattr(block, "tool_type", None),
                decision.reason or "Tool blocked by external-context policy.",
            )

    token = _active_workspace.set(workspace or None)
    try:
        if _registered_executor is not None:
            policy_names = email_tool_policy_names(getattr(block, "tool_type", None))
            if disabled_tools and not policy_names.isdisjoint(disabled_tools):
                output = (
                    f"{getattr(block, 'tool_type', None)}: BLOCKED",
                    {"error": f"Tool '{getattr(block, 'tool_type', None)}' is disabled by user.", "exit_code": 1, "blocked": True, "policy": "disabled_tools"},
                )
            elif tool_policy and any(tool_policy.blocks(name) for name in policy_names):
                output = (
                    f"{getattr(block, 'tool_type', None)}: BLOCKED",
                    {"error": f"Execution of tool '{getattr(block, 'tool_type', None)}' is forbade by the active guide-only policy.", "exit_code": 1, "blocked": True, "policy": "tool_policy"},
                )
            else:
            # Registered bindings reuse the same security/approval gate above;
            # only their mature executor implementation is supplied here.
                output = await _registered_executor(block, owner=owner)
        else:
            output = await _execute_tool_block_impl(
                block,
                session_id=session_id,
                disabled_tools=disabled_tools,
                owner=owner,
                progress_cb=progress_cb,
                tool_policy=tool_policy,
                approved_document_id=(
                    exact_approval.pending.document_id
                    if approval_claimed
                    else None
                ),
                approved_document_version=(
                    exact_approval.pending.document_version
                    if approval_claimed
                    else None
                ),
                approved_document_digest=(
                    exact_approval.pending.document_digest
                    if approval_claimed
                    else None
                ),
            )
        if isinstance(security_context, ToolRunSecurityContext):
            security_context.observe_tool_result(
                getattr(block, "tool_type", None),
                output[1],
                getattr(block, "content", None),
            )
        return output
    finally:
        _active_workspace.reset(token)


async def _execute_tool_block_impl(
    block: Any,
    session_id: Optional[str] = None,
    disabled_tools: Optional[set] = None,
    owner: Optional[str] = None,
    progress_cb: Optional[Callable[[Dict], Awaitable[None]]] = None,
    tool_policy: Optional[Any] = None,
    approved_document_id: Optional[str] = None,
    approved_document_version: Optional[int] = None,
    approved_document_digest: Optional[str] = None,
) -> Tuple[str, Dict]:
    """Execute a single tool block. Returns (description, result_dict).

    `progress_cb` is forwarded to long-running subprocess tools
    (bash, python) so the agent loop can emit `tool_progress` SSE
    events while the command is in flight. Ignored by other tools.
    """
    from src.tool_implementations import (
        do_search_chats, do_manage_tasks,
        do_manage_skills, do_api_call, do_manage_notes,
        do_manage_calendar,
        do_download_model, do_serve_model, do_list_served_models, do_stop_served_model,
        do_tail_serve_output,
        do_list_downloads, do_cancel_download, do_search_hf_models, do_list_cached_models,
        do_list_serve_presets, do_serve_preset, do_adopt_served_model,
        do_list_cookbook_servers,
        do_edit_image, do_trigger_research, do_manage_research, do_resolve_contact,
        do_manage_contact,
        do_vault_search, do_vault_get, do_vault_unlock,
        do_app_api,
    )

    # HACK:
    # This is a temporary workaround for a circular dependency between
    # tool_execution.py and agent_tools.__init__.py.
    #
    # See issue #4277:
    # refactor(tools): Move the registry from __init__.py into a
    # dedicated registry.py module.
    #
    # Do not copy this pattern elsewhere. This import should be removed
    # once the registry refactor is completed.
    try:
        agent_tools_mod = __import__("src.agent_tools", fromlist=["TOOL_HANDLERS"])
        dynamic_handlers = getattr(agent_tools_mod, "TOOL_HANDLERS", {})
    except ImportError:
        dynamic_handlers = {}

    tool = block.tool_type
    content = block.content

    # The block/disable gates below must match every policy-equivalent
    # spelling of the tool name (bare email names alias their mcp__email__
    # form — see email_tool_policy_names), not just the spelling the model
    # happened to emit.
    policy_names = email_tool_policy_names(tool)

    # Misformatted tool call detection: model put JSON inside ```python``` (or
    # similar) without naming the tool. Common with MiniMax-style outputs.
    # Return a helpful error so the model retries with the correct format.
    if tool in ("python", "json", "xml") and content.strip().startswith("{") and content.strip().endswith("}"):
        try:
            parsed = json.loads(content.strip())
            if isinstance(parsed, dict):
                desc = f"{tool}: misformatted tool call"
                result = {
                    "error": (
                        f"You wrote a JSON object inside a ```{tool}``` block, but that's not a tool call.\n"
                        "To call a tool, use the tool name as the fence tag, e.g.\n"
                        "```resolve_contact\n"
                        "{\"name\": \"...\"}\n"
                        "```\n"
                        "or\n"
                        "```send_email\n"
                        "{\"to\": \"...\", \"subject\": \"...\", \"body\": \"...\"}\n"
                        "```"
                    ),
                    "exit_code": 1,
                }
                return desc, result
        except (ValueError, TypeError):
            pass

    # Reject tools that the user has disabled for this request
    if disabled_tools and not policy_names.isdisjoint(disabled_tools):
        desc = f"{tool}: BLOCKED"
        result = {"error": f"Tool '{tool}' is disabled by user.", "exit_code": 1}
        logger.info(f"Tool blocked by user: {tool}")
        return desc, result

    if tool_policy and any(tool_policy.blocks(name) for name in policy_names):
        desc = f"{tool}: BLOCKED"
        result = {
            "error": f"Execution of tool '{tool}' is forbade by the active guide-only policy.",
            "exit_code": 1,
        }
        logger.warning("Tool policy blocked tool=%s", tool)
        return desc, result

    if tool in _ADMIN_TOOLS and not _owner_is_admin(owner):
        desc = f"{tool}: BLOCKED"
        result = {"error": f"Tool '{tool}' requires an admin user.", "exit_code": 1}
        logger.warning("Admin tool blocked for non-admin owner=%r tool=%s", owner, tool)
        return desc, result

    if is_public_blocked_tool(tool) and not _owner_is_admin(owner):
        desc = f"{tool}: BLOCKED"
        result = {
            "error": (
                f"Tool '{tool}' is restricted to admin users on this deployment. "
                "Ask an admin to perform this action or grant the needed permission."
            ),
            "exit_code": 1,
        }
        logger.warning("Public tool policy blocked owner=%r tool=%s", owner, tool)
        return desc, result


    # Background execution: a `bash` block whose first line is the `#!bg`
    # marker runs DETACHED — returns a job id immediately so the chat stream
    # isn't held open for a multi-minute install/ffmpeg/download. The always-on
    # monitor re-invokes the agent with the full output when the job finishes.
    if tool == "bash" and session_id:
        _is_bg, _bg_cmd = _split_bg_marker(content)
        if _is_bg and _bg_cmd:
            from src import bg_jobs
            rec = bg_jobs.launch(_bg_cmd, session_id=session_id, cwd=agent_cwd())
            short = _bg_cmd.strip().split(chr(10))[0][:80]
            desc = f"bash (background): {short}"
            result = {
                "output": (
                    f"Started background job `{rec['id']}`. It is running detached; "
                    f"do NOT wait for it or poll it. You will be automatically re-invoked "
                    f"with its full output when it finishes. Continue with other work, or "
                    f"end your turn now and resume when the result arrives. If the user "
                    f"later asks to check progress or stop it, call the manage_bg_jobs "
                    f"tool yourself (output or kill); do not tell them to run a tool "
                    f"command, and do not surface raw tool syntax in your reply."
                ),
                "exit_code": 0,
                "bg_job_id": rec["id"],
            }
            logger.info(f"Tool executed: {desc} -> bg job {rec['id']}")
            return desc, result

    # Route MCP-extracted tools through the MCP manager. Forward
    # the progress callback so long-running subprocess tools
    # (bash, python) can stream `tool_progress` events to the UI.
    if tool in _MCP_TOOL_MAP:
        first_line = content.split(chr(10))[0][:80]
        desc = f"{tool}: {first_line}"
        result = await _call_mcp_tool(tool, content, progress_cb=progress_cb)
    elif tool in ("grep", "glob", "ls", "get_workspace"):
        # Code-navigation tools — no MCP server; run the direct implementation.
        first_line = content.split(chr(10))[0][:80]
        desc = f"{tool}: {first_line}"
        result = await _direct_fallback(tool, content, progress_cb=progress_cb) \
            or {"error": f"{tool}: execution failed", "exit_code": 1}
    elif tool in ("apply_patch", "todowrite"):
        first_line = content.split(chr(10))[0][:80]
        desc = f"{tool}: {first_line}" if first_line else tool
        result = await _direct_fallback(tool, content, session_id=session_id, owner=owner) \
            or {"error": f"{tool}: execution failed", "exit_code": 1}
    elif tool == "manage_bg_jobs":
        # Inspect/kill detached `bash` jobs; needs session_id to scope to chat.
        desc = f"manage_bg_jobs: {content.split(chr(10))[0][:80]}"
        result = await _direct_fallback(tool, content, session_id=session_id, owner=owner) \
            or {"error": "manage_bg_jobs: execution failed", "exit_code": 1}
    elif tool in ("create_document", "update_document", "edit_document",
                  "suggest_document", "manage_documents"):
        desc = f"{tool}: {content.split(chr(10))[0][:80]}"
        result = await _document_tool_dispatch(
            tool,
            content,
            session_id,
            owner,
            document_id=approved_document_id,
            document_version=approved_document_version,
            document_digest=approved_document_digest,
        ) \
            or {"error": f"{tool}: execution failed", "exit_code": 1}
        if tool in ("edit_document", "suggest_document") and "title" in (result or {}):
            desc = f"{tool}: {result.get('title', '')}"
    elif tool == "search_chats":
        query = content.split("\n")[0].strip()
        desc = f"search_chats: {query[:80]}"
        result = await do_search_chats(query, owner=owner)
    elif tool in ("chat_with_model", "ask_teacher", "list_models"):
        # Migrated to the agent_tools registry (#3629): dispatched through
        # TOOL_HANDLERS with the owner/session ctx these tools need, instead
        # of the legacy dispatch_ai_tool elif. The impls live in
        # src/agent_tools/model_interaction_tools.py.
        first_line = content.split(chr(10))[0].strip()[:60]
        desc = f"{tool}: {first_line}" if first_line else tool
        result = await _document_tool_dispatch(tool, content, session_id, owner) \
            or {"error": f"{tool}: execution failed", "exit_code": 1}
    elif tool in ("create_session", "list_sessions", "send_to_session", "manage_session"):
        # Migrated to the agent_tools registry (#3629): dispatched through
        # TOOL_HANDLERS with the owner/session ctx these tools need. The impls
        # live in src/agent_tools/session_tools.py.
        first_line = content.split(chr(10))[0].strip()[:60]
        desc = f"{tool}: {first_line}" if first_line else tool
        result = await _document_tool_dispatch(tool, content, session_id, owner) \
            or {"error": f"{tool}: execution failed", "exit_code": 1}
    elif tool in ("pipeline", "manage_memory", "ui_control"):
        from src.ai_interaction import dispatch_ai_tool
        desc, result = await dispatch_ai_tool(tool, content, session_id, owner=owner)
    elif tool == "manage_tasks":
        desc = "manage_tasks"
        result = await do_manage_tasks(content, owner=owner)
    elif tool == "manage_skills":
        desc = "manage_skills"
        result = await do_manage_skills(content, owner=owner)
    elif tool == "api_call":
        first_line = content.split("\n")[0].strip()[:60]
        desc = f"api_call: {first_line}"
        result = await do_api_call(content)
    elif tool in ("manage_endpoints", "manage_mcp", "manage_webhooks", "manage_tokens", "manage_settings"):
        # Registry-dispatched (agent_tools.admin_tools); owner threaded for ownership/admin checks.
        desc = tool
        result = await _direct_fallback(tool, content, owner=owner) \
            or {"error": f"{tool}: execution failed", "exit_code": 1}
    elif tool == "manage_notes":
        desc = "manage_notes"
        result = await do_manage_notes(content, owner=owner)
    elif tool == "manage_calendar":
        desc = "manage_calendar"
        result = await do_manage_calendar(content, owner=owner)
    elif tool == "download_model":
        desc = "download_model"
        result = await do_download_model(content, owner=owner)
    elif tool == "serve_model":
        desc = "serve_model"
        result = await do_serve_model(content, owner=owner)
    elif tool == "list_served_models":
        desc = "list_served_models"
        result = await do_list_served_models(content, owner=owner)
    elif tool == "stop_served_model":
        desc = "stop_served_model"
        result = await do_stop_served_model(content, owner=owner)
    elif tool == "tail_serve_output":
        desc = "tail_serve_output"
        result = await do_tail_serve_output(content, owner=owner)
    elif tool == "list_downloads":
        desc = "list_downloads"
        result = await do_list_downloads(content, owner=owner)
    elif tool == "cancel_download":
        desc = "cancel_download"
        result = await do_cancel_download(content, owner=owner)
    elif tool == "search_hf_models":
        desc = "search_hf_models"
        result = await do_search_hf_models(content, owner=owner)
    elif tool == "list_cached_models":
        desc = "list_cached_models"
        result = await do_list_cached_models(content, owner=owner)
    elif tool == "app_api":
        desc = "app_api"
        result = await do_app_api(content, owner=owner)
    elif tool == "list_serve_presets":
        desc = "list_serve_presets"
        result = await do_list_serve_presets(content, owner=owner)
    elif tool == "serve_preset":
        desc = "serve_preset"
        result = await do_serve_preset(content, owner=owner)
    elif tool == "adopt_served_model":
        desc = "adopt_served_model"
        result = await do_adopt_served_model(content, owner=owner)
    elif tool == "list_cookbook_servers":
        desc = "list_cookbook_servers"
        result = await do_list_cookbook_servers(content, owner=owner)
    elif tool == "edit_image":
        desc = "edit_image"
        result = await do_edit_image(content, owner=owner)
    elif tool == "edit_file":
        result = await _direct_fallback(tool, content) or {"error": "edit failed", "exit_code": 1}
        desc = result.get("output") or result.get("error") or "edit_file"
    elif tool == "trigger_research":
        desc = "trigger_research"
        result = await do_trigger_research(content, owner=owner)
    elif tool == "manage_research":
        desc = "manage_research"
        result = await do_manage_research(content, owner=owner)
    elif tool == "resolve_contact":
        desc = "resolve_contact"
        result = await do_resolve_contact(content, owner=owner)
    elif tool == "manage_contact":
        desc = "manage_contact"
        result = await do_manage_contact(content, owner=owner)
    elif tool == "vault_search":
        desc = "vault_search"
        result = await do_vault_search(content, owner=owner)
    elif tool == "vault_get":
        desc = "vault_get"
        result = await do_vault_get(content, owner=owner)
    elif tool == "vault_unlock":
        desc = "vault_unlock"
        result = await do_vault_unlock(content, owner=owner)
    elif tool in BUILTIN_EMAIL_TOOLS:
        # Bare email tool name from fenced-block models (e.g. Ollama) — route to MCP email server.
        # Non-admin owners never reach here: BUILTIN_EMAIL_TOOLS ⊆ NON_ADMIN_BLOCKED_TOOLS,
        # so is_public_blocked_tool() above already rejected them.
        mcp = get_mcp_manager()
        qualified = f"mcp__email__{tool}"
        desc = f"email: {tool}"
        if mcp:
            _raw = content.strip()
            args = {}
            _args_error = None
            if _raw:
                # A non-empty body is always meant to be the call's arguments,
                # and every email tool takes a JSON object. Anything that
                # isn't one is a correctable error — NOT a silent empty-args
                # call, which would read the DEFAULT mailbox/folder instead of
                # the one the model meant (#3966 class). Only an EMPTY body
                # keeps the no-arg path (e.g. ```list_email_accounts```).
                try:
                    parsed = json.loads(_raw)
                except (json.JSONDecodeError, TypeError) as _je:
                    # Covers both `{account: "work"}` (looks like JSON, bad)
                    # and `account: work` (not JSON at all).
                    _args_error = (
                        f"'{tool}' arguments are not valid JSON ({_je}). "
                        'Send a JSON object, e.g. {"account": "work"} — '
                        "keys and string values need double quotes."
                    )
                else:
                    if isinstance(parsed, dict):
                        args = parsed
                    else:
                        _args_error = (
                            f"'{tool}' arguments must be a JSON object, "
                            'e.g. {"uid": "..."} — got a JSON array/value instead.'
                        )
            if _args_error is not None:
                result = {"error": _args_error, "exit_code": 1}
            else:
                if owner:
                    args = dict(args)
                    args[_EMAIL_MCP_OWNER_ARG] = owner
                result = await mcp.call_tool(qualified, args)
        else:
            result = {"error": "MCP manager not available", "exit_code": 1}
    elif tool.startswith("mcp__"):
        # MCP tool dispatch
        mcp = get_mcp_manager()
        if mcp:
            desc = f"mcp: {tool}"
            args, parse_error = _parse_qualified_mcp_args(tool, content)
            if parse_error:
                result = {"error": parse_error, "exit_code": 1}
            else:
                if tool.startswith("mcp__email__") and owner:
                    args = dict(args)
                    args[_EMAIL_MCP_OWNER_ARG] = owner
                result = await mcp.call_tool(tool, args)
        else:
            desc = f"mcp: {tool}"
            result = {"error": "MCP manager not available", "exit_code": 1}


    elif tool in dynamic_handlers:
        first_line = content.split(chr(10))[0][:80]
        desc = f"registry: {tool} {first_line}".strip()
        res = await _direct_fallback(tool, content, progress_cb=progress_cb)

        if isinstance(res, tuple):
            desc, result = res
        else:
            result = res or {"error": f"{tool}: execution failed", "exit_code": 1}

    else:
        desc = f"unknown: {tool}"
        result = {
            "error": f"Unknown tool: {tool}",
            "exit_code": 1
        }

    logger.info(f"Tool executed: {desc} -> exit_code={result.get('exit_code', 'n/a')}")
    return desc, result


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------

# Keys handled by the dedicated branches below — never echo them as raw JSON.
_FORMATTER_HANDLED_KEYS = {
    "stdout", "stderr", "exit_code", "content", "size",
    "response", "results", "session_id", "name", "model", "session_name",
    "success", "path", "action", "title", "doc_id", "version", "applied",
    "error", "output",
}


def format_tool_result(description: str, result: Dict) -> str:
    """Format a tool result into text for feeding back to the LLM."""
    parts = [f"### {description}"]

    if "stdout" in result:
        if result["stdout"]:
            parts.append(f"**stdout:**\n```\n{result['stdout']}\n```")
        if result["stderr"]:
            parts.append(f"**stderr:**\n```\n{result['stderr']}\n```")
        parts.append(f"**exit_code:** {result.get('exit_code', 'unknown')}")
    elif "output" in result:
        # bash / python canonical result shape: {"output": ..., "exit_code": ...}
        parts.append(f"```\n{result['output']}\n```")
        if result.get("exit_code") not in (0, None):
            parts.append(f"**exit_code:** {result['exit_code']}")
    elif "content" in result:
        parts.append(f"**content ({result.get('size', '?')} chars):**\n```\n{result['content']}\n```")
    elif "response" in result:
        model = result.get("model", result.get("session_name", ""))
        if model:
            parts.append(f"**{model} responded:**\n{result['response']}")
        else:
            parts.append(result["response"])
    elif "results" in result:
        parts.append(result["results"])
    elif "session_id" in result and "name" in result:
        parts.append(f"Session created: **{result['name']}** (id: `{result['session_id']}`, model: {result.get('model', 'unknown')})")
    elif "success" in result:
        if result["success"]:
            parts.append(f"File written: {result['path']} ({result['size']} bytes)")
        else:
            parts.append(f"Error: {result.get('error', 'unknown')}")
    elif "action" in result:
        action = result["action"]
        if action == "create":
            parts.append(f"Document created: \"{result.get('title', '')}\" (id: {result['doc_id']}, v{result['version']})")
        elif action == "update":
            parts.append(f"Document updated: \"{result.get('title', '')}\" (v{result['version']})")
        elif action == "edit":
            parts.append(f'Document edited: "{result.get("title", "")}" (v{result.get("version", "?")}, {result.get("applied", 0)} edit(s) applied)')
    elif "error" in result:
        parts.append(f"**Error:** {result['error']}")

    # Surface any additional structured payload (events, tasks, notes, calendars,
    # documents, attachments, etc.) that the dedicated branches above don't show.
    # Without this, tools that return {"response": "...", "events": [...]} would
    # silently drop the events list and the model would only see the summary line.
    extra = {k: v for k, v in result.items() if k not in _FORMATTER_HANDLED_KEYS}
    if extra:
        try:
            extra_json = json.dumps(extra, indent=2, default=str, ensure_ascii=False)
            # Cap to avoid blowing the context window on huge payloads.
            if len(extra_json) > 8000:
                extra_json = extra_json[:8000] + f"\n... (truncated, {len(extra_json)} chars total)"
            parts.append(f"**data:**\n```json\n{extra_json}\n```")
        except (TypeError, ValueError):
            pass

    return "\n".join(parts)

# _ODY_V34_EXECUTION_EXTENSION
# Wrap the real dispatcher owner. Existing execution stays untouched.
import asyncio as _ody_v34_asyncio
import functools as _ody_v34_functools
import json as _ody_v34_json
import subprocess as _ody_v34_subprocess
import sys as _ody_v34_sys

_ody_v34_original_execute_tool_block = execute_tool_block


def _ody_v34_asset_argv(args, owner=None):
    if not isinstance(args, dict):
        raise ValueError("manage_assets arguments must be an object")

    action = str(args.get("action") or "")
    argv = [_ody_v34_sys.executable, "-m", "src.asset_inventory"]
    owner = str(owner or "").strip()

    def _with_owner(command):
        return argv + [command] + (["--owner", owner] if owner else [])

    if action == "summary":
        return _with_owner("summary")

    if action in ("list", "search"):
        argv = _with_owner(action)
        if args.get("query"):
            argv.append(str(args["query"]))
        if args.get("type"):
            argv += ["--type", str(args["type"])]
        if args.get("status"):
            argv += ["--status", str(args["status"])]
        if args.get("limit") is not None:
            argv += ["--limit", str(max(1, min(int(args["limit"]), 500)))]
        return argv

    if action == "get":
        return _with_owner("get") + [str(args["asset"])]

    if action == "add":
        argv = _with_owner("add") + ["--name", str(args["name"])]
        for key in (
            "id", "type", "status", "manufacturer", "model", "serial",
            "system_uuid", "hostname", "mac", "location", "notes", "source"
        ):
            if args.get(key) is not None:
                argv += ["--" + key.replace("_", "-"), str(args[key])]
        if args.get("confidence") is not None:
            argv += ["--confidence", str(float(args["confidence"]))]
        if args.get("attributes") is not None:
            if not isinstance(args["attributes"], dict):
                raise ValueError("attributes must be an object")
            argv += [
                "--attributes",
                _ody_v34_json.dumps(args["attributes"], sort_keys=True),
            ]
        return argv

    if action == "update":
        argv = _with_owner("update") + [str(args["asset"])]
        for key in (
            "name", "type", "status", "manufacturer", "model", "serial",
            "system_uuid", "hostname", "mac", "location", "notes", "source"
        ):
            if args.get(key) is not None:
                argv += ["--" + key.replace("_", "-"), str(args[key])]
        if args.get("confidence") is not None:
            argv += ["--confidence", str(float(args["confidence"]))]
        if args.get("attributes") is not None:
            if not isinstance(args["attributes"], dict):
                raise ValueError("attributes must be an object")
            argv += [
                "--attributes",
                _ody_v34_json.dumps(args["attributes"], sort_keys=True),
            ]
        return argv

    if action == "record_observation":
        argv = _with_owner("observe") + [
            "--kind",
            str(args.get("kind") or "observation"),
        ]
        if args.get("asset"):
            argv += ["--asset", str(args["asset"])]
        if args.get("source"):
            argv += ["--source", str(args["source"])]
        if args.get("confidence") is not None:
            argv += ["--confidence", str(float(args["confidence"]))]
        if args.get("data") is not None:
            if not isinstance(args["data"], dict):
                raise ValueError("data must be an object")
            argv += [
                "--json",
                _ody_v34_json.dumps(args["data"], sort_keys=True),
            ]
        elif args.get("text") is not None:
            argv += ["--text", str(args["text"])]
        return argv

    if action == "link_component":
        argv = _with_owner("link") + [
            str(args["parent"]),
            str(args["child"]),
            "--relation",
            str(args.get("relation") or "installed_in"),
        ]
        if args.get("source"):
            argv += ["--source", str(args["source"])]
        if args.get("notes"):
            argv += ["--notes", str(args["notes"])]
        return argv

    if action == "unlink_component":
        return _with_owner("unlink") + [
            "--parent", str(args["parent"]),
            "--child", str(args["child"]),
            "--relation", str(args.get("relation") or "installed_in"),
        ]

    if action == "retire":
        return _with_owner("retire") + [str(args["asset"])]

    if action == "merge":
        argv = _with_owner("merge") + [
            str(args["source_asset"]),
            str(args["target_asset"]),
        ]
        if args.get("reason"):
            argv += ["--reason", str(args["reason"])]
        return argv

    raise ValueError("unsupported manage_assets action: " + action)


async def _execute_manage_assets_binding(block, owner=None):
    try:
        if not owner:
            raise PermissionError("authenticated IT asset owner is required")
        payload = _ody_v34_json.loads(block.content or "{}")
        argv = _ody_v34_asset_argv(payload, owner=owner)

        def _run():
            return _ody_v34_subprocess.run(
                argv, cwd="/app", text=True, capture_output=True,
                timeout=45, check=False,
            )

        cp = await _ody_v34_asyncio.to_thread(_run)
        output = (cp.stdout or "") + (cp.stderr or "")
        if cp.returncode != 0:
            return "manage_assets", {
                "error": output[-2000:] or "canonical IT asset read failed",
                "output": output[-30000:], "exit_code": cp.returncode,
            }
        try:
            parsed = _ody_v34_json.loads(cp.stdout or "")
        except (TypeError, ValueError) as exc:
            return "manage_assets", {
                "error": f"canonical IT asset service returned invalid structured data: {exc}",
                "output": output[-30000:], "exit_code": 1,
            }
        action = str(payload.get("action") or "")
        if action in {"list", "search"} and isinstance(parsed, list):
            data = {
                "status": "EMPTY_RESULT" if not parsed else "SUCCESS",
                "assets": parsed,
                "asset_count": len(parsed),
                "source": "canonical_it_asset_cmdb",
                "owner_scope": str(owner or "authenticated_owner"),
            }
        elif action == "summary" and isinstance(parsed, dict):
            data = {
                "status": "SUCCESS",
                **parsed,
                "source": "canonical_it_asset_cmdb",
                "owner_scope": str(owner or "authenticated_owner"),
            }
        else:
            data = {
                "status": "SUCCESS",
                "result": parsed,
                "source": "canonical_it_asset_cmdb",
                "owner_scope": str(owner or "authenticated_owner"),
            }
        return "manage_assets", {
            "output": _ody_v34_json.dumps(data, default=str, sort_keys=True),
            "exit_code": 0,
            "success": True,
            "data": data,
        }
    except Exception as exc:
        return "manage_assets", {"error": str(exc), "output": str(exc), "exit_code": 1}


async def _execute_privileged_action_binding(block, owner=None):
    try:
        payload = _ody_v34_json.loads(block.content or "{}")
        from src.privileged_broker import client_request as _ody_v34_priv_request
        data = await _ody_v34_asyncio.to_thread(_ody_v34_priv_request, payload)
        return "privileged_action", {
            "output": _ody_v34_json.dumps(data, indent=2, sort_keys=True),
            "exit_code": 0 if data.get("ok") else 1,
            "data": data,
        }
    except Exception as exc:
        return "privileged_action", {"error": str(exc), "output": str(exc), "exit_code": 1}


async def _execute_manage_homelab_binding(block, owner=None):
    try:
        payload = _ody_v34_json.loads(block.content or "{}")
        from src.homelab_operations import HomelabOperations
        # The ActionSpec/exact-approval gate has already run in the dispatcher
        # before this binding is reached.  Bind the narrowly scoped host
        # operator profile for the structured Homelab capability so its
        # approved scanner/broker operation is not accidentally downgraded to
        # the ordinary chat profile.  The context-local binding is reset on
        # every return path.
        from src.execution_profiles import use_execution_profile
        with use_execution_profile("privileged_host"):
            result = await HomelabOperations().execute(payload, owner=str(owner or ""))
        return "manage_homelab", {"output": _ody_v34_json.dumps(result, indent=2, sort_keys=True), "exit_code": 0, "data": result}
    except Exception as exc:
        return "manage_homelab", {"error": str(exc), "output": str(exc), "exit_code": 1}


async def _execute_manage_osint_binding(block, owner=None):
    try:
        payload = _ody_v34_json.loads(block.content or "{}")
        read_action = str(payload.get("action") or "").strip().casefold()
        if read_action in {"list_cases", "get_case"}:
            if not owner:
                raise PermissionError("authenticated OSINT owner is required")
            from src.osint_read import get_case, list_cases
            result = list_cases(owner, limit=int(payload.get("limit") or 50)) if read_action == "list_cases" else get_case(owner, str(payload.get("case_id") or payload.get("target") or ""))
            return "manage_osint", {"output": _ody_v34_json.dumps(result, default=str, sort_keys=True), "exit_code": 0, "success": True, "data": result}
        from src.osint_policy import build_plan, validate_request
        action, target, objective, sources = validate_request(payload)
        if action == "plan":
            result = build_plan(target, objective, sources)
        elif action == "search":
            from src.agent_tools.web_tools import WebSearchTool
            result = await WebSearchTool().execute(_ody_v34_json.dumps({"query": f"{target} {objective}"}), {})
        else:
            from src.agent_tools.web_tools import WebFetchTool
            result = await WebFetchTool().execute(target, {})
        return "manage_osint", {"output": _ody_v34_json.dumps(result, indent=2, sort_keys=True), "exit_code": int(result.get("exit_code", 0)), "data": result, "untrusted_content": action != "plan"}
    except Exception as exc:
        return "manage_osint", {"error": str(exc), "output": str(exc), "exit_code": 1}


async def _execute_security_assessment_binding(block, owner=None):
    """Expose only read projections to the agent transport in V1."""
    try:
        payload = _ody_v34_json.loads(block.content or "{}")
        from core.database import SessionLocal
        from src.security_assessment import SecurityAssessmentService
        if not owner:
            raise ValueError("an authenticated assessment owner is required")
        action = str(payload.get("action") or "").strip().casefold()
        with SessionLocal() as db:
            service = SecurityAssessmentService(db)
            if action == "list_engagements":
                result = {"engagements": service.list_engagements(str(owner))}
            elif action == "get_engagement":
                result = service.get_engagement(str(owner), str(payload.get("engagement_id") or ""))
            elif action == "list_findings":
                from core.security_assessment_models import SecurityFinding
                result = {"findings": [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in db.query(SecurityFinding).filter_by(owner=str(owner)).all()]}
            elif action == "list_evidence":
                from core.security_assessment_models import SecurityEvidence
                result = {"evidence": [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in db.query(SecurityEvidence).filter_by(owner=str(owner)).all()]}
            else:
                raise ValueError("unsupported read-only security assessment action")
        result = _with_canonical_read_status(result)
        return "manage_security_assessment", {"output": _ody_v34_json.dumps(result, default=str, indent=2, sort_keys=True), "exit_code": 0, "success": True, "data": result}
    except Exception as exc:
        return "manage_security_assessment", {"error": str(exc), "output": str(exc), "exit_code": 1}


async def _execute_read_memory_binding(block, owner=None):
    """Adapt the canonical Brain store to the capability binding boundary."""
    try:
        payload = _ody_v34_json.loads(block.content or "{}")
        action = str(payload.get("action") or "").strip().casefold()
        if action not in {"summarize_owner_memory", "search_memory", "inspect_memory"}:
            raise ValueError("unsupported read-only memory action")
        from src import ai_interaction
        from src.memory_grounding import build_explicit_memory_result
        result = build_explicit_memory_result(
            ai_interaction._memory_manager,
            owner,
            str(payload.get("query") or "what do you remember about me"),
        )
        success = result.get("status") in {"ok", "zero_result"}
        return "read_memory", {
            "output": _ody_v34_json.dumps(result, default=str, sort_keys=True),
            "exit_code": 0 if success else 1,
            "success": success,
            "data": result,
        }
    except Exception as exc:
        return "read_memory", {"error": str(exc), "output": str(exc), "exit_code": 1}


def _with_canonical_read_status(result: Any) -> dict[str, Any]:
    """Attach an explicit status without changing a domain's payload shape.

    Read adapters historically returned useful domain dictionaries but left
    empty-list interpretation to the model.  The control plane needs a
    machine-readable distinction: an empty canonical collection is not a
    failed or unavailable read. Existing explicit domain statuses are retained
    verbatim for compatibility; only status-less structured results are
    classified here.
    """
    if not isinstance(result, dict):
        return {"status": "INVALID_RESULT", "data": result}
    explicit_status = str(result.get("status") or "").strip().upper()
    if explicit_status and explicit_status not in {"SUCCESS", "SUCCESS_EMPTY", "SUCCESS_WITH_DATA"}:
        return result
    if result.get("unavailable") is True:
        return {"status": "UNAVAILABLE", **result}
    if result.get("error"):
        return {"status": "FAILED", **result}

    # A structured overview may contain a deliberately unprojected or
    # unavailable subdomain (for example Contacts while the CardDAV provider
    # has no proven owner boundary). Do not flatten that partial truth into an
    # apparently complete empty result. Preserve the nested detail and mark
    # the enclosing read degraded for model/UI grounding.
    def _nested_status(value: Any) -> str | None:
        if isinstance(value, dict):
            nested = str(value.get("status") or "").strip().upper()
            if nested in {"DEGRADED", "NOT_PROJECTED", "UNAVAILABLE", "FAILED"}:
                return nested
            for child in value.values():
                found = _nested_status(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = _nested_status(child)
                if found:
                    return found
        return None

    nested_status = _nested_status(result)
    if nested_status and explicit_status not in {"DEGRADED", "UNAVAILABLE", "FAILED"}:
        return {**result, "status": "DEGRADED", "degraded_reason": nested_status}
    if explicit_status:
        return result
    collections = [value for value in result.values() if isinstance(value, list)]
    status = "SUCCESS_EMPTY" if collections and not any(collections) else "SUCCESS_WITH_DATA"
    return {"status": status, **result}


async def _execute_read_work_binding(block, owner=None):
    """Adapt the canonical WorkEngine projections to a read-only binding."""
    try:
        payload = _ody_v34_json.loads(block.content or "{}")
        action = str(payload.get("action") or "").strip().casefold()
        allowed = {"overview", "review", "attention", "context", "list_goals", "list_projects", "list_tasks", "list_runs", "list_commitments", "list_missions", "list_watches"}
        if action not in allowed:
            raise ValueError("unsupported read-only Work action")
        if not owner:
            raise PermissionError("authenticated Work owner is required")
        from core.database import SessionLocal
        from core.persistent_agent_models import Monitor
        from core.work_models import WorkCommitment, WorkGoal, WorkProject, WorkRun, WorkTask
        from src.mission_projection import MissionService
        from src.work_engine import WorkEngine
        with SessionLocal() as db:
            service = WorkEngine(db)
            if action == "overview":
                result = {
                    "goals": service.list_records(owner, WorkGoal, status="active"),
                    "projects": service.list_records(owner, WorkProject, status="active"),
                    "tasks": service.list_records(owner, WorkTask),
                    "runs": service.list_records(owner, WorkRun),
                    "commitments": service.list_records(owner, WorkCommitment, status="open"),
                }
            elif action == "review":
                result = service.life_review(owner, horizon_hours=int(payload.get("horizon_hours") or 48))
            elif action == "attention":
                from src.persistent_agent import PersistentAgent
                result = PersistentAgent(db).attention(owner)
            elif action == "context":
                result = service.context(owner, goal_id=payload.get("goal_id"), project_id=payload.get("project_id"), task_id=payload.get("task_id"), run_id=payload.get("run_id"))
            elif action == "list_missions":
                missions = MissionService(db).list(owner, lifecycle=payload.get("lifecycle"), limit=int(payload.get("limit") or 200))
                result = {"missions": missions, "status": "SUCCESS" if missions else "EMPTY_RESULT"}
            elif action == "list_watches":
                watches = db.query(Monitor).filter_by(owner=owner).order_by(Monitor.updated_at.desc()).limit(max(1, min(int(payload.get("limit") or 200), 500))).all()
                result = {"watches": [
                    {column.name: (getattr(row, column.name).isoformat() if hasattr(getattr(row, column.name), "isoformat") else getattr(row, column.name)) for column in row.__table__.columns}
                    for row in watches
                ], "status": "SUCCESS" if watches else "EMPTY_RESULT"}
            else:
                models = {"list_goals": (WorkGoal, None), "list_projects": (WorkProject, None), "list_tasks": (WorkTask, None), "list_runs": (WorkRun, None), "list_commitments": (WorkCommitment, "open")}
                model, status = models[action]
                result = {action.removeprefix("list_"): service.list_records(owner, model, status=status)}
        result = _with_canonical_read_status(result)
        return "read_work", {"output": _ody_v34_json.dumps(result, default=str, sort_keys=True), "exit_code": 0, "success": True, "data": result}
    except Exception as exc:
        return "read_work", {"error": str(exc), "output": str(exc), "exit_code": 1}


async def _execute_read_household_binding(block, owner=None):
    """Adapt canonical Household Inventory reads to the binding registry."""
    try:
        payload = _ody_v34_json.loads(block.content or "{}")
        action = str(payload.get("action") or "").strip().casefold()
        allowed = {"overview", "list_items", "search_items", "get_item"}
        if action not in allowed:
            raise ValueError("unsupported read-only Household action")
        if not owner:
            raise PermissionError("authenticated Household owner is required")
        from src.inventory_service import get_inventory_service
        service = get_inventory_service()
        if action == "overview":
            result = service.household_overview(owner, expiry_days=int(payload.get("expiry_days") or 30))
        elif action == "list_items":
            result = {"items": service.list_items(owner, domain=payload.get("domain"))}
        elif action == "search_items":
            query = str(payload.get("query") or "").strip()
            if not query:
                raise ValueError("query is required for search_items")
            result = {"items": service.search_items(owner, query, domain=payload.get("domain"))}
        else:
            item_id = str(payload.get("item_id") or "").strip()
            if not item_id:
                raise ValueError("item_id is required for get_item")
            result = {"item": service.get_item(owner, item_id), "lots": service.list_lots(owner, item_id)}
        result = _with_canonical_read_status(result)
        return "read_household", {"output": _ody_v34_json.dumps(result, default=str, sort_keys=True), "exit_code": 0, "success": True, "data": result}
    except Exception as exc:
        return "read_household", {"error": str(exc), "output": str(exc), "exit_code": 1}


async def _execute_read_setup_binding(block, owner=None):
    """Adapt Setup Center's secret-free owner projection to a read binding."""
    try:
        payload = _ody_v34_json.loads(block.content or "{}")
        action = str(payload.get("action") or "").strip().casefold()
        if action not in {"state", "integrations", "permissions"}:
            raise ValueError("unsupported read-only Setup action")
        if not owner:
            raise PermissionError("authenticated Setup owner is required")
        from src.setup_center import SetupCenterService
        service = SetupCenterService()
        result = {"state": service.projection, "integrations": service.integrations_projection, "permissions": service.permissions_projection}[action](str(owner))
        if result.get("secrets_exposed") or result.get("secret_values_exposed"):
            raise ValueError("Setup projection violated secret-free contract")
        result = _with_canonical_read_status(result)
        return "read_setup", {"output": _ody_v34_json.dumps(result, default=str, sort_keys=True), "exit_code": 0, "success": True, "data": result}
    except Exception as exc:
        return "read_setup", {"error": str(exc), "output": str(exc), "exit_code": 1}


async def _execute_read_career_binding(block, owner=None):
    """Adapt the durable Career projection; never synthesize provider jobs."""
    try:
        payload = json.loads(block.content or "{}")
        if not owner:
            raise PermissionError("authenticated Career owner is required")
        from core.database import SessionLocal
        from src.career_service import CareerService
        with SessionLocal() as db:
            result = CareerService(db).read(str(owner), str(payload.get("action") or "overview"))
        result = _with_canonical_read_status(result)
        return "read_career", {"output": json.dumps(result, default=str, sort_keys=True), "exit_code": 0, "success": True, "data": result}
    except Exception as exc:
        return "read_career", {"error": str(exc), "output": str(exc), "exit_code": 1}


async def _execute_read_communications_binding(block, owner=None):
    """Adapt the existing owner-scoped Communications overview to a read binding."""
    try:
        payload = _ody_v34_json.loads(block.content or "{}")
        action = str(payload.get("action") or "overview").strip().casefold()
        if action not in {"overview", "contacts"}:
            raise ValueError("unsupported read-only Communications action")
        if not owner:
            raise PermissionError("authenticated Communications owner is required")
        if action == "contacts":
            # The existing CardDAV provider is global in its storage layer.
            # Reuse its established security boundary: only an authenticated
            # admin/single-user owner may receive that provider projection.
            from src.tool_security import owner_is_admin_or_single_user
            if not owner_is_admin_or_single_user(owner):
                result = {
                    "status": "UNAVAILABLE",
                    "error_code": "OWNER_BOUNDARY_UNAVAILABLE",
                    "reason": "CardDAV contacts are not owner-isolated for this account",
                    "contacts": [],
                }
                return "read_communications", {"output": _ody_v34_json.dumps(result, sort_keys=True), "exit_code": 0, "success": True, "data": result}
            import asyncio
            from routes.contacts_routes import _fetch_contacts
            rows = await asyncio.to_thread(_fetch_contacts)
            contacts = []
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                contacts.append({
                    key: row.get(key)
                    for key in ("uid", "name", "emails", "phones", "address")
                    if row.get(key) is not None
                })
            result = {
                "status": "SUCCESS_WITH_DATA" if contacts else "SUCCESS_EMPTY",
                "source": "canonical_carddav_contacts",
                "owner_scope": "admin_or_single_user",
                "contacts": contacts,
            }
            return "read_communications", {"output": _ody_v34_json.dumps(result, default=str, sort_keys=True), "exit_code": 0, "success": True, "data": result}
        from datetime import datetime, timedelta
        from sqlalchemy import and_, or_
        from core.database import CalendarCal, CalendarEvent, EmailAccount, SessionLocal
        now = datetime.utcnow()
        horizon = now + timedelta(days=14)
        with SessionLocal() as db:
            accounts = db.query(EmailAccount).filter(
                or_(
                    EmailAccount.owner == owner,
                    and_(or_(EmailAccount.owner.is_(None), EmailAccount.owner == ""), EmailAccount.from_address == owner),
                )
            ).order_by(EmailAccount.is_default.desc(), EmailAccount.created_at.asc()).all()
            calendars = db.query(CalendarCal).filter(CalendarCal.owner == owner).all()
            calendar_ids = [calendar.id for calendar in calendars]
            events = []
            if calendar_ids:
                events = db.query(CalendarEvent).filter(
                    CalendarEvent.calendar_id.in_(calendar_ids),
                    CalendarEvent.status != "cancelled",
                    CalendarEvent.dtstart < horizon,
                    CalendarEvent.dtend >= now,
                ).order_by(CalendarEvent.dtstart).limit(20).all()
            result = {
                "status": "SUCCESS" if accounts or calendars or events else "SUCCESS_EMPTY",
                "source": "canonical_email_accounts_and_calendar",
                "email": {
                    "configured": len(accounts),
                    "enabled": sum(1 for account in accounts if account.enabled),
                    "accounts": [
                        {"id": account.id, "name": account.name, "enabled": bool(account.enabled), "default": bool(account.is_default)}
                        for account in accounts
                    ],
                },
                "calendar": {
                    "calendars": len(calendars),
                    "upcoming_14_days": len(events),
                    "events": [
                        {"uid": event.uid, "summary": event.summary, "dtstart": event.dtstart.isoformat(), "calendar_id": event.calendar_id}
                        for event in events
                    ],
                },
                "contacts": {"status": "NOT_PROJECTED", "reason": "CardDAV contact ownership is not yet a canonical read binding"},
            }
        result = _with_canonical_read_status(result)
        return "read_communications", {"output": _ody_v34_json.dumps(result, default=str, sort_keys=True), "exit_code": 0, "success": True, "data": result}
    except Exception as exc:
        return "read_communications", {"error": str(exc), "output": str(exc), "exit_code": 1}


_CAPABILITY_V1_EXECUTORS = {
    "manage_assets": _execute_manage_assets_binding,
    "privileged_action": _execute_privileged_action_binding,
    "manage_homelab": _execute_manage_homelab_binding,
    "manage_osint": _execute_manage_osint_binding,
    "manage_security_assessment": _execute_security_assessment_binding,
    "read_memory": _execute_read_memory_binding,
    "read_work": _execute_read_work_binding,
    "read_household": _execute_read_household_binding,
    "read_setup": _execute_read_setup_binding,
    "read_career": _execute_read_career_binding,
    "read_communications": _execute_read_communications_binding,
}


async def execute_registered_binding(*, tool_name, payload, owner=None, **security_context):
    """Bridge a validated Work Action to the existing ToolBinding registry.

    WorkEngine owns validation, approval, locks, and result persistence. This
    helper only invokes the registered binding and rejects unknown executors;
    it never accepts a model-supplied command or alternate executor.
    """
    from types import SimpleNamespace
    from src.tool_bindings import binding_for_tool
    binding = binding_for_tool(str(tool_name or ""))
    if binding is None or binding.executor_key not in _CAPABILITY_V1_EXECUTORS:
        raise ValueError("registered action binding is unavailable")
    if not isinstance(payload, dict):
        raise ValueError("registered binding payload must be an object")
    block = SimpleNamespace(tool_type=binding.transport_name, content=_ody_v34_json.dumps(payload, sort_keys=True))
    # Headless callers must opt into the explicit no-taint context. This keeps
    # the adapter usable for canonical reads while ensuring consequential
    # calls cannot silently omit the shared dispatcher context.
    security_context.setdefault("security_context", NO_TOOL_SECURITY_CONTEXT)
    result = await execute_tool_block(block, owner=owner, **security_context)
    if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[1], dict):
        raise ValueError("registered binding returned an invalid result")
    name, data = result
    normalized = dict(data)
    normalized.setdefault("binding", name)
    normalized.setdefault("success", normalized.get("exit_code", 1) == 0 and not normalized.get("error"))
    return normalized


def _validate_registered_result(block, result):
    """Fail closed on a malformed success-shaped first-class Result."""
    if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[1], dict):
        return result
    name, data = result
    if data.get("error") or data.get("blocked") or not isinstance(data.get("data"), dict):
        return result
    from src.capability_registry import action_for_tool
    action = action_for_tool(block.tool_type, block.content)
    if action is None:
        return result
    from src.intent_contracts import validate_bound_result
    valid, status = validate_bound_result(block.tool_type, action.action_id, data["data"])
    if valid:
        return result
    invalid = dict(data)
    invalid.update({
        "success": False,
        "exit_code": 1,
        "status": "INVALID_RESULT",
        "error_code": "RESULT_INVALID",
        "error": f"registered ActionSpec result contract rejected payload ({status})",
    })
    return name, invalid


@_ody_v34_functools.wraps(_ody_v34_original_execute_tool_block)
async def execute_tool_block(block, *args, **kwargs):
    from src.tool_bindings import binding_for_tool
    binding = binding_for_tool(block.tool_type)
    executor = _CAPABILITY_V1_EXECUTORS.get(binding.executor_key) if binding else None
    if executor is not None:
        # This is a trusted-caller-only narrowing credential. It is never
        # read from model tool arguments and cannot replace policy, approval,
        # owner isolation, disabled-tools, or broker authorization.
        grant_id = kwargs.get("delegated_grant_id")
        from src.capability_registry import action_for_tool
        action = action_for_tool(block.tool_type, block.content)
        exact_approval = kwargs.get("exact_approval")
        if action is None or not action.known:
            return (f"{block.tool_type}: BLOCKED", {"error": "Unknown registered ActionSpec.", "exit_code": 1, "blocked": True, "policy": "actionspec"})
        if action.approval.value == "exact" and exact_approval is None and not grant_id:
            return (f"{block.tool_type}: BLOCKED", {"error": "This exact ActionSpec requires exact approval.", "exit_code": 1, "blocked": True, "policy": "exact_tool_approval"})
        if grant_id:
            owner = kwargs.get("owner")
            if not owner:
                return (f"{block.tool_type}: BLOCKED", {"error": "delegated grant requires an authenticated owner", "exit_code": 1, "blocked": True, "policy": "delegated_capability_grant"})
            try:
                from core.database import SessionLocal
                from src.delegated_grants import DelegatedGrantService
                with SessionLocal() as db:
                    DelegatedGrantService(db).consume(str(owner), str(grant_id), {
                        "run_id": kwargs.get("delegated_grant_run_id"),
                        "action_id": kwargs.get("delegated_grant_action_id"),
                        "capability_id": kwargs.get("delegated_grant_capability_id") or binding.capability_id,
                        "sealed_input_digest": kwargs.get("delegated_grant_digest"),
                        "target_resource": kwargs.get("delegated_grant_target_resource"),
                    })
            except Exception as exc:
                return (f"{block.tool_type}: BLOCKED", {"error": str(exc), "exit_code": 1, "blocked": True, "policy": "delegated_capability_grant"})
        kwargs.setdefault("security_context", NO_TOOL_SECURITY_CONTEXT)
        kwargs["_registered_executor"] = executor
        kwargs.pop("delegated_grant_id", None)
        kwargs.pop("delegated_grant_run_id", None)
        kwargs.pop("delegated_grant_action_id", None)
        kwargs.pop("delegated_grant_capability_id", None)
        kwargs.pop("delegated_grant_digest", None)
        kwargs.pop("delegated_grant_target_resource", None)
        executed = await _ody_v34_original_execute_tool_block(block, *args, **kwargs)
        return _validate_registered_result(block, executed)

    return await _ody_v34_original_execute_tool_block(
        block,
        *args,
        **kwargs,
    )
