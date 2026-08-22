"""Portfolio Governor — central pre-execution signal gate.

Signal flow:
  AISignal
    ↓
  PortfolioGovernor.evaluate(signal)
    ├─ CooldownEngine.check()        → COOLDOWN_ACTIVE?
    ├─ ExposureManager.check()       → DUPLICATE_POSITION | MAX_POSITIONS | EXPOSURE_LIMIT?
    └─ APPROVED → caller may proceed to TradeManager
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.portfolio_governor.interfaces import IPortfolioGovernor
from research_platform.portfolio_governor.models import (
    GovernorConfig,
    GovernedPosition,
    PortfolioDecision,
)
from research_platform.portfolio_governor.position_manager import PositionManager
from research_platform.portfolio_governor.exposure_manager import ExposureManager
from research_platform.portfolio_governor.cooldown_engine import CooldownEngine
from research_platform.portfolio_governor.events import (
    GovernorPositionClosed,
    GovernorPositionOpened,
    GovernorPositionUpdated,
    PortfolioDecisionCreated,
)

logger = logging.getLogger(__name__)


class PortfolioGovernor(IPortfolioGovernor):
    """Orchestrates position, exposure, and cooldown checks before trade execution.

    Thread-safe: all mutable state is inside child managers that use RLocks.
    """

    def __init__(
        self,
        config: GovernorConfig,
        event_bus: Optional[IEventBus] = None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus

        self._position_mgr = PositionManager()
        self._exposure_mgr = ExposureManager(config)
        self._cooldown_engine = CooldownEngine(config)

        # Rejection counters
        self._blocked_cooldown = 0
        self._blocked_duplicate = 0
        self._blocked_exposure = 0
        self._blocked_max_positions = 0
        self._approved_count = 0

        self._lock = threading.RLock()

    # ── IPortfolioGovernor ────────────────────────────────────────────────────

    def evaluate(self, signal: Any) -> PortfolioDecision:
        """Evaluate a trading signal against all governance rules.

        Args:
            signal: Any object exposing .symbol, .direction, and optionally .signal_id

        Returns:
            PortfolioDecision with approved=True/False and reason string.
        """
        symbol: str = getattr(signal, "symbol", "")
        direction: str = getattr(signal, "direction", "")
        signal_id: str = getattr(signal, "signal_id", "")

        open_positions = self._position_mgr.get_all_positions()

        # ── Gate 1: Cooldown ─────────────────────────────────────────────────
        cd_ok, cd_reason = self._cooldown_engine.check(symbol)
        if not cd_ok:
            decision = PortfolioDecision(
                approved=False,
                reason="COOLDOWN_ACTIVE",
                symbol=symbol,
                direction=direction,
                signal_id=signal_id,
            )
            self._record_block("cooldown")
            self._publish_decision(decision)
            return decision

        # ── Gate 2: Exposure / Duplicate / Max-positions ─────────────────────
        exp_ok, exp_reason = self._exposure_mgr.check(symbol, direction, open_positions)
        if not exp_ok:
            decision = PortfolioDecision(
                approved=False,
                reason=exp_reason,   # type: ignore[arg-type]
                symbol=symbol,
                direction=direction,
                signal_id=signal_id,
            )
            self._record_block(exp_reason.lower())
            self._publish_decision(decision)
            return decision

        # ── APPROVED ─────────────────────────────────────────────────────────
        decision = PortfolioDecision(
            approved=True,
            reason="APPROVED",
            symbol=symbol,
            direction=direction,
            signal_id=signal_id,
        )
        with self._lock:
            self._approved_count += 1
        logger.info("PortfolioGovernor: APPROVED %s %s (signal=%s)", direction, symbol, signal_id)
        self._publish_decision(decision)
        return decision

    def record_fill(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        price: float,
    ) -> None:
        """Update governor state after a confirmed order fill.

        - Opens or extends position in PositionManager.
        - Starts cooldown timer.
        - Publishes position event.
        """
        side = "LONG" if direction == "BUY" else "SHORT"

        # Check if this is a closing trade (opposite side exists)
        existing = self._position_mgr.get_position(symbol)
        if existing and existing.side != side:
            # Closing / reversing: reduce or close existing position
            pos = self._position_mgr.reduce_position(symbol, quantity, price)
            if pos is None or pos.quantity == 0.0:
                self._publish(GovernorPositionClosed(payload={"symbol": symbol}))
            else:
                self._publish(GovernorPositionUpdated(payload={"symbol": symbol, "quantity": pos.quantity}))
        else:
            # Opening or adding to same-side position
            pos = self._position_mgr.open_position(symbol, side, quantity, price)
            if existing is None:
                self._publish(GovernorPositionOpened(payload={"symbol": symbol, "side": side}))
            else:
                self._publish(GovernorPositionUpdated(payload={"symbol": symbol, "quantity": pos.quantity}))

        # Always start cooldown after any fill
        self._cooldown_engine.record_trade(symbol)
        logger.info("PortfolioGovernor: fill recorded %s %s qty=%.4f @ %.2f", direction, symbol, quantity, price)

    def get_portfolio_summary(self) -> Dict:
        """Return serialisable portfolio snapshot for runtime/status API."""
        positions = self._position_mgr.get_all_positions()
        total_unrealized = sum(p.unrealized_pnl for p in positions)
        total_realized = sum(p.realized_pnl for p in positions)

        with self._lock:
            blocked = {
                "cooldown": self._blocked_cooldown,
                "duplicate": self._blocked_duplicate,
                "exposure": self._blocked_exposure,
                "max_positions": self._blocked_max_positions,
            }
            approved = self._approved_count

        # Simple exposure = positions open / max_positions
        exposure = len(positions) / max(self._config.max_open_positions, 1)

        return {
            "open_positions": len(positions),
            "exposure": round(exposure, 4),
            "unrealized_pnl": round(total_unrealized, 2),
            "realized_pnl": round(total_realized, 2),
            "approved_trades": approved,
            "blocked_trades": blocked,
            "positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "quantity": p.quantity,
                    "avg_entry": round(p.average_entry_price, 4),
                    "current_price": round(p.current_price, 4),
                    "unrealized_pnl": round(p.unrealized_pnl, 2),
                    "realized_pnl": round(p.realized_pnl, 2),
                    "opened_at": p.opened_at.isoformat(),
                }
                for p in positions
            ],
        }

    def update_market_price(self, symbol: str, price: float) -> None:
        """Propagate price tick to position manager for unrealized PnL refresh."""
        self._position_mgr.update_price(symbol, price)

    # ── Internals ────────────────────────────────────────────────────────────

    def _record_block(self, reason_lower: str) -> None:
        with self._lock:
            if reason_lower == "cooldown":
                self._blocked_cooldown += 1
            elif reason_lower == "duplicate_position":
                self._blocked_duplicate += 1
            elif reason_lower == "exposure_limit":
                self._blocked_exposure += 1
            elif reason_lower == "max_positions":
                self._blocked_max_positions += 1

    def _publish_decision(self, decision: PortfolioDecision) -> None:
        self._publish(
            PortfolioDecisionCreated(
                payload={
                    "approved": decision.approved,
                    "reason": decision.reason,
                    "symbol": decision.symbol,
                    "direction": decision.direction,
                }
            )
        )

    def _publish(self, event: Any) -> None:
        if self._event_bus:
            try:
                self._event_bus.publish(event)
            except Exception as exc:
                logger.debug("PortfolioGovernor: failed to publish event %s: %s", type(event).__name__, exc)
