"""WebSocket Manager tracking connections, heartbeats, and reconnections.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connection health, auto-reconnects, and heartbeats."""

    def __init__(self, exchange: str) -> None:
        self.exchange = exchange
        self._connected = False
        self._reconnect_count = 0
        self._last_heartbeat: Optional[datetime] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    def connect(self) -> None:
        self._connected = True
        self._last_heartbeat = datetime.now(timezone.utc)
        logger.info("WebSocket connected to %s", self.exchange)

    def disconnect(self) -> None:
        self._connected = False
        logger.warning("WebSocket disconnected from %s", self.exchange)

    def trigger_reconnect(self) -> None:
        self._reconnect_count += 1
        self.connect()

    def send_ping(self) -> bool:
        """Simulate sending heartbeat ping."""
        if not self._connected:
            return False
        self._last_heartbeat = datetime.now(timezone.utc)
        return True
