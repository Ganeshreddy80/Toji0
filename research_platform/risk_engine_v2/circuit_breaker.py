"""Circuit breaker levels and emergency kill switch triggers."""

from __future__ import annotations

import logging
import threading
from typing import Set, Dict

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Manages emergency shutdown states and trading halts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._global_halt = False
        self._halted_symbols: Set[str] = set()
        self._drawdown_breaches: Dict[str, float] = {}

    def trigger_global_kill_switch(self, reason: str) -> None:
        with self._lock:
            self._global_halt = True
        logger.critical("GLOBAL RISK KILL SWITCH TRIGGERED: %s. HALTING ALL PLATFORM OPERATIONS.", reason)

    def reset_global_kill_switch(self) -> None:
        with self._lock:
            self._global_halt = False
        logger.info("Global risk halt reset. Trading operations resumed.")

    def halt_symbol(self, symbol: str, reason: str) -> None:
        with self._lock:
            self._halted_symbols.add(symbol)
        logger.warning("SYMBOL CIRCUIT BREAKER TRIGGERED for %s: %s.", symbol, reason)

    def resume_symbol(self, symbol: str) -> None:
        with self._lock:
            self._halted_symbols.discard(symbol)
        logger.info("Circuit breaker reset for %s.", symbol)

    def is_trading_allowed(self, symbol: str) -> bool:
        with self._lock:
            if self._global_halt:
                return False
            return symbol not in self._halted_symbols
