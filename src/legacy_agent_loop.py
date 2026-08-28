"""Compatibility boundary for callers still using the retired loop name.

The implementation deliberately contains no orchestration. It delegates to
the canonical runtime in ``src.agent_loop`` while preserving the historical
async-generator contract for compatibility callers.
"""

from __future__ import annotations

from typing import Any


async def stream_agent_loop(*args: Any, **kwargs: Any):
    """Delegate an explicit legacy call without creating a second runtime."""
    from src import agent_loop

    kwargs.setdefault("aci_mode", "legacy")
    delegated = agent_loop.stream_aci_runtime(*args, **kwargs)
    try:
        async for event in delegated:
            yield event
    finally:
        await delegated.aclose()


stream_agent_loop._aci_compatibility_facade = True
