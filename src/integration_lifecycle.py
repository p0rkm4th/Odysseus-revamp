"""Small canonical lifecycle vocabulary for owner-scoped Finance connections."""

from __future__ import annotations

from datetime import datetime

from core.database import utcnow_naive
from core.finance_models import FinanceConnection

LIFECYCLE_STATES = frozenset({
    "NOT_CONFIGURED", "AUTHORIZATION_REQUIRED", "AUTHORIZATION_IN_PROGRESS",
    "CONNECTED", "SYNCING", "HEALTHY", "DEGRADED", "RECONNECT_REQUIRED",
})


def set_connection_state(
    connection: FinanceConnection,
    state: str,
    *,
    provider_health: str | None = None,
    capability_available: bool | None = None,
    error: str | None = None,
    synced_at: datetime | None = None,
) -> None:
    if state not in LIFECYCLE_STATES:
        raise ValueError(f"unsupported connection lifecycle state: {state}")
    connection.lifecycle_state = state
    if provider_health is not None:
        connection.provider_health = provider_health
    if capability_available is not None:
        connection.capability_available = capability_available
    connection.last_error_classification = error[:128] if error else None
    if synced_at is not None:
        connection.last_successful_sync_at = synced_at


def capability_available(connection: FinanceConnection | None) -> bool:
    return bool(connection and connection.capability_available and connection.lifecycle_state == "HEALTHY")


def new_connection(owner: str, provider: str, connection_id: str) -> FinanceConnection:
    return FinanceConnection(
        id=connection_id, owner=owner, provider=provider,
        lifecycle_state="AUTHORIZATION_REQUIRED", provider_health="UNKNOWN",
    )
