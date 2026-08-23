"""Supervised outbound-only Telegram long-poll lifecycle.

The poller owns no bot token itself beyond the transport object supplied by the
caller. It accepts only private parsed updates, records update IDs before
dispatch, serializes a bound Odysseus session, and backs off on transport
failures. It never starts a webhook listener or executes model actions directly.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from core.telegram_models import TelegramConnection
from src.telegram_store import TelegramStore, TelegramStoreError
from src.telegram_transport import (
    OutboundLongPollTransport, PrivateTelegramUpdate, TelegramOutboundMessage,
    TelegramTransportError,
    parse_private_update,
)

logger = logging.getLogger(__name__)

Dispatch = Callable[[PrivateTelegramUpdate, str, int], Awaitable[str | TelegramOutboundMessage | None]]
CallbackDispatch = Callable[[PrivateTelegramUpdate, str, str, str], Awaitable[str | TelegramOutboundMessage | None]]


class TelegramPoller:
    """Run one owner's private Telegram channel until explicitly stopped."""

    def __init__(
        self, *, owner: str, transport: OutboundLongPollTransport,
        session_factory: Callable[[], Any], dispatch: Dispatch,
        callback_dispatch: CallbackDispatch | None = None,
        poll_timeout_seconds: int = 30,
    ) -> None:
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("poller owner is required")
        if type(poll_timeout_seconds) is not int or not 1 <= poll_timeout_seconds <= 40:
            raise ValueError("poll timeout must be between 1 and 40 seconds")
        self.owner = owner.strip()
        self.transport = transport
        self.session_factory = session_factory
        self.dispatch = dispatch
        self.callback_dispatch = callback_dispatch
        self.poll_timeout_seconds = poll_timeout_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._offset: int | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> asyncio.Task[None]:
        if self.running:
            raise RuntimeError("Telegram poller is already running")
        self._stop.clear()
        self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        if task is not None and not task.done():
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def run(self) -> None:
        backoff = 1.0
        try:
            while not self._stop.is_set():
                try:
                    updates = await self.transport.get_updates(
                        offset=self._offset, timeout_seconds=self.poll_timeout_seconds,
                    )
                    backoff = 1.0
                    for payload in updates:
                        if self._stop.is_set():
                            break
                        # Reject malformed/unsupported updates without wedging
                        # the long poll on the same Telegram update forever.
                        # Transport failures during dispatch are deliberately
                        # still handled by the outer retry path so a response
                        # send is not silently discarded.
                        try:
                            parse_private_update(payload)
                        except TelegramTransportError:
                            if isinstance(payload, dict) and type(payload.get("update_id")) is int:
                                self._offset = payload["update_id"] + 1
                            logger.warning("Ignoring malformed or unsupported Telegram update")
                            continue
                        await self._handle_payload(payload)
                        if isinstance(payload, dict) and type(payload.get("update_id")) is int:
                            self._offset = payload["update_id"] + 1
                except (TelegramTransportError, TelegramStoreError, ValueError):
                    logger.warning("Telegram poll iteration failed; retrying with backoff")
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                    except asyncio.TimeoutError:
                        pass
                    backoff = min(backoff * 2, 60.0)
        finally:
            self._task = None

    async def _handle_payload(self, payload: object) -> None:
        update = parse_private_update(payload)

        def claim() -> tuple[bool, str | None, int | None, str | None, str | None, bool]:
            db = self.session_factory()
            try:
                store = TelegramStore(db)
                active_connection = db.query(TelegramConnection).filter_by(
                    owner=self.owner, active=1,
                ).one_or_none()
                if active_connection is None:
                    # Pairing is the one pre-connection operation allowed by
                    # this poller. The code is short-lived, hashed at rest,
                    # single-use, and accepted only from a private identity-
                    # consistent update. Do not record arbitrary unpaired
                    # messages in the owner's update ledger.
                    if update.callback_data is not None or not update.text:
                        return True, None, None, None, None, False
                    try:
                        store.claim_pairing_code(
                            code=update.text.strip(),
                            telegram_user_id=update.telegram_user_id,
                            private_chat_id=update.private_chat_id,
                            display_username=update.username,
                        )
                    except TelegramStoreError:
                        return True, None, None, None, None, False
                    return True, None, None, None, None, True
                fresh = store.record_update(
                    owner=self.owner, telegram_user_id=update.telegram_user_id,
                    update_id=update.update_id, payload=payload,
                )
                if not fresh:
                    return False, None, None, None, None, False
                if update.media is not None:
                    store.record_media(
                        owner=self.owner, telegram_user_id=update.telegram_user_id,
                        update_id=update.update_id, file_id=update.media.file_id,
                        file_unique_id=update.media.file_unique_id,
                        media_kind=update.media.kind, mime_type=update.media.mime_type,
                        byte_size=update.media.byte_size,
                    )
                session = store.get_session(
                    owner=self.owner, telegram_user_id=update.telegram_user_id,
                    private_chat_id=update.private_chat_id,
                )
                if session is None:
                    return True, None, None, None, None, False
                if update.callback_data is not None:
                    callback = store.consume_approval_callback(
                        owner=self.owner, telegram_user_id=update.telegram_user_id,
                        private_chat_id=update.private_chat_id,
                        callback_data=update.callback_data,
                    )
                    return (
                        True, session.odysseus_session_id, session.revision,
                        callback.approval_digest, callback.allowed_decision, False,
                    )
                advanced = store.advance_session_revision(
                    owner=self.owner, telegram_user_id=update.telegram_user_id,
                    private_chat_id=update.private_chat_id, expected_revision=session.revision,
                )
                return True, advanced.odysseus_session_id, advanced.revision, None, None, False
            finally:
                db.close()

        fresh, session_id, revision, approval_digest, decision, paired = await asyncio.to_thread(claim)
        if paired:
            await self.transport.send_text(
                private_chat_id=update.private_chat_id,
                text="Telegram pairing succeeded. Bind this private chat to an Odysseus session before sending requests.",
            )
            return
        if not fresh or session_id is None or revision is None:
            return
        if decision is not None and self.callback_dispatch is not None and approval_digest is not None:
            # Telegram stores the safe public decision as approve/deny. The
            # web approval path requires the explicit task-scoped spelling for
            # an approval continuation; deny remains unchanged.
            continuation_decision = "approve_task" if decision == "approve" else decision
            response = await self.callback_dispatch(
                update, session_id, approval_digest, continuation_decision,
            )
        else:
            response = await self.dispatch(update, session_id, revision)
        if response:
            if isinstance(response, TelegramOutboundMessage):
                text, reply_markup = response.text, response.reply_markup
            else:
                text, reply_markup = str(response), None
            try:
                await self.transport.send_text(
                    private_chat_id=update.private_chat_id,
                    text=text[:4096], reply_markup=reply_markup,
                )
            except TypeError:
                # Test/dummy transports written against the original plain-text
                # contract remain usable; production transport supports markup.
                await self.transport.send_text(
                    private_chat_id=update.private_chat_id, text=text[:4096],
                )
