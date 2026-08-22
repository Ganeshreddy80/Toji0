"""Replay Journal — persists every event for deterministic replay.

Subscribes to wildcard ``"*"`` on the event bus and stores all events
as JSON lines partitioned by date. Supports loading events by date range
or session for deterministic re-publishing.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Optional

from toji_platform.core.event_bus.interfaces import IEvent, IEventBus
from toji_platform.core.lifecycle.interfaces import IHealthCheck, ILifecycle
from toji_platform.core.types import HealthStatus

logger = logging.getLogger(__name__)


class ReplayJournal(ILifecycle, IHealthCheck):
    """Captures all platform events for deterministic replay.

    Events are written as JSON lines to date-partitioned files.
    Replay can load events for a date range and optionally filter
    by session (correlation_id).
    """

    def __init__(
        self,
        base_dir: str = "data/journals/events",
        event_bus: Optional[IEventBus] = None,
        flush_interval: float = 5.0,
        max_buffer_size: int = 1000,
    ) -> None:
        self._base_dir = Path(base_dir)
        self._event_bus = event_bus
        self._flush_interval = flush_interval
        self._max_buffer_size = max_buffer_size

        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._running = False
        self._shutdown_event = threading.Event()
        self._flush_thread: Optional[threading.Thread] = None
        self._total_events = 0
        self._last_flush: Optional[datetime] = None
        self._events_per_type: dict[str, int] = {}

    # ── ILifecycle ─────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "Replay Journal"

    def start(self) -> None:
        """Start capturing events from the bus."""
        if self._running:
            return
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="ReplayJournal-Flush"
        )
        self._flush_thread.start()

        if self._event_bus is not None:
            self._event_bus.subscribe("*", self._on_event)

        logger.info("Replay Journal started ✓ (dir=%s)", self._base_dir)

    def stop(self) -> None:
        """Flush remaining events and stop capture."""
        self._running = False
        self._shutdown_event.set()
        if self._event_bus is not None:
            try:
                self._event_bus.unsubscribe("*", self._on_event)
            except Exception:
                pass
        self._flush()
        if self._flush_thread is not None:
            self._flush_thread.join(timeout=1.0)
            self._flush_thread = None
        logger.info(
            "Replay Journal stopped ✓ (%d total events captured)",
            self._total_events,
        )

    # ── IHealthCheck ───────────────────────────────────────────────────

    def check_health(self) -> HealthStatus:
        if not self._running:
            return HealthStatus.UNHEALTHY
        return HealthStatus.HEALTHY

    # ── Public API ─────────────────────────────────────────────────────

    def load_events(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        session_id: Optional[str] = None,
        event_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Load persisted events for a date range with optional filters.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            session_id: Filter by correlation_id for session replay.
            event_types: Filter to specific event types.

        Returns:
            List of event dicts ordered by timestamp.
        """
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

            events_file = day_dir / "events.jsonl"
            if not events_file.exists():
                continue

            for line in events_file.read_text().strip().splitlines():
                try:
                    event_dict = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if session_id and event_dict.get("correlation_id") != session_id:
                    continue
                if event_types and event_dict.get("event_type") not in event_types:
                    continue

                results.append(event_dict)

        return results

    def replay_to_bus(
        self,
        event_bus: IEventBus,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Load events and re-publish them to a target event bus.

        Returns the number of events replayed.
        """
        from toji_platform.core.event_bus.events import BaseEvent

        events = self.load_events(
            start_date=start_date,
            end_date=end_date,
            session_id=session_id,
        )
        replayed = 0
        for event_dict in events:
            replay_event = BaseEvent(
                source=event_dict.get("source", "replay"),
                payload=event_dict.get("payload", {}),
            )
            try:
                event_bus.publish(replay_event)
                replayed += 1
            except Exception as exc:
                logger.warning("Replay event publish failed: %s", exc)

        return replayed

    def get_stats(self) -> dict[str, Any]:
        """Return current journal statistics."""
        return {
            "total_events": self._total_events,
            "buffer_size": len(self._buffer),
            "last_flush": self._last_flush.isoformat() if self._last_flush else None,
            "events_per_type": dict(self._events_per_type),
            "base_dir": str(self._base_dir),
            "running": self._running,
        }

    # ── Event Handler ──────────────────────────────────────────────────

    def _on_event(self, event: IEvent) -> None:
        """Capture any event from the bus."""
        payload = getattr(event, "payload", {}) or {}
        correlation_id = None
        if isinstance(payload, dict):
            correlation_id = payload.get("correlation_id")

        ts = getattr(event, "timestamp", None)
        if ts and hasattr(ts, "isoformat"):
            ts_str = ts.isoformat()
        else:
            ts_str = datetime.now(timezone.utc).isoformat()

        event_type = str(getattr(event, "event_type", "unknown"))

        entry = {
            "event_id": str(getattr(event, "event_id", "")),
            "event_type": event_type,
            "source": str(getattr(event, "source", "")),
            "timestamp": ts_str,
            "correlation_id": str(correlation_id) if correlation_id else None,
            "payload": self._serialize_payload(payload),
        }

        with self._lock:
            self._buffer.append(entry)
            self._events_per_type[event_type] = (
                self._events_per_type.get(event_type, 0) + 1
            )

            # Auto-flush if buffer exceeds max size
            if len(self._buffer) >= self._max_buffer_size:
                self._flush_unlocked()

    # ── Internal ───────────────────────────────────────────────────────

    @staticmethod
    def _serialize_payload(payload: Any) -> Any:
        """Safely serialize payload to JSON-compatible format."""
        if payload is None:
            return {}
        if isinstance(payload, dict):
            result = {}
            for k, v in payload.items():
                try:
                    json.dumps(v, default=str)
                    result[k] = v
                except (TypeError, ValueError):
                    result[k] = str(v)
            return result
        return str(payload)

    def _flush_loop(self) -> None:
        """Background thread that periodically flushes the buffer."""
        while self._running:
            if self._shutdown_event.wait(self._flush_interval):
                break
            self._flush()

    def _flush(self) -> None:
        """Thread-safe flush of buffer to disk."""
        with self._lock:
            self._flush_unlocked()

    def _flush_unlocked(self) -> None:
        """Flush buffer to disk (must be called while holding self._lock)."""
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
            events_file = day_dir / "events.jsonl"

            with open(events_file, "a") as f:
                for entry in day_entries:
                    f.write(json.dumps(entry, default=str) + "\n")

            self._total_events += len(day_entries)

        self._last_flush = datetime.now(timezone.utc)
