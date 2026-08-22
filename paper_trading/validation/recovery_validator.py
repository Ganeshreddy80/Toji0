"""Thread-safe Recovery Validator for Sprint 9C Paper Trading Validation."""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Tuple

from paper_trading.events import FeedRecovered
from paper_trading.feed_manager import FeedManager
from paper_trading.reconnect import ReconnectionManager
from toji_platform.core.event_bus import InMemoryEventBus

logger = logging.getLogger(__name__)


class RecoveryValidator:
    """Thread-safe Recovery Validator verifying resilience under feed disruptions, disconnects, and repeated failures."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def test_single_recovery(self, feed_manager: FeedManager) -> Tuple[bool, float]:
        """Test a single disconnect and recovery cycle.

        Returns (success: bool, recovery_duration_seconds: float).
        """
        with self._lock:
            feed_manager.connect()
            feed_manager.disconnect(reason="Test Disconnect")

            start = time.perf_counter()
            success, status = feed_manager.recover()
            elapsed = time.perf_counter() - start

            is_valid = success and status.connected is True and feed_manager.get_feed_status().connected is True
            return is_valid, elapsed

    def test_repeated_failures(self, failure_count: int = 5) -> Dict[str, float]:
        """Test repeated failure and recovery cycles and verify no state corruption or duplicate events."""
        event_bus = InMemoryEventBus()
        events_published: List[str] = []
        event_bus.subscribe("*", lambda e: events_published.append(e.event_type))

        reconn_mgr = ReconnectionManager(base_delay=0.001, max_delay=0.01, max_retries=failure_count + 2)
        fm = FeedManager(event_bus=event_bus, reconnection_manager=reconn_mgr)

        with self._lock:
            fm.connect()
            successful_recoveries = 0
            total_duration = 0.0

            for _ in range(failure_count):
                fm.disconnect(reason="Simulated Failure")
                start = time.perf_counter()
                success, status = fm.recover()
                total_duration += (time.perf_counter() - start)

                if success and status.connected:
                    successful_recoveries += 1

            # Count event types
            recovered_event_count = events_published.count("FeedRecovered")
            disconnected_event_count = events_published.count("FeedDisconnected")

            is_state_clean = (
                successful_recoveries == failure_count
                and recovered_event_count == failure_count
                and disconnected_event_count == failure_count
                and fm.get_feed_status().reconnect_count == failure_count
            )

            return {
                "failure_count": float(failure_count),
                "successful_recoveries": float(successful_recoveries),
                "recovered_event_count": float(recovered_event_count),
                "avg_recovery_time_seconds": round(total_duration / max(1, failure_count), 6),
                "state_clean": 1.0 if is_state_clean else 0.0,
            }

    def verify_no_event_duplication(self, feed_manager: FeedManager, event_bus: InMemoryEventBus) -> bool:
        """Verify that recovery events emit exactly once per recovery cycle."""
        events: List[str] = []
        event_bus.subscribe("FeedRecovered", lambda e: events.append(e.event_id))

        with self._lock:
            feed_manager.disconnect()
            feed_manager.recover()

            # Ensure event IDs are unique
            return len(events) == len(set(events))
