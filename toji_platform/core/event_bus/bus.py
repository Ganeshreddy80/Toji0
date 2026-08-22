"""In-memory event bus implementation.

``InMemoryEventBus`` is the default, synchronous, single-process
event bus.  It is sufficient for local development and testing.
A distributed implementation (e.g. Redis Pub/Sub) can be swapped
in by implementing ``IEventBus``.
"""

from __future__ import annotations

import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Callable, Any

from toji_platform.core.errors import EventBusError
from toji_platform.core.event_bus.interfaces import (
    EventHandler,
    IEvent,
    IEventBus,
    IEventHandler,
)

logger = logging.getLogger(__name__)

# Internal normalised handler type
_NormHandler = Callable[[IEvent], None]

_WILDCARD = "*"


class InMemoryEventBus(IEventBus):
    """Dict-backed publish/subscribe bus with wildcard support.

    * Subscribe to a specific event type: ``bus.subscribe("system.asset_selected", fn)``
    * Subscribe to **all** events: ``bus.subscribe("*", fn)``
    * Handlers are called synchronously in registration order.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[_NormHandler]] = defaultdict(list)
        self._timeline: deque[dict[str, Any]] = deque(maxlen=100)
        import threading
        self._lock = threading.RLock()
        self.exception_count = 0

    # ── helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _normalise(handler: EventHandler | IEventHandler) -> _NormHandler:
        """Wrap class-based handlers so everything is a plain callable."""
        if isinstance(handler, IEventHandler):
            return handler.handle
        return handler  # type: ignore[return-value]

    # ── IEventBus ──────────────────────────────────────────────────────
    def publish(self, event: IEvent) -> None:
        """Broadcast *event* to type-specific and wildcard subscribers."""
        event_type = event.event_type
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
            handlers.extend(self._handlers.get(_WILDCARD, []))

        start_time = time.perf_counter()
        errors = []
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                self.exception_count += 1
                logger.error(
                    "Handler %s failed for event %s: %s",
                    handler,
                    event_type,
                    exc,
                )
                errors.append(exc)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        
        # Extract correlation ID and other details safely
        payload = getattr(event, "payload", {}) or {}
        correlation_id = getattr(event, "correlation_id", None)
        if not correlation_id and isinstance(payload, dict):
            correlation_id = payload.get("correlation_id")
            # Try nested signal structure if applicable
            if not correlation_id and "signal" in payload:
                signal = payload.get("signal") or {}
                if isinstance(signal, dict):
                    correlation_id = signal.get("correlation_id")
        
        event_id = getattr(event, "event_id", "")
        source = getattr(event, "source", "")
        ts = getattr(event, "timestamp", None)
        if ts:
            if hasattr(ts, "isoformat"):
                ts_str = ts.isoformat()
            else:
                ts_str = str(ts)
        else:
            ts_str = datetime.now(timezone.utc).isoformat()
            
        with self._lock:
            self._timeline.append({
                "event_id": str(event_id),
                "event_type": str(event_type),
                "source": str(source),
                "timestamp": ts_str,
                "correlation_id": str(correlation_id) if correlation_id else None,
                "processing_latency_ms": latency_ms,
            })

        if errors:
            if len(errors) == 1:
                raise EventBusError(
                    f"Handler failed for {event_type}: {errors[0]}"
                ) from errors[0]
            else:
                raise EventBusError(
                    f"Multiple handlers failed for {event_type}: {errors}"
                )

    def get_timeline(self) -> list[dict[str, Any]]:
        """Retrieve the latest 100 event dispatch traces."""
        with self._lock:
            return list(self._timeline)

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler | IEventHandler,
    ) -> None:
        """Register *handler* for *event_type* (or ``'*'`` for all)."""
        normalised = self._normalise(handler)
        with self._lock:
            if normalised not in self._handlers[event_type]:
                self._handlers[event_type].append(normalised)
            else:
                logger.debug("InMemoryEventBus: Handler already registered to '%s'", event_type)
        logger.debug("Subscribed handler to '%s'", event_type)

    def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler | IEventHandler,
    ) -> None:
        """Remove a previously registered handler."""
        normalised = self._normalise(handler)
        with self._lock:
            if event_type in self._handlers:
                handlers = self._handlers[event_type]
                try:
                    handlers.remove(normalised)
                except ValueError:
                    logger.warning(
                        "Handler not found for event type '%s'", event_type
                    )
                if not handlers:
                    del self._handlers[event_type]

    def has_subscribers(self, event_type: str) -> bool:
        """Return ``True`` if at least one handler is registered."""
        with self._lock:
            return bool(self._handlers.get(event_type))

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._handlers.clear()
        logger.debug("All event subscriptions cleared")
