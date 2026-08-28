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
import os
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional

from src.memory import MemoryStoreUnreadable
from src.deterministic_reads import deterministic_read_concept
from src.prompt_security import untrusted_context_message

logger = logging.getLogger(__name__)


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
    query = str(text or "").strip()
    return bool(
        _EXPLICIT_MEMORY_RE.search(query)
        or deterministic_read_concept(query) == "MEMORY"
    )


def memory_query_kind(text: str) -> str:
    query = str(text or "").strip()
    if _WORK_RE.search(query):
        return "work"
    if re.search(r"\b(?:check|show|inspect|search)\b", query, re.IGNORECASE):
        return "inspect"
    return "summary"


def minimal_saved_memory_message(messages: List[Dict]) -> Optional[Dict]:
    """Project only bounded saved-memory facts into a model context."""
    facts: List[str] = []
    seen = set()
    for message in messages:
        if not isinstance(message, dict):
            continue
        metadata = message.get("metadata")
        source = str((metadata or {}).get("source") or "")
        if not source.startswith("saved memory:"):
            continue
        content = str(message.get("content") or "")
        # Explicit canonical results retain their status even when they have
        # no facts, so the model cannot infer a false zero-result answer.
        if (metadata or {}).get("context_kind") == "explicit_memory_result":
            return untrusted_context_message(
                "saved memory: explicit canonical result",
                content[:20000],
            )
        content = re.sub(r"(?m)^\s*Source:\s*saved memory:[^\n]*\n?", "", content)
        content = content.replace("Core facts about the user:", "")
        content = re.sub(
            r"Memory context\. Do not reference unless the user asks about these topics\.\s*",
            "",
            content,
        )
        for line in content.splitlines():
            line = line.strip()
            if not line.startswith("- "):
                continue
            fact = line[2:].strip()
            if not fact or fact in seen:
                continue
            seen.add(fact)
            facts.append(fact)
            if len(facts) >= 5:
                break
        if len(facts) >= 5:
            break
    if not facts:
        return None
    logger.info("[agent-intent] odysseus doc minimal memory facts=%s", len(facts))
    return untrusted_context_message(
        "saved memory: minimal context",
        (
            "Saved user memory facts from Odysseus Brain. These are the same "
            "user facts available in the normal prompt path. Use them when "
            "the user asks for personalization, identity, background, "
            "preferences, or anything about \"me\" or \"my\":\n"
            + "\n".join(f"- {fact}" for fact in facts)
        ),
    )


def looks_like_memory_identity_turn(text: str) -> bool:
    """Recognize identity/personal-memory questions as memory evidence."""
    query = re.sub(r"[^a-z0-9\s'?]", " ", (text or "").lower())
    query = re.sub(r"\bhwho\b", "who", query)
    return bool(re.search(
        r"\b("
        r"who am i|who i am|what'?s my name|what is my name|where do i live|"
        r"what do you know about me|about me|relate to me|use what you know|"
        r"remember\b|forget\b|my preference|my preferences|i prefer|"
        r"my memory|memories about me"
        r")\b",
        query,
    ))


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


def build_runtime_self_state(model: str = "", endpoint: str = "", *,
                             source_commit: str = "", active_branch: str = "") -> Dict[str, Any]:
    """Return a small derived runtime fact set for Memory reconciliation.

    This is not a second truth store.  It describes the provider/model that is
    serving the current turn so old user-authored Memory can remain visible
    while being labeled historical when it contradicts current runtime state.
    """
    model_name = str(model or "").strip()
    endpoint_name = str(endpoint or "").strip()
    source = str(source_commit or os.getenv("ODYSSEUS_SOURCE_COMMIT") or "").strip()
    branch = str(active_branch or os.getenv("ODYSSEUS_SOURCE_BRANCH") or "").strip()
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
        "active": bool(model_name or endpoint_name or source or branch),
        "model": model_name or "unknown",
        "provider": provider,
        "source_commit": source,
        "active_branch": branch,
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
        elif state.get("active") and re.search(
            r"\b(?:current(?:ly)?\s+)?(?:on|using|working\s+from)\s+(?:the\s+)?"
            r"[a-z0-9._/-]+\s+branch\b|\bcurrent\s+(?:branch|commit|head)\b",
            lowered,
        ) and (state.get("active_branch") or state.get("source_commit")):
            if state.get("active_branch"):
                reason = (
                    f"current canonical branch is {state['active_branch']}; "
                    "remembered branch state is historical"
                )
            else:
                reason = (
                    "current deployment source is "
                    f"{str(state.get('source_commit'))[:12]}; remembered branch state is historical"
                )
        record = {
            "ref": str(row.get("id") or ""),
            "category": str(row.get("category") or "fact"),
            "source": str(row.get("source") or "unknown"),
            "text": text,
            "epistemic_type": "HISTORICAL" if reason else "REMEMBERED",
            "stale": bool(row.get("stale", False)) or bool(reason),
            "pinned": bool(row.get("pinned", False)),
            "contradicted": bool(reason),
        }
        records.append(record)
        if reason:
            contradictions.append({"ref": record["ref"], "reason": reason})

    # Current evidence leads the answer, but a contradiction is T0 state and
    # must not disappear merely because many current records consume the L1
    # budget. Keep a small current lead, then contradicted history, followed by
    # the remaining current and ordinary historical records.
    current_records = [row for row in records if not row.get("stale")]
    current_records.sort(key=lambda row: (
        not bool(row.get("pinned")),
        row.get("category") != "preference",
    ))
    contradicted_records = [row for row in records if row.get("stale") and row.get("contradicted")]
    historical_records = [row for row in records if row.get("stale") and not row.get("contradicted")]
    current_lead = min(8, len(current_records))
    records = (
        current_records[:current_lead]
        + contradicted_records
        + current_records[current_lead:]
        + historical_records
    )
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
        if state.get("active_branch") or state.get("source_commit"):
            lines.append(
                "CURRENT DEPLOYMENT STATE: "
                f"branch={state.get('active_branch') or 'not projected'}; "
                f"source_commit={str(state.get('source_commit') or 'unknown')[:12]}."
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
