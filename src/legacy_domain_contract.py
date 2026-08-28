"""Compatibility projections for the retired prompt domain map.

This module contains descriptive tool visibility metadata used by legacy prompt
callers.  Canonical capability identity, policy, execution, and result truth
remain owned by the ACI registries and contracts.
"""

from __future__ import annotations

from src.tool_bindings import TOOL_BINDINGS, tools_for_domains
from src.tool_overrides import get_builtin_overrides
from src.tool_policy import WEB_TOOL_NAMES


DOMAIN_TOOL_MAP = {
    "web": set(WEB_TOOL_NAMES),
    "documents": {"create_document", "edit_document", "update_document", "suggest_document", "manage_documents"},
    "email": {"list_email_accounts", "list_emails", "read_email", "scan_email_unsubscribes", "unsubscribe_email", "send_email", "reply_to_email", "bulk_email", "archive_email", "delete_email", "mark_email_read", "resolve_contact", "manage_contact"},
    "cookbook": {"download_model", "serve_model", "serve_preset", "list_serve_presets", "list_served_models", "stop_served_model", "tail_serve_output", "list_downloads", "cancel_download", "search_hf_models", "list_cached_models", "list_cookbook_servers", "adopt_served_model"},
    "notes_calendar_tasks": {"manage_notes", "manage_calendar", "manage_tasks"},
    "memory": {"manage_memory"},
    "ui": {"ui_control"},
    "sessions": {"create_session", "list_sessions", "manage_session", "send_to_session", "search_chats"},
    "files": {"bash", "python", "read_file", "write_file", "edit_file", "apply_patch", "todowrite", "grep", "glob", "ls", "get_workspace", "manage_bg_jobs"},
    "operations": {"bash", "read_file", "grep", "glob", "ls", "get_workspace"},
    "network_ops": {"bash", "read_file", "grep", "ls"},
    "storage_ops": {"bash", "read_file", "grep", "ls"},
    "system_ops": {"bash", "read_file", "grep", "ls"},
    "container_ops": {"bash", "read_file", "grep", "glob", "ls", "get_workspace"},
    "remote_ops": {"bash", "read_file", "grep"},
    "security_audit": {"bash", "read_file", "grep", "ls"},
    "pentest_ops": {"bash", "read_file", "grep", "ls", "python"},
    "osint": {"manage_osint", "web_search", "web_fetch", "trigger_research"},
    "homelab": {"manage_homelab"},
    "shell_exec": {"bash"},
    "settings": {"manage_settings", "manage_endpoints", "manage_mcp", "manage_webhooks", "manage_tokens", "app_api"},
    "communications": {"read_communications"},
    "contacts": {"resolve_contact", "manage_contact"},
    "integrations": {"api_call"},
    "asset_inventory": {"manage_assets"},
    "developer": {"developer_read"},
}

# Keep the compatibility map in sync with the descriptive ToolBinding domains.
for _binding in TOOL_BINDINGS.values():
    for _domain in _binding.domains:
        DOMAIN_TOOL_MAP.setdefault(_domain, set()).add(_binding.transport_name)


CANONICAL_TOOLS_FOR_DOMAINS = tools_for_domains
BUILTIN_OVERRIDES = get_builtin_overrides
