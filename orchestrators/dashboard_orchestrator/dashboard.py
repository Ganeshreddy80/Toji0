"""Dashboard Orchestrator for tracking live state, alerts, market pulse, and decision timelines."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from decision.models import TimelineState

if TYPE_CHECKING:
    from toji_platform.core.event_bus.interfaces import IEvent
    from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class DashboardOrchestrator:
    """Consolidates system status, tracks timelines, logs alerts, and aggregates stats."""

    def __init__(self, event_bus: IEventBus) -> None:
        """Initialize the DashboardOrchestrator.

        Args:
            event_bus: Kernel Event Bus.
        """
        self.event_bus = event_bus

        # Live state cache
        self._market_pulses: dict[str, dict[str, Any]] = {}
        self._alerts: list[dict[str, Any]] = []
        self._decision_timelines: dict[str, list[dict[str, Any]]] = {}
        self._performance: dict[str, int] = {
            "total_decisions": 0,
            "correct_decisions": 0,
        }

        # Subscribe to integration events
        self.event_bus.subscribe("system.market_data_updated", self._on_market_data_updated)
        self.event_bus.subscribe("system.decision_generated", self._on_decision_generated)
        self.event_bus.subscribe("system.learning_completed", self._on_learning_completed)
        self.event_bus.subscribe("system.alert_triggered", self._on_alert_triggered)

    def _on_market_data_updated(self, event: IEvent) -> None:
        """Handle new market data, update pulse/volatility indicators."""
        payload = event.payload
        symbol = payload.get("symbol")
        if not symbol:
            return

        prices = payload.get("prices", [])
        volumes = payload.get("volumes", [])

        # Simple pulse simulation
        self._market_pulses[symbol] = {
            "last_price": prices[-1] if prices else 0.0,
            "last_volume": volumes[-1] if volumes else 0.0,
            "updated_at": event.timestamp,
        }

    def _on_decision_generated(self, event: IEvent) -> None:
        """Handle new compiled decisions, initialize timeline tracking, trigger alerts."""
        payload = event.payload
        dec_id = payload.get("decision_id")
        symbol = payload.get("symbol")
        rec = payload.get("recommendation", "IGNORE")

        if not dec_id:
            return

        # Initialize timeline
        self._decision_timelines[dec_id] = [
            {
                "timestamp": event.timestamp,
                "state": TimelineState.CREATED.value,
                "details": f"Decision created for {symbol}. Recommendation: {rec}",
            }
        ]

        self._performance["total_decisions"] += 1

        # Trigger high-priority alert for entries / exits
        if rec in ("ENTER", "EXIT", "EMERGENCY_EXIT"):
            self._alerts.append(
                {
                    "timestamp": event.timestamp,
                    "severity": "critical" if rec == "EMERGENCY_EXIT" else "warning",
                    "message": f"Action recommended: {rec} on {symbol} (Decision ID: {dec_id})",
                    "symbol": symbol,
                }
            )

    def _on_learning_completed(self, event: IEvent) -> None:
        """Handle learning audit outcomes, update timeline status to Closed, calibrate performance metrics."""
        payload = event.payload
        dec_id = payload.get("decision_id")
        is_correct = payload.get("is_correct")

        if not dec_id:
            return

        # Update timeline state to Closed
        if dec_id in self._decision_timelines:
            self._decision_timelines[dec_id].append(
                {
                    "timestamp": event.timestamp,
                    "state": TimelineState.CLOSED.value,
                    "details": f"Decision performance audited. Correctness: {is_correct}",
                }
            )

        if is_correct:
            self._performance["correct_decisions"] += 1

    def _on_alert_triggered(self, event: IEvent) -> None:
        """Append external risk alert dispatch items."""
        payload = event.payload
        self._alerts.append(
            {
                "timestamp": event.timestamp,
                "severity": payload.get("severity", "info"),
                "message": payload.get("message", ""),
                "symbol": payload.get("symbol"),
            }
        )

    # ── Client Query Accessors ─────────────────────────────────────────

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Retrieve all logged system alerts."""
        return list(self._alerts)

    def get_market_pulses(self) -> dict[str, dict[str, Any]]:
        """Retrieve active pulses for all observed assets."""
        return dict(self._market_pulses)

    def get_decision_timeline(self, decision_id: str) -> list[dict[str, Any]]:
        """Retrieve timeline lifecycle path for a target decision."""
        return list(self._decision_timelines.get(decision_id, []))

    def get_performance_summary(self) -> dict[str, Any]:
        """Aggregate performance review parameters."""
        total = self._performance["total_decisions"]
        correct = self._performance["correct_decisions"]
        ratio = correct / total if total > 0 else 0.0

        return {
            "total_decisions": total,
            "correct_decisions": correct,
            "correctness_ratio": ratio,
        }
