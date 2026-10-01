"""Secret-safe Plaid application configuration for the owner setup flow."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.atomic_io import atomic_write_json
from src.constants import DATA_DIR
from src.secret_storage import decrypt, encrypt

CONFIG_PATH = Path(DATA_DIR) / "plaid_config.json"
_ENVIRONMENTS = {"sandbox", "development", "production"}


def _read() -> dict[str, Any]:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _file_credentials() -> tuple[str, str]:
    value = _read()
    return decrypt(str(value.get("client_id") or "")), decrypt(str(value.get("secret") or ""))


def configured_credentials() -> tuple[str, str, str, str]:
    """Return credentials for server use; callers must never serialize them."""
    file_client_id, file_secret = _file_credentials()
    client_id = file_client_id or os.getenv("PLAID_CLIENT_ID", "").strip()
    secret = file_secret or os.getenv("PLAID_SECRET", "").strip()
    value = _read()
    environment = str(value.get("environment") or os.getenv("PLAID_ENV", "sandbox")).strip().lower()
    if environment not in _ENVIRONMENTS:
        environment = "sandbox"
    client_name = str(value.get("client_name") or os.getenv("PLAID_CLIENT_NAME", "HADES")).strip()[:100] or "HADES"
    return client_id, secret, environment, client_name


def public_status() -> dict[str, Any]:
    client_id, secret, environment, client_name = configured_credentials()
    file_client_id, file_secret = _file_credentials()
    return {
        "configured": bool(client_id and secret),
        "environment": environment,
        "client_name": client_name,
        "source": "stored" if file_client_id and file_secret else "environment" if client_id and secret else "none",
    }


def save_configuration(*, client_id: str, secret: str, environment: str = "sandbox", client_name: str = "HADES") -> dict[str, Any]:
    client_id = str(client_id or "").strip()
    secret = str(secret or "").strip()
    environment = str(environment or "sandbox").strip().lower()
    client_name = str(client_name or "HADES").strip()[:100] or "HADES"
    if not client_id or len(client_id) > 128:
        raise ValueError("A valid Plaid client ID is required")
    if not secret or len(secret) > 256:
        raise ValueError("A valid Plaid secret is required")
    if environment not in _ENVIRONMENTS:
        raise ValueError("Plaid environment must be sandbox, development, or production")
    atomic_write_json(str(CONFIG_PATH), {
        "client_id": encrypt(client_id),
        "secret": encrypt(secret),
        "environment": environment,
        "client_name": client_name,
    }, indent=2)
    return public_status()
