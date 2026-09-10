"""Small, secret-safe HTTP transport for the Plaid read-only surface."""

from __future__ import annotations

import os
from typing import Any

import httpx


class PlaidError(RuntimeError):
    def __init__(self, classification: str, message: str = "Plaid request failed"):
        super().__init__(message)
        self.classification = classification


class PlaidTransport:
    def __init__(self, *, client: httpx.Client | None = None, base_url: str | None = None,
                 client_id: str | None = None, secret: str | None = None):
        self.client = client or httpx.Client(timeout=20.0)
        environment = os.getenv("PLAID_ENV", "sandbox").strip().lower()
        self.base_url = (base_url or {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com",
        }.get(environment, "https://sandbox.plaid.com")).rstrip("/")
        self.client_id = client_id or os.getenv("PLAID_CLIENT_ID", "")
        self.secret = secret or os.getenv("PLAID_SECRET", "")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.client_id or not self.secret:
            raise PlaidError("PLAID_CREDENTIALS_MISSING", "Plaid credentials are not configured")
        try:
            response = self.client.post(
                f"{self.base_url}{path}",
                json={"client_id": self.client_id, "secret": self.secret, **payload},
            )
        except httpx.HTTPError as exc:
            raise PlaidError("PROVIDER_UNAVAILABLE") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise PlaidError("MALFORMED_PROVIDER_RESPONSE") from exc
        if not isinstance(body, dict):
            raise PlaidError("MALFORMED_PROVIDER_RESPONSE")
        if response.status_code >= 400 or body.get("error_code"):
            raise PlaidError(str(body.get("error_code") or f"HTTP_{response.status_code}"))
        return body

    def accounts_get(self, access_token: str) -> dict[str, Any]:
        return self._post("/accounts/get", {"access_token": access_token})

    def item_get(self, access_token: str) -> dict[str, Any]:
        return self._post("/item/get", {"access_token": access_token})

    def transactions_sync(self, access_token: str, cursor: str | None) -> dict[str, Any]:
        payload: dict[str, Any] = {"access_token": access_token, "count": 500}
        if cursor:
            payload["cursor"] = cursor
        return self._post("/transactions/sync", payload)

    def link_token_create(self, client_user_id: str, *, access_token: str | None = None) -> dict[str, Any]:
        """Create a Transactions Link token for one authenticated owner."""
        client_name = os.getenv("PLAID_CLIENT_NAME", "HADES")[:100]
        payload = {
                "client_name": client_name,
                "user": {"client_user_id": client_user_id},
                "language": "en",
                "country_codes": ["US"],
            }
        if access_token:
            payload["access_token"] = access_token
        else:
            payload["products"] = ["transactions"]
        return self._post("/link/token/create", payload)

    def item_public_token_exchange(self, public_token: str) -> dict[str, Any]:
        """Exchange the one-time Link public token server-side."""
        return self._post("/item/public_token/exchange", {"public_token": public_token})
