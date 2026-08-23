"""Explicitly supervised Telegram runtime lifecycle.

The runtime is opt-in and owns the in-memory Bot API transport. It never reads
or persists the token itself; callers provide a local secret and an owner-bound
dispatch pair, then stop it during application shutdown.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.telegram_poller import TelegramPoller
from src.telegram_transport import TelegramBotApiLongPoll


class TelegramRuntime:
    def __init__(
        self, *, owner: str, bot_token: str, session_factory: Callable[[], Any],
        dispatch, callback_dispatch=None, poll_timeout_seconds: int = 30,
    ) -> None:
        self.transport = TelegramBotApiLongPoll(bot_token=bot_token)
        self.poller = TelegramPoller(
            owner=owner, transport=self.transport, session_factory=session_factory,
            dispatch=dispatch, callback_dispatch=callback_dispatch,
            poll_timeout_seconds=poll_timeout_seconds,
        )

    @property
    def running(self) -> bool:
        return self.poller.running

    def start(self):
        """Start the long poll; callers retain explicit lifecycle control."""
        return self.poller.start()

    async def stop(self) -> None:
        await self.poller.stop()
        await self.transport.close()
