"""Tick dispatcher notifying registered callbacks.
"""

from __future__ import annotations

import logging
from typing import Callable, List

logger = logging.getLogger(__name__)


class TickDispatcher:
    """Dispatches real-time tick price feeds updates to registered listeners."""

    def __init__(self) -> None:
        self._listeners: List[Callable[[str, float], None]] = []

    def register_listener(self, callback: Callable[[str, float], None]) -> None:
        self._listeners.append(callback)

    def dispatch_tick(self, symbol: str, price: float) -> None:
        for cb in self._listeners:
            try:
                cb(symbol, price)
            except Exception as e:
                logger.error("Error in tick listener callback: %s", e)
