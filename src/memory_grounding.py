"""Canonical, owner-scoped memory grounding for explicit user queries.

Passive memory recall is intentionally small and relevance-ranked.  Explicit
questions about what Hades remembers are different: they must read the Brain
store itself and give the model a structured, authoritative result.  This
module is only a projection/helper; it does not introduce another memory
store or retrieval engine.
"""

from __future__ import annotations

import re
import json
from typing import Any, Dict, Iterable, List, Mapping, Optional

from src.memory import MemoryStoreUnreadable


_EXPLICIT_MEMORY_RE = re.compile(
    r"\b(?:what\s+do\s+you\s+(?:remember|know)\s+about\s+me|"
    r"what\s+(?:personal\s+)?information\s+do\s+you\s+have\s+stored\s+about\s+me|"
    r"(?:give|provide|show)\s+(?:me\s+)?(?:a\s+)?(?:concise\s+)?(?:breakdown|summary|list)\s+of\s+(?:all\s+)?(?:the\s+)?information\s+you\s+have\s+about\s+me|"
    r"what\s+information\s+do\s+you\s+have\s+about\s+me|"
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


def build_runtime_self_state(model: str = "", endpoint: str = "") -> Dict[str, Any]:
    """Return a small derived runtime fact set for Memory reconciliation.

    This is not a second truth store.  It describes the provider/model that is
    serving the current turn so old user-authored Memory can remain visible
    while being labeled historical when it contradicts current runtime state.
    """
    model_name = str(model or "").strip()
    endpoint_name = str(endpoint or "").strip()
    endpoint_lower = endpoint_name.lower()
    if "ollama" in endpoint_lower or ":11434" in endpoint_lower:
        provider = "ollama"
    elif "chatgpt.com" in endpoint_lower or "openai" in endpoint_lower:
        provider = "openai-compatible"
    elif endpoint_name:
        provider = "configured-runtime"
    else:
        provider = "unknown"
    return {
        "active": bool(model_name or endpoint_name),
        "model": model_name or "unknown",
        "provider": provider,
        "source": "current_runtime",
    }


def project_explicit_memory_result(
    result: Mapping[str, Any],
    *,
    current_self_state: Mapping[str, Any] | None = None,
    max_chars: int = 7000,
) -> Dict[str, Any]:
    """Project a canonical Memory Result into a bounded cognition interface.

    The full Result remains canonical at the Memory store/Action boundary. The
    model and UI receive this deterministic L1 projection instead of a nested
    64-record execution envelope. Historical records are not deleted or
    rewritten; an explicit current-runtime contradiction is surfaced beside
    them as epistemic state.
    """
    source = dict(result or {})
    status = str(source.get("status") or "retrieval_failed")
    memories = [row for row in (source.get("memories") or []) if isinstance(row, Mapping)]
    diagnostics = source.get("diagnostics") if isinstance(source.get("diagnostics"), Mapping) else {}
    state = dict(current_self_state or {})
    model_name = str(state.get("model") or "").strip()
    provider = str(state.get("provider") or "").strip()
    contradictions: list[dict[str, str]] = []
    records: list[dict[str, Any]] = []

    for row in memories:
        text = str(row.get("text") or "").strip()
        lowered = text.casefold()
        reason = ""
        if state.get("active") and re.search(
            r"\b(?:not|no|without)\s+(?:currently\s+)?running\s+(?:a\s+)?local\s+llm\b",
            lowered,
        ) and (model_name and model_name.casefold() not in {"unknown", "none"}):
            reason = f"current runtime is actively serving model {model_name}"
        elif state.get("active") and "chatgpt subscription backend" in lowered and provider == "ollama":
            reason = "current runtime provider is Ollama"
        record = {
            "ref": str(row.get("id") or ""),
            "category": str(row.get("category") or "fact"),
            "source": str(row.get("source") or "unknown"),
            "text": text,
            "epistemic_type": "HISTORICAL" if reason else "REMEMBERED",
            "stale": bool(row.get("stale", False)) or bool(reason),
        }
        records.append(record)
        if reason:
            contradictions.append({"ref": record["ref"], "reason": reason})

    # Keep pinned/current-looking records first, then preserve canonical order.
    records.sort(key=lambda row: (not bool(row.get("stale")), row.get("category") != "preference"))
    budget = max(1000, int(max_chars or 7000))
    bounded: list[dict[str, Any]] = []
    used = 0
    for record in records:
        text = record["text"]
        if len(text) > 220:
            record = {**record, "text": text[:217].rstrip() + "..."}
        cost = len(json.dumps(record, ensure_ascii=False, separators=(",", ":"))) + 1
        if bounded and used + cost > budget:
            break
        bounded.append(record)
        used += cost

    return {
        "status": status,
        "query_type": source.get("query_type") or "summary",
        "retrieved_count": int(diagnostics.get("retrieved_count") or len(memories)),
        "owner_scoped": bool(diagnostics.get("owner_scoped", status in {"ok", "zero_result"})),
        "records": bounded,
        "omitted_count": max(0, len(records) - len(bounded)),
        "current_self_state": state,
        "contradictions": contradictions,
        "epistemic_type": "REMEMBERED",
        "freshness": "current canonical read",
        "detail_level": "L1",
        "canonical_refs": ["memory:owner-scoped"],
    }


def render_memory_result_projection(
    projection: Mapping[str, Any],
    *,
    include_records: bool = True,
) -> str:
    """Render the bounded Memory projection for model context and UI."""
    status = str(projection.get("status") or "retrieval_failed")
    kind = str(projection.get("query_type") or "summary")
    if status == "retrieval_failed":
        return (
            "CANONICAL MEMORY RESULT\nSTATUS: RETRIEVAL_FAILED\n"
            "Memory retrieval failed: the owner-scoped Brain store could not be read. "
            "Do not claim that no memories exist."
        )
    if status == "owner_required":
        return "CANONICAL MEMORY RESULT\nSTATUS: OWNER_REQUIRED\nAn authenticated owner scope is required."
    if status == "zero_result":
        return f"CANONICAL MEMORY RESULT\nQUERY TYPE: {kind}\nSTATUS: ZERO_RESULT\nNo applicable owner-scoped memories were found."

    lines = [
        "CANONICAL MEMORY RESULT",
        f"QUERY TYPE: {kind}",
        f"STATUS: OK; RETRIEVED: {projection.get('retrieved_count', 0)}; DETAIL: L1",
        "These are owner-scoped remembered records. Skills are procedural, not memory.",
    ]
    state = projection.get("current_self_state")
    if isinstance(state, Mapping) and state.get("active"):
        lines.append(
            "CURRENT DERIVED HADES STATE: "
            f"provider={state.get('provider', 'unknown')}; model={state.get('model', 'unknown')} "
            "(current runtime evidence supersedes contradictory historical claims)."
        )
    contradictions = projection.get("contradictions") or []
    if contradictions:
        lines.append(
            "RECONCILIATION: " + "; ".join(
                f"{item.get('ref')}: historical/contradicted ({item.get('reason')})"
                for item in contradictions if isinstance(item, Mapping)
            )
        )
    if include_records:
        for record in projection.get("records") or []:
            if not isinstance(record, Mapping):
                continue
            marker = "HISTORICAL" if record.get("epistemic_type") == "HISTORICAL" else "REMEMBERED"
            lines.append(
                f"- [{record.get('category')}] {marker}: {record.get('text')}"
            )
    omitted = int(projection.get("omitted_count") or 0)
    if omitted:
        lines.append(f"- {omitted} additional canonical records remain available by reference; they were omitted from this L1 projection.")
    return "\n".join(lines)


def render_explicit_memory_context(
    result: Dict[str, Any],
    *,
    current_self_state: Mapping[str, Any] | None = None,
) -> str:
    """Render a safe, unambiguous canonical Result for model context."""
    return render_memory_result_projection(
        project_explicit_memory_result(result, current_self_state=current_self_state)
    )
