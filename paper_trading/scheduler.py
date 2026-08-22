"""Trading Session Scheduler managing market open/close lifecycle (Sprint 9B)."""

from __future__ import annotations

import logging
import threading
from typing import Optional

from paper_trading.events import MarketClosed, MarketOpened
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class SessionScheduler:
    """Thread-safe trading session scheduler driving market open and market close events."""

    def __init__(self, event_bus: Optional[IEventBus] = None) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus

        self._is_open: bool = False
        self._current_session_name: Optional[str] = None

    def open_market(self, session_name: str = "RegularTradingHours") -> MarketOpened:
        """Open market trading session and emit MarketOpened event."""
        with self._lock:
            self._is_open = True
            self._current_session_name = session_name

            event = MarketOpened(session_name=session_name)
            if self._event_bus:
                self._event_bus.publish(event)

            logger.info("Market session OPENED: %s", session_name)
            return event

    def close_market(self, session_name: str = "RegularTradingHours") -> MarketClosed:
        """Close market trading session and emit MarketClosed event."""
        with self._lock:
            self._is_open = False
            self._current_session_name = None

            event = MarketClosed(session_name=session_name)
            if self._event_bus:
                self._event_bus.publish(event)

            logger.info("Market session CLOSED: %s", session_name)
            return event

    def is_market_open(self) -> bool:
        """Check if market is currently open for trading."""
        with self._lock:
            return self._is_open

    def get_current_session_name(self) -> Optional[str]:
        """Get name of current active market session."""
        with self._lock:
            return self._current_session_name
