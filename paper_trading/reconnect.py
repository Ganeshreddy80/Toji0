"""Reconnection Manager providing exponential backoff recovery workflows (Sprint 9B)."""

from __future__ import annotations

import logging
import threading
import time
from typing import Tuple

logger = logging.getLogger(__name__)


class ReconnectionManager:
    """Thread-safe reconnection coordinator implementing exponential backoff and retry policy."""

    def __init__(
        self,
        base_delay: float = 0.1,
        max_delay: float = 5.0,
        max_retries: int = 5,
    ) -> None:
        self._lock = threading.RLock()
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._max_retries = max_retries

        self._attempts: int = 0
        self._is_reconnecting: bool = False

    def register_disconnect(self) -> None:
        """Flag disconnect state."""
        with self._lock:
            self._is_reconnecting = True

    def calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay for given attempt index."""
        if attempt <= 0:
            return 0.0
        delay = self._base_delay * (2 ** (attempt - 1))
        return min(self._max_delay, delay)

    def attempt_reconnect(self) -> Tuple[bool, float, int]:
        """Execute a reconnection attempt step using exponential backoff strategy.

        Returns (success: bool, delay_applied: float, attempt_count: int).
        """
        with self._lock:
            if self._attempts >= self._max_retries:
                logger.error("Max reconnection retries (%d) exhausted.", self._max_retries)
                return False, 0.0, self._attempts

            self._attempts += 1
            curr_attempt = self._attempts
            delay = self.calculate_backoff(curr_attempt)

        if delay > 0.0:
            time.sleep(delay)

        with self._lock:
            self._is_reconnecting = False
            return True, delay, curr_attempt

    def reset(self) -> None:
        """Reset reconnection state on successful recovery."""
        with self._lock:
            self._attempts = 0
            self._is_reconnecting = False

    @property
    def attempts(self) -> int:
        """Get current reconnection attempt count."""
        with self._lock:
            return self._attempts

    @property
    def is_reconnecting(self) -> bool:
        """Get whether currently in a reconnection cycle."""
        with self._lock:
            return self._is_reconnecting
