"""Deterministic safeguards for action repetition and knowledge gaps."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any


def _parse(value):
    if not value: return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def action_fingerprint(action: dict[str, Any]) -> str:
    payload = {
        "capability_id": action.get("capability_id"),
        "action_id": action.get("action_id"),
        "normalized_input": action.get("normalized_input") or {},
        "target_resources": action.get("target_resources") or [],
        "state_version": action.get("state_version"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(encoded).hexdigest()


def detect_action_loop(actions: list[dict[str, Any]], *, threshold: int = 2) -> dict[str, Any]:
    counts: dict[str, int] = {}
    result_refs: dict[str, set[str]] = {}
    for action in actions:
        fingerprint = action_fingerprint(action)
        counts[fingerprint] = counts.get(fingerprint, 0) + 1
        result_refs.setdefault(fingerprint, set()).add(str(action.get("result_reference") or ""))
    repeated = [{"fingerprint": key, "count": count, "result_count": len(result_refs[key])} for key, count in counts.items() if count >= threshold]
    no_information_gain = any(item["count"] >= threshold and item["result_count"] <= 1 for item in repeated)
    return {"stop": no_information_gain, "reason": "no_information_gain" if no_information_gain else None, "repeated": repeated}


def classify_knowledge_gaps(required: list[dict[str, Any]], claims: list[dict[str, Any]], *, at=None) -> dict[str, Any]:
    moment = _parse(at) if at else datetime.now(timezone.utc).replace(tzinfo=None)
    known, stale, unknown = [], [], []
    for requirement in required or []:
        subject = requirement.get("subject_ref")
        predicate = requirement.get("predicate")
        matches = [claim for claim in claims or [] if claim.get("subject_ref") == subject and claim.get("predicate") == predicate and claim.get("status", "active") == "active"]
        if not matches:
            unknown.append(requirement)
            continue
        fresh = []
        for claim in matches:
            expiry = _parse(claim.get("valid_until")) or _parse(claim.get("expires_at"))
            if expiry is None or expiry >= moment: fresh.append(claim)
        (known if fresh else stale).append({"requirement": requirement, "claims": fresh or matches})
    return {"known": known, "stale": stale, "unknown": unknown, "complete": not unknown and not stale}
