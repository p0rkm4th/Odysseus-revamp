"""Owner-granted developer execution tools for the model.

The browser can grant/revoke a lease, but the model must be the caller that
uses it.  This adapter deliberately does not accept a lease id: it resolves
the newest active lease for the authenticated owner inside the server-side
database boundary.
"""

from __future__ import annotations

import asyncio
import json


class YoloShellTool:
    """Run one bounded model-requested command under the owner's YOLO lease."""

    async def execute(self, content: str, ctx: dict) -> dict:
        owner = str(ctx.get("owner") or "").strip()
        if not owner:
            return {"error": "YOLO shell requires an authenticated owner.", "exit_code": 1}
        try:
            payload = json.loads(content or "{}") if isinstance(content, str) else content
        except (TypeError, ValueError):
            return {"error": "yolo_shell arguments must be a JSON object.", "exit_code": 1}
        if not isinstance(payload, dict):
            return {"error": "yolo_shell arguments must be a JSON object.", "exit_code": 1}
        command = str(payload.get("command") or "").strip()
        if not command:
            return {"error": "yolo_shell requires a command.", "exit_code": 1}
        if len(command) > 16_384:
            return {"error": "yolo_shell command exceeds the bounded length limit.", "exit_code": 1}

        def _run() -> dict:
            from core.database import SessionLocal
            from src import developer_mode

            with SessionLocal() as db:
                lease = developer_mode.latest_active(db, owner)
                if lease is None:
                    return {
                        "error": "YOLO is not active for this owner. Enable Workspace YOLO or Hardcore YOLO first.",
                        "exit_code": 1,
                        "requires_owner_grant": True,
                    }
                return developer_mode.execute(db, owner, lease.id, command)

        try:
            result = await asyncio.to_thread(_run)
        except ValueError as exc:
            return {"error": str(exc), "exit_code": 1}
        result["model_invoked"] = True
        result["lease_selected_server_side"] = True
        return result

