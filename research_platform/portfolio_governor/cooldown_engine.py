"""Trade Cooldown Engine — per-symbol rate limiter after fills."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Tuple

from research_platform.portfolio_governor.models import GovernorConfig

logger = logging.getLogger(__name__)


class CooldownEngine:
    """Enforces a minimum time gap between consecutive trades on the same symbol.

    Cooldown period is read from GovernorConfig.symbol_cooldowns (per-symbol override)
    or GovernorConfig.default_cooldown_seconds for all other symbols.

    Thread-safe: uses RLock for concurrent tick handler access.
    """

    def __init__(self, config: GovernorConfig) -> None:
        self._config = config
        self._last_trade_time: Dict[str, datetime] = {}
        self._lock = threading.RLock()

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self, symbol: str) -> Tuple[bool, str]:
        """Return (True, "APPROVED") if no cooldown is active; (False, "COOLDOWN_ACTIVE") otherwise."""
        with self._lock:
            last = self._last_trade_time.get(symbol)
            if last is None:
                return True, "APPROVED"

            cooldown = self._cooldown_for(symbol)
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if elapsed < cooldown:
                remaining = cooldown - elapsed
                logger.warning(
                    "CooldownEngine: %s cooldown active — %.1fs remaining (%.0fs window)",
                    symbol, remaining, cooldown,
                )
                return False, "COOLDOWN_ACTIVE"

            return True, "APPROVED"

    def record_trade(self, symbol: str) -> None:
        """Mark the symbol as traded now; resets its cooldown timer."""
        with self._lock:
            self._last_trade_time[symbol] = datetime.now(timezone.utc)
            logger.info("CooldownEngine: %s cooldown started (%.0fs)", symbol, self._cooldown_for(symbol))

    def remaining_seconds(self, symbol: str) -> float:
        """Return remaining cooldown seconds for a symbol (0 if none active)."""
        with self._lock:
            last = self._last_trade_time.get(symbol)
            if last is None:
                return 0.0
            cooldown = self._cooldown_for(symbol)
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            return max(0.0, cooldown - elapsed)

    # ── Internals ────────────────────────────────────────────────────────────

    def _cooldown_for(self, symbol: str) -> float:
        """Look up the cooldown window for a given symbol."""
        return self._config.symbol_cooldowns.get(symbol, self._config.default_cooldown_seconds)
