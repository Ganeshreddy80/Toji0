"""Event Aggregator for synthesizing platform-wide event payloads."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from dashboard.core.models import DashboardSnapshot, HistoricalEvent
from dashboard.core.orchestrator import DashboardOrchestrator
from dashboard.health.health_monitor import HealthMonitor
from dashboard.websocket.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class DashboardEventAggregator:
    """Consumes platform events, compiles snapshots, and tracks historical logs."""

    def __init__(
        self,
        orchestrator: DashboardOrchestrator,
        health_monitor: HealthMonitor,
        websocket_manager: WebSocketManager,
        event_bus: Any = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._health_monitor = health_monitor
        self._websocket_manager = websocket_manager
        self._event_bus = event_bus
        self._lock = threading.Lock()
        
        # Historical events log timeline
        self._events_history: List[HistoricalEvent] = []
        self._history_limit = 2000

    def get_events_history(self) -> List[HistoricalEvent]:
        """Retrieve the historical log timeline."""
        with self._lock:
            return list(self._events_history)

    def add_historical_event(self, hist_event: HistoricalEvent) -> None:
        """Add a parsed event to the timeline and broadcast to WS logs channel."""
        with self._lock:
            self._events_history.append(hist_event)
            if len(self._events_history) > self._history_limit:
                self._events_history.pop(0)

        # Broadcast event info on logs channel
        log_message = (
            f"[{hist_event.timestamp.strftime('%H:%M:%S.%f')[:-3]}] "
            f"{hist_event.subsystem}::{hist_event.event_name} published for "
            f"{hist_event.symbol}/{hist_event.timeframe} (latency={hist_event.latency_ms:.1f}ms)."
        )
        self._websocket_manager.broadcast("logs", {"message": log_message, "severity": hist_event.severity})

    def handle_market_state_updated(self, event: Any) -> None:
        """Handle MIL updates."""
        self._process_event(event, "MIL", "market_state", "market")

    def handle_pattern_updated(self, event: Any) -> None:
        """Handle PAE updates."""
        self._process_event(event, "PAE", "pattern_state", "patterns")

    def handle_pattern_quality_updated(self, event: Any) -> None:
        """Handle PQE updates."""
        self._process_event(event, "PQE", "pattern_quality", "confluence")

    def handle_confluence_updated(self, event: Any) -> None:
        """Handle CE updates."""
        self._process_event(event, "CE", "confluence", "confluence")

    def handle_strategy_updated(self, event: Any) -> None:
        """Handle SE updates."""
        self._process_event(event, "SE", "strategy", "strategy")

    def handle_trading_context_updated(self, event: Any) -> None:
        """Handle Trading Context updates."""
        self._process_event(event, "TC", "trading_context", "system", payload_key="context")

    def handle_risk_updated(self, event: Any) -> None:
        """Handle Risk Engine updates."""
        self._process_event(event, "RE", "risk_assessment", "risk")

    def handle_position_size_updated(self, event: Any) -> None:
        """Handle Position Sizing updates."""
        self._process_event(event, "PSE", "position_size", "position")

    def handle_execution_completed(self, event: Any) -> None:
        """Handle Execution Engine updates."""
        self._process_event(event, "EE", "execution_state", "execution", payload_key=None)

    def handle_portfolio_updated(self, event: Any) -> None:
        """Handle Portfolio Engine updates."""
        self._process_event(event, "PE", "portfolio_state", "portfolio", payload_key="portfolio")

    def _process_event(
        self,
        event: Any,
        subsystem: str,
        snapshot_field: str,
        ws_channel: str,
        payload_key: str | None = "state",
    ) -> None:
        """Generic method to extract payload data, update snapshot and notify clients."""
        start_time = time.perf_counter()
        if not event or not hasattr(event, "payload") or not event.payload:
            return

        payload = event.payload
        symbol = payload.get("symbol")
        timeframe = payload.get("timeframe")
        state_data = payload.get(payload_key) if payload_key is not None else payload

        if not symbol or not timeframe:
            return

        symbol = symbol.upper()
        timeframe = timeframe.lower()

        # Update health monitor statistics
        latency_calc_ms = (time.perf_counter() - start_time) * 1000.0
        self._health_monitor.register_message(subsystem, latency_calc_ms)

        # Assemble unified snapshot
        state_store = self._orchestrator._state_store
        if not state_store:
            return

        with self._lock:
            existing = state_store.get_snapshot(symbol, timeframe)
            if existing:
                updated_states = dict(existing.health_status)
                # Keep upstream components immutable by copying dict
                new_update = {
                    snapshot_field: state_data,
                    "health_status": self._health_monitor.get_health_status(),
                    "timestamp": datetime.now(timezone.utc),
                }
                updated_snapshot = existing.model_copy(update=new_update)
            else:
                new_fields = {
                    "snapshot_id": str(uuid.uuid4()),
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "health_status": self._health_monitor.get_health_status(),
                    "timestamp": datetime.now(timezone.utc),
                }
                new_fields[snapshot_field] = state_data
                updated_snapshot = DashboardSnapshot(**new_fields)

            self._orchestrator.process_snapshot(updated_snapshot)

        # Push to relevant WebSocket channel
        self._websocket_manager.broadcast(ws_channel, {
            "symbol": symbol,
            "timeframe": timeframe,
            "data": state_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Broadcast full snapshot to dashboard channel
        self._websocket_manager.broadcast("system", updated_snapshot.model_dump(mode="json"))

        # Add to timeline history logs
        hist_event = HistoricalEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            subsystem=subsystem,
            event_name=event.__class__.__name__,
            symbol=symbol,
            timeframe=timeframe,
            latency_ms=latency_calc_ms,
            severity="info",
            payload=payload,
        )
        self.add_historical_event(hist_event)

        # Publish DashboardUpdated event to the Platform Event Bus
        if self._event_bus is not None:
            try:
                from toji_platform.core.event_bus.events import DashboardUpdated
                db_event = DashboardUpdated(
                    source=f"dashboard.aggregator.{subsystem}",
                    payload={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "snapshot": updated_snapshot.model_dump(mode="json"),
                    }
                )
                self._event_bus.publish(db_event)
            except Exception as e:
                logger.error("DashboardEventAggregator: Failed to publish DashboardUpdated: %s", e)
