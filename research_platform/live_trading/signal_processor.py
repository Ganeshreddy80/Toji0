"""Signal Processor ingestion and filters duplicate strategy signals.
"""

from __future__ import annotations

import logging
from typing import Set

from research_platform.live_trading.interfaces import ISignalProcessor
from research_platform.live_trading.models import ActiveSignal

logger = logging.getLogger(__name__)


class SignalProcessor(ISignalProcessor):
    """Filters duplicate signals and validates alpha strategy bounds."""

    def __init__(self, min_strength: float = 0.1) -> None:
        self.min_strength = min_strength
        self._processed_ids: Set[str] = set()

    def process_signal(self, signal: ActiveSignal) -> bool:
        """Filter duplicate signals. Returns True if valid."""
        if signal.signal_id in self._processed_ids:
            logger.warning("Duplicate signal rejected: %s", signal.signal_id)
            return False
            
        if signal.strength < self.min_strength:
            logger.warning("Signal %s rejected: strength %f is below min limit %f", 
                           signal.signal_id, signal.strength, self.min_strength)
            return False

        self._processed_ids.add(signal.signal_id)
        return True
