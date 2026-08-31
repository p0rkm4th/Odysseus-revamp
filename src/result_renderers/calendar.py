"""Grounded owner-facing Calendar Result rendering."""
from __future__ import annotations
from typing import Any, Mapping, Sequence

def canonical_communications_read_answer(tool_events: Sequence[Mapping[str, Any]]) -> str | None:
    event = next((item for item in reversed(tuple(tool_events or ())) if isinstance(item, Mapping) and item.get("tool") == "read_communications"), None)
    if event is None or event.get("exit_code") not in (None, 0): return None
    projection = event.get("result_projection")
    calendar = projection.get("calendar") if isinstance(projection, Mapping) else None
    if isinstance(calendar, Mapping):
        events = calendar.get("events") if isinstance(calendar.get("events"), list) else []
        if not events:
            return "You have no calendar events scheduled in the next 14 days." if int(calendar.get("calendars") or 0) > 0 else "Your calendar is not connected, so I can't check today's schedule."
        lines = [f"You have {len(events)} calendar event{'s' if len(events) != 1 else ''} coming up:"]
        for item in events[:20]:
            if isinstance(item, Mapping):
                summary = str(item.get("summary") or "(untitled event)").strip()
                when = str(item.get("dtstart") or "").strip()
                lines.append(f"- {summary}" + (f" — {when}" if when else ""))
        return "\n".join(lines)
    text = str(event.get("output") or "").strip()
    return text if text.startswith(("You have no calendar events", "Your calendar is not connected", "You have ")) else None
