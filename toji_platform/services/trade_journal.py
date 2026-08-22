"""Trade Journal — persists every execution with full metadata.

Stores entries as JSON lines partitioned by date for efficient retrieval.
Thread-safe write buffer with periodic flush.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Optional

from toji_platform.core.event_bus.interfaces import IEvent, IEventBus
from toji_platform.core.lifecycle.interfaces import IHealthCheck, ILifecycle
from toji_platform.core.types import HealthStatus

logger = logging.getLogger(__name__)


class TradeJournalEntry:
    """Single trade journal record."""

    __slots__ = (
        "timestamp", "execution_id", "request_id", "signal_id",
        "symbol", "timeframe", "side", "quantity", "price",
        "fees", "slippage", "latency_ms", "strategy_decision",
        "risk_assessment", "replay_id", "correlation_id",
        "order_type", "status", "broker",
    )

    def __init__(self, **kwargs: Any) -> None:
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot))

    def to_dict(self) -> dict[str, Any]:
        return {s: getattr(self, s) for s in self.__slots__}


class TradeJournal(ILifecycle, IHealthCheck):
    """Persists execution events to date-partitioned JSONL files.

    Subscribes to ``system.execution_completed`` on the event bus
    and writes full trade metadata to disk.
    """

    def __init__(
        self,
        base_dir: str = "data/journals/trades",
        event_bus: Optional[IEventBus] = None,
        flush_interval: float = 5.0,
    ) -> None:
        self._base_dir = Path(base_dir)
        self._event_bus = event_bus
        self._flush_interval = flush_interval

        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._running = False
        self._shutdown_event = threading.Event()
        self._flush_thread: Optional[threading.Thread] = None
        self._total_entries = 0
        self._last_flush: Optional[datetime] = None

    # ── ILifecycle ─────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "Trade Journal"

    def start(self) -> None:
        """Start the journal flush thread and subscribe to execution events."""
        if self._running:
            return
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="TradeJournal-Flush"
        )
        self._flush_thread.start()

        if self._event_bus is not None:
            self._event_bus.subscribe(
                "system.execution_completed", self._on_execution_completed
            )

        logger.info("Trade Journal started ✓ (dir=%s)", self._base_dir)

    def stop(self) -> None:
        """Flush remaining entries and stop the flush thread."""
        self._running = False
        self._shutdown_event.set()
        if self._event_bus is not None:
            try:
                self._event_bus.unsubscribe(
                    "system.execution_completed", self._on_execution_completed
                )
            except Exception:
                pass
        self._flush()
        if self._flush_thread is not None:
            self._flush_thread.join(timeout=1.0)
            self._flush_thread = None
        logger.info("Trade Journal stopped ✓ (%d total entries)", self._total_entries)

    # ── IHealthCheck ───────────────────────────────────────────────────

    def check_health(self) -> HealthStatus:
        if not self._running:
            return HealthStatus.UNHEALTHY
        return HealthStatus.HEALTHY

    # ── Public API ─────────────────────────────────────────────────────

    def record(self, entry: dict[str, Any]) -> None:
        """Add a trade entry to the write buffer."""
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._buffer.append(entry)

    def query(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        symbol: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Query journal entries by date range and/or symbol."""
        results: list[dict[str, Any]] = []
        if not self._base_dir.exists():
            return results

        for day_dir in sorted(self._base_dir.iterdir()):
            if not day_dir.is_dir():
                continue
            try:
                dir_date = date.fromisoformat(day_dir.name)
            except ValueError:
                continue
            if start_date and dir_date < start_date:
                continue
            if end_date and dir_date > end_date:
                continue

            journal_file = day_dir / "trades.jsonl"
            if not journal_file.exists():
                continue

            for line in journal_file.read_text().strip().splitlines():
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if symbol and entry.get("symbol", "").upper() != symbol.upper():
                    continue
                results.append(entry)

        return results

    def get_stats(self) -> dict[str, Any]:
        """Return current journal statistics."""
        return {
            "total_entries": self._total_entries,
            "buffer_size": len(self._buffer),
            "last_flush": self._last_flush.isoformat() if self._last_flush else None,
            "base_dir": str(self._base_dir),
            "running": self._running,
        }

    # ── Event Handler ──────────────────────────────────────────────────

    def _on_execution_completed(self, event: IEvent) -> None:
        """Handle execution_completed events from the event bus."""
        payload = getattr(event, "payload", {}) or {}
        entry = {
            "timestamp": getattr(event, "timestamp", datetime.now(timezone.utc)).isoformat()
            if hasattr(getattr(event, "timestamp", None), "isoformat")
            else datetime.now(timezone.utc).isoformat(),
            "event_id": str(getattr(event, "event_id", "")),
            "execution_id": payload.get("execution_id", ""),
            "request_id": payload.get("request_id", ""),
            "signal_id": payload.get("signal_id", ""),
            "symbol": payload.get("symbol", ""),
            "timeframe": payload.get("timeframe", ""),
            "side": payload.get("side", ""),
            "quantity": payload.get("quantity", 0.0),
            "price": payload.get("price", 0.0),
            "fees": payload.get("fees", 0.0),
            "slippage": payload.get("slippage", 0.0),
            "latency_ms": payload.get("latency_ms", 0.0),
            "strategy_decision": payload.get("strategy_decision", ""),
            "risk_assessment": payload.get("risk_assessment", ""),
            "replay_id": payload.get("replay_id", ""),
            "correlation_id": payload.get("correlation_id", ""),
            "order_type": payload.get("order_type", ""),
            "status": payload.get("status", ""),
            "broker": payload.get("broker", ""),
        }
        self.record(entry)

    # ── Internal ───────────────────────────────────────────────────────

    def _flush_loop(self) -> None:
        """Background thread that periodically flushes the buffer to disk."""
        while self._running:
            if self._shutdown_event.wait(self._flush_interval):
                break
            self._flush()

    def _flush(self) -> None:
        """Write buffered entries to date-partitioned JSONL files."""
        with self._lock:
            if not self._buffer:
                return
            entries = list(self._buffer)
            self._buffer.clear()

        # Group by date
        by_date: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            ts_str = entry.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts_str)
                day_key = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            by_date.setdefault(day_key, []).append(entry)

        for day_key, day_entries in by_date.items():
            day_dir = self._base_dir / day_key
            day_dir.mkdir(parents=True, exist_ok=True)
            journal_file = day_dir / "trades.jsonl"

            with open(journal_file, "a") as f:
                for entry in day_entries:
                    f.write(json.dumps(entry, default=str) + "\n")

            self._total_entries += len(day_entries)

        self._last_flush = datetime.now(timezone.utc)
