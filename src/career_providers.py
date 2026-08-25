"""Provider boundary for Career; external listings are never canonical."""
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CareerProvider:
    provider_id: str
    label: str
    configured: bool = False

    def search(self, criteria: Mapping[str, Any]) -> dict[str, Any]:
        if not self.configured:
            return {"status": "NOT_CONFIGURED", "provider": self.provider_id, "opportunities": []}
        raise NotImplementedError("configured provider adapter must implement search")


def providers() -> tuple[CareerProvider, ...]:
    # Deliberately empty until an owner-configured adapter exists.
    return ()


def provider_status() -> dict[str, Any]:
    available = [p.__dict__ for p in providers()]
    return {"status": "NOT_CONFIGURED" if not available else "READY", "providers": available}
