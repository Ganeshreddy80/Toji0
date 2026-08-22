"""Heartbeat Monitor tracking periodic component signals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    """Detects stalled threads and missing component heartbeats."""

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._last_pulses: Dict[str, datetime] = {}

    def record_heartbeat(self, subsystem: str) -> None:
        self._last_pulses[subsystem] = datetime.now(timezone.utc)

    def check_heartbeats(self) -> List[str]:
        """Detect missing workers or stalled loops. Returns list of dead subsystems."""
        dead = []
        now = datetime.now(timezone.utc)
        
        for sub, pulse in self._last_pulses.items():
            diff = (now - pulse).total_seconds()
            if diff > self.timeout_seconds:
                dead.append(sub)
                logger.warning("Heartbeat missing: Subsystem %s has not responded for %s seconds.", sub, diff)
                
        return dead
