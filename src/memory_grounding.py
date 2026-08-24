"""Canonical, owner-scoped memory grounding for explicit user queries.

Passive memory recall is intentionally small and relevance-ranked.  Explicit
questions about what Hades remembers are different: they must read the Brain
store itself and give the model a structured, authoritative result.  This
module is only a projection/helper; it does not introduce another memory
store or retrieval engine.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from src.memory import MemoryStoreUnreadable


_EXPLICIT_MEMORY_RE = re.compile(
    r"\b(?:what\s+do\s+you\s+(?:remember|know)\s+about\s+me|"
    r"what\s+(?:personal\s+)?information\s+do\s+you\s+have\s+stored\s+about\s+me|"
    r"check\s+(?:your\s+)?memories?|"
    r"show\s+(?:me\s+)?what\s+you\s+remember|"
    r"what\s+do\s+you\s+remember\s+about\s+my\s+(?:work|job|career|professional)|"
    r"what\s+do\s+you\s+know\s+about\s+my\s+(?:work|job|career|professional)|"
    r"what\s+do\s+you\s+remember\s+about\s+[a-z0-9][a-z0-9 _-]{1,80})\b",
    re.IGNORECASE,
)

_WORK_RE = re.compile(r"\b(?:work|job|career|professional|employment|homelab)\b", re.IGNORECASE)


def is_explicit_memory_query(text: str) -> bool:
    """Return true only for an owner asking to inspect stored memory."""
    return bool(_EXPLICIT_MEMORY_RE.search(str(text or "").strip()))


def memory_query_kind(text: str) -> str:
    query = str(text or "").strip()
    if _WORK_RE.search(query):
        return "work"
    if re.search(r"\b(?:check|show|inspect|search)\b", query, re.IGNORECASE):
        return "inspect"
    return "summary"


def _read_owner_entries(memory_manager: Any, owner: Optional[str]) -> List[Dict[str, Any]]:
    if not owner:
        raise PermissionError("owner is required for explicit memory reads")
    # This is deliberately strict. MemoryManager.load() is a UI-friendly
    # lenient read that maps an unreadable store to [], which is unsafe for a
    # canonical answer because it would look like a truthful zero result.
    if hasattr(memory_manager, "load_all_for_update"):
        entries = memory_manager.load_all_for_update()
    else:
        entries = memory_manager.load(owner=owner)
    return [entry for entry in entries if isinstance(entry, dict) and entry.get("owner") == owner]


def _matches_work(entry: Dict[str, Any]) -> bool:
    text = " ".join(str(entry.get(key) or "") for key in ("text", "category", "source"))
    return bool(_WORK_RE.search(text))


def build_explicit_memory_result(memory_manager: Any, owner: Optional[str], query: str) -> Dict[str, Any]:
    """Build a bounded structured Result for an explicit Memory read.

    The content is intended for the owner-facing model context. Diagnostics
    intentionally contain IDs/counts/status only and never memory text.
    """
    kind = memory_query_kind(query)
    try:
        entries = _read_owner_entries(memory_manager, owner)
    except PermissionError:
        return {
            "status": "owner_required",
            "query_type": kind,
            "memories": [],
            "diagnostics": {"result_status": "owner_required", "retrieved_count": 0},
        }
    except (MemoryStoreUnreadable, OSError, ValueError, TypeError) as exc:
        return {
            "status": "retrieval_failed",
            "query_type": kind,
            "memories": [],
            "diagnostics": {
                "result_status": "retrieval_failed",
                "retrieved_count": 0,
                "error_class": type(exc).__name__,
            },
        }

    if kind == "work":
        selected = [entry for entry in entries if _matches_work(entry)]
    else:
        selected = entries

    selected = selected[:100]
    memories = []
    for entry in selected:
        memories.append({
            "id": str(entry.get("id") or ""),
            "category": str(entry.get("category") or "fact"),
            "text": str(entry.get("text") or ""),
            "source": str(entry.get("source") or "unknown"),
            "pinned": bool(entry.get("pinned")),
            "timestamp": entry.get("timestamp"),
            "confirmation": entry.get("confirmation") or entry.get("confirmed") or None,
            "stale": bool(entry.get("stale", False)),
        })
    status = "ok" if memories else "zero_result"
    return {
        "status": status,
        "query_type": kind,
        "memories": memories,
        "diagnostics": {
            "result_status": status,
            "retrieved_count": len(memories),
            "owner_scoped": True,
        },
    }


def render_explicit_memory_context(result: Dict[str, Any]) -> str:
    """Render a safe, unambiguous canonical Result for model context."""
    status = result.get("status")
    kind = result.get("query_type") or "summary"
    if status == "retrieval_failed":
        return (
            "CANONICAL MEMORY RESULT\n"
            "STATUS: RETRIEVAL_FAILED\n"
            "The Brain memory store could not be read for this request. "
            "Tell the user retrieval failed; do not claim that no memories exist."
        )
    if status == "owner_required":
        return (
            "CANONICAL MEMORY RESULT\nSTATUS: OWNER_REQUIRED\n"
            "An authenticated owner scope is required to read personal memory."
        )
    if status == "zero_result":
        return (
            f"CANONICAL MEMORY RESULT\nQUERY TYPE: {kind}\nSTATUS: ZERO_RESULT\n"
            "The canonical owner-scoped memory query returned zero applicable memories."
        )

    lines = [
        "CANONICAL MEMORY RESULT",
        f"QUERY TYPE: {kind}",
        "STATUS: OK",
        "These are owner-scoped records from Hades Brain. Skills are procedural and are not memory.",
        "Summarize only these records; do not invent additional personal facts.",
    ]
    for memory in result.get("memories") or []:
        lines.append(
            "- "
            f"[{memory.get('category')}] id={memory.get('id')} "
            f"source={memory.get('source')} pinned={str(bool(memory.get('pinned'))).lower()}: "
            f"{memory.get('text')}"
        )
    return "\n".join(lines)

