"""Outbound-only Telegram Bot API transport and fail-closed update parsing.

The adapter intentionally has no webhook server or background task. The bot token is
held only in memory and all raised errors are token-free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

_OPAQUE_CALLBACK = re.compile(r"^a:([A-Za-z0-9_-]{16,32})$")


class TelegramTransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class TelegramMedia:
    kind: str
    file_id: str
    file_unique_id: str
    mime_type: str | None
    byte_size: int | None


@dataclass(frozen=True)
class PrivateTelegramUpdate:
    update_id: int
    telegram_user_id: int
    private_chat_id: int
    username: str | None
    text: str | None
    media: TelegramMedia | None
    callback_data: str | None


@dataclass(frozen=True)
class TelegramOutboundMessage:
    text: str
    reply_markup: dict[str, Any] | None = None


class OutboundLongPollTransport(Protocol):
    async def get_updates(self, *, offset: int | None, timeout_seconds: int) -> list[dict[str, Any]]: ...
    async def send_text(
        self, *, private_chat_id: int, text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> int: ...


def _positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise TelegramTransportError(f"{label} is not a positive numeric ID")
    return value


def parse_private_update(payload: object) -> PrivateTelegramUpdate:
    """Parse only private, identity-consistent message/callback updates.

    Unknown update shapes, bots, anonymous senders, groups, channels, and callback
    values containing executable detail all fail closed before model dispatch.
    """
    if not isinstance(payload, dict) or type(payload.get("update_id")) is not int or payload["update_id"] < 0:
        raise TelegramTransportError("invalid Telegram update")
    callback = payload.get("callback_query")
    message = payload.get("message")
    callback_data = None
    if callback is not None:
        if not isinstance(callback, dict) or message is not None:
            raise TelegramTransportError("ambiguous Telegram update")
        message = callback.get("message")
        sender = callback.get("from")
        callback_data = callback.get("data")
        if not isinstance(callback_data, str) or _OPAQUE_CALLBACK.fullmatch(callback_data) is None:
            raise TelegramTransportError("callback data must be an opaque approval reference")
    else:
        sender = message.get("from") if isinstance(message, dict) else None
    if not isinstance(message, dict) or not isinstance(sender, dict):
        raise TelegramTransportError("unsupported Telegram update type")
    chat = message.get("chat")
    if not isinstance(chat, dict) or chat.get("type") != "private":
        raise TelegramTransportError("Telegram groups and channels are not supported")
    user_id = _positive_int(sender.get("id"), "Telegram user ID")
    chat_id = _positive_int(chat.get("id"), "Telegram chat ID")
    if sender.get("is_bot") is True or user_id != chat_id:
        raise TelegramTransportError("Telegram sender does not match the private chat")
    username = sender.get("username")
    if username is not None and (not isinstance(username, str) or len(username) > 64):
        raise TelegramTransportError("invalid Telegram username")
    text = message.get("text") or message.get("caption")
    if text is not None and (not isinstance(text, str) or len(text) > 16_384):
        raise TelegramTransportError("Telegram message text exceeds the adapter limit")
    media = _parse_media(message)
    if callback_data is None and text is None and media is None:
        raise TelegramTransportError("unsupported Telegram message content")
    return PrivateTelegramUpdate(
        update_id=payload["update_id"], telegram_user_id=user_id,
        private_chat_id=chat_id, username=username, text=text, media=media,
        callback_data=callback_data,
    )


def _parse_media(message: dict[str, Any]) -> TelegramMedia | None:
    candidates: list[tuple[str, object]] = []
    for kind in ("photo", "voice", "document"):
        if kind in message:
            candidates.append((kind, message[kind]))
    if not candidates:
        return None
    if len(candidates) != 1:
        raise TelegramTransportError("ambiguous Telegram media")
    kind, raw = candidates[0]
    if kind == "photo":
        if not isinstance(raw, list) or not raw or not all(isinstance(item, dict) for item in raw):
            raise TelegramTransportError("invalid Telegram photo metadata")
        raw = max(raw, key=lambda item: item.get("file_size", 0) if type(item.get("file_size")) is int else 0)
    if not isinstance(raw, dict):
        raise TelegramTransportError("invalid Telegram media metadata")
    file_id, unique = raw.get("file_id"), raw.get("file_unique_id")
    if not isinstance(file_id, str) or not 1 <= len(file_id) <= 256:
        raise TelegramTransportError("invalid Telegram file ID")
    if not isinstance(unique, str) or not 1 <= len(unique) <= 128:
        raise TelegramTransportError("invalid Telegram unique file ID")
    size = raw.get("file_size")
    if size is not None and (type(size) is not int or not 0 <= size <= 25 * 1024 * 1024):
        raise TelegramTransportError("Telegram media exceeds the adapter limit")
    mime = raw.get("mime_type")
    if mime is not None and (not isinstance(mime, str) or not mime or len(mime) > 128):
        raise TelegramTransportError("invalid Telegram MIME type")
    return TelegramMedia(kind=kind, file_id=file_id, file_unique_id=unique, mime_type=mime, byte_size=size)


class TelegramBotApiLongPoll:
    """Minimal fixed-origin Bot API client; lifecycle remains caller-owned."""

    _ORIGIN = "https://api.telegram.org"

    def __init__(self, *, bot_token: str, client: httpx.AsyncClient | None = None) -> None:
        if not isinstance(bot_token, str) or not 20 <= len(bot_token) <= 256 or any(c.isspace() for c in bot_token):
            raise TelegramTransportError("valid Telegram bot token is required")
        self._token = bot_token
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0), follow_redirects=False)
        self._owns_client = client is None

    def __repr__(self) -> str:
        return "TelegramBotApiLongPoll(bot_token=<redacted>)"

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_updates(self, *, offset: int | None, timeout_seconds: int) -> list[dict[str, Any]]:
        if offset is not None and (type(offset) is not int or offset < 0):
            raise TelegramTransportError("invalid Telegram update offset")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 40:
            raise TelegramTransportError("long-poll timeout must be between 1 and 40 seconds")
        payload: dict[str, Any] = {
            "timeout": timeout_seconds,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        data = await self._call("getUpdates", payload)
        if not isinstance(data, list) or len(data) > 100 or not all(isinstance(x, dict) for x in data):
            raise TelegramTransportError("invalid Telegram updates response")
        return data

    async def send_text(
        self, *, private_chat_id: int, text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> int:
        chat_id = _positive_int(private_chat_id, "Telegram private chat ID")
        if not isinstance(text, str) or not text or len(text) > 4096:
            raise TelegramTransportError("Telegram text must contain 1 to 4096 characters")
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            if not isinstance(reply_markup, dict) or set(reply_markup) != {"inline_keyboard"}:
                raise TelegramTransportError("invalid Telegram reply markup")
            keyboard = reply_markup.get("inline_keyboard")
            if not isinstance(keyboard, list) or len(keyboard) > 8 or not all(isinstance(row, list) for row in keyboard):
                raise TelegramTransportError("invalid Telegram reply markup")
            payload["reply_markup"] = reply_markup
        data = await self._call("sendMessage", payload)
        if not isinstance(data, dict):
            raise TelegramTransportError("invalid Telegram send response")
        return _positive_int(data.get("message_id"), "Telegram message ID")

    async def _call(self, method: str, payload: dict[str, Any]) -> object:
        # Telegram requires the credential in the path. Do not log the URL,
        # response object, or underlying exception because each may contain it.
        url = f"{self._ORIGIN}/bot{self._token}/{method}"
        try:
            response = await self._client.post(url, json=payload)
            if len(response.content) > 2 * 1024 * 1024:
                raise TelegramTransportError("Telegram response exceeds the adapter limit")
            response.raise_for_status()
            body = response.json()
        except TelegramTransportError:
            raise
        except Exception:
            raise TelegramTransportError("Telegram Bot API request failed") from None
        if not isinstance(body, dict) or body.get("ok") is not True or "result" not in body:
            raise TelegramTransportError("Telegram Bot API returned an invalid response")
        return body["result"]
