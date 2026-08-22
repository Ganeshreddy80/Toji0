"""Exposure Manager — enforces portfolio allocation limits before each trade."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from research_platform.portfolio_governor.models import GovernedPosition, GovernorConfig

logger = logging.getLogger(__name__)


class ExposureManager:
    """Checks three exposure constraints before approving a new position.

    Rules (all configurable via GovernorConfig):
      1. MAX_POSITIONS   — total number of open positions
      2. EXPOSURE_LIMIT  — total portfolio capital currently deployed
      3. DUPLICATE       — same symbol + same-direction position already open
    """

    def __init__(self, config: GovernorConfig) -> None:
        self._config = config

    # ── Public API ────────────────────────────────────────────────────────────

    def check(
        self,
        symbol: str,
        direction: str,                          # "BUY" or "SELL"
        open_positions: List[GovernedPosition],
    ) -> Tuple[bool, str]:
        """Run all exposure checks.

        Returns:
            (True, "APPROVED") if all constraints pass.
            (False, "<REASON>") on first failure.
        """
        # 1. Duplicate position guard
        duplicate_ok, dup_reason = self._check_duplicate(symbol, direction, open_positions)
        if not duplicate_ok:
            return False, dup_reason

        # 2. Max open positions
        if len(open_positions) >= self._config.max_open_positions:
            logger.warning(
                "ExposureManager: MAX_POSITIONS reached (%d/%d) — rejecting %s %s",
                len(open_positions), self._config.max_open_positions, direction, symbol,
            )
            return False, "MAX_POSITIONS"

        # 3. Portfolio exposure (rough notional estimate — positions counted equally)
        #    A production implementation would use actual notional values here.
        exposure_pct = (len(open_positions) + 1) / max(self._config.max_open_positions, 1)
        if exposure_pct > self._config.max_portfolio_exposure_pct:
            logger.warning(
                "ExposureManager: EXPOSURE_LIMIT reached (%.0f%% > %.0f%%) — rejecting %s %s",
                exposure_pct * 100, self._config.max_portfolio_exposure_pct * 100,
                direction, symbol,
            )
            return False, "EXPOSURE_LIMIT"

        return True, "APPROVED"

    # ── Internals ────────────────────────────────────────────────────────────

    def _check_duplicate(
        self,
        symbol: str,
        direction: str,
        open_positions: List[GovernedPosition],
    ) -> Tuple[bool, str]:
        """Prevent adding a position in the same direction when one already exists.

        Logic:
          BUY  → maps to LONG
          SELL → maps to SHORT

        - Same direction already open? → BLOCK (DUPLICATE_POSITION)
        - Opposite direction? → ALLOW (this is a close / counter trade)
        """
        existing = next((p for p in open_positions if p.symbol == symbol), None)
        if existing is None:
            return True, "APPROVED"

        incoming_side = "LONG" if direction == "BUY" else "SHORT"

        if existing.side == incoming_side:
            logger.warning(
                "ExposureManager: DUPLICATE_POSITION %s %s already %s — rejecting %s",
                symbol, existing.side, existing.side, direction,
            )
            return False, "DUPLICATE_POSITION"

        # Opposite side = closing trade — allow through
        logger.info(
            "ExposureManager: %s %s — closing existing %s position (allowed)",
            direction, symbol, existing.side,
        )
        return True, "APPROVED"
