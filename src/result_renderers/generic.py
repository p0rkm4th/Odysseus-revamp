from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def canonical_structured_empty_read_answer(
    tool_events: Sequence[Mapping[str, Any]],
) -> str | None:
    labels = {
        "manage_homelab": "homelab state",
        "manage_osint": "research",
        "manage_security_assessment": "security assessment",
        "developer_read": "workspace state",
        "read_setup": "integration/setup state",
    }
    for event in reversed(tuple(tool_events or ())):
        if not isinstance(event, Mapping) or event.get("exit_code") not in (None, 0):
            continue
        label = labels.get(str(event.get("tool") or "").strip())
        if not label:
            continue
        try:
            payload = json.loads(str(event.get("output") or ""))
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, Mapping):
            continue
        status = str(payload.get("status") or "").strip().upper()
        collections = [value for value in payload.values() if isinstance(value, list)]
        if status in {"SUCCESS_EMPTY", "EMPTY_RESULT", "ZERO_RESULT"} and collections and not any(collections):
            return f"No {label} records were returned by the canonical read."
    return None
