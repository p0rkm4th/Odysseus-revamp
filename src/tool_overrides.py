"""Owner-managed overrides for built-in tool descriptions.

This is configuration projection only. It does not define capabilities,
select tools, or grant execution authority.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_builtin_overrides() -> dict:
    """Return the owner's built-in tool-description overrides."""
    try:
        from src.settings import get_setting

        overrides = get_setting("builtin_tool_overrides", {})
        return overrides if isinstance(overrides, dict) else {}
    except Exception:
        logger.warning("Failed to load built-in tool overrides; using defaults", exc_info=True)
        return {}
