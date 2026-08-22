"""Health monitor for reporting Market Gateway and provider connectivity metrics."""

from __future__ import annotations

from typing import Any

from market_gateway.core.gateway import MarketGateway


class MarketHealthMonitor:
    """Aggregates and formats gateway health status and telemetry stats."""

    def __init__(self, gateway: MarketGateway) -> None:
        self.gateway = gateway

    def get_summary(self) -> dict[str, Any]:
        """Aggregate metrics across all active provider plugins."""
        return {
            "gateway_state": self.gateway.state.value,
            "gateway_health": self.gateway.health_check().value,
            "active_subscriptions_count": len(self.gateway.active_subscriptions),
            "providers": self.gateway.get_detailed_health(),
        }
