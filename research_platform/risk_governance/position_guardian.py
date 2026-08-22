"""Position Guardian — monitors each open trade and recommends management actions."""

from __future__ import annotations

import logging
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PositionAction(str, Enum):
    HOLD = "HOLD"
    REDUCE_POSITION = "REDUCE_POSITION"
    MOVE_STOP = "MOVE_STOP"
    EXIT = "EXIT"


@dataclass
class PositionRecommendation:
    position_id: str
    symbol: str
    action: PositionAction
    reason: str
    urgency: str = "LOW"  # LOW / MEDIUM / HIGH / CRITICAL


class PositionGuardian:
    """Watches every active position and recommends protective actions.

    Triggers:
        EXIT:            SL breached; excessive time in trade; trend reversal detected.
        REDUCE_POSITION: Position approaching TP at high volatility (lock partial profit).
        MOVE_STOP:       Strong trend continuation → trail stop closer.
        HOLD:            All good — no intervention needed.
    """

    def __init__(
        self,
        max_time_in_trade_hours: float = 48.0,
        trailing_atr_multiplier: float = 1.5,
    ) -> None:
        self.max_time_in_trade_hours = max_time_in_trade_hours
        self.trailing_atr_multiplier = trailing_atr_multiplier

    def review_position(
        self,
        position: Dict[str, Any],
        current_price: float,
        current_atr: float,
        trend_direction: str,   # "bullish" / "bearish" / "neutral"
    ) -> PositionRecommendation:
        """Evaluate one active position and return a recommended action.

        Expected position dict keys:
            position_id, symbol, side, entry_price, stop_loss, take_profit,
            quantity, opened_at (datetime)
        """
        pid = position.get("position_id", "unknown")
        symbol = position.get("symbol", "UNKNOWN")
        side = position.get("side", "BUY").upper()
        entry = float(position.get("entry_price", current_price))
        sl = float(position.get("stop_loss", 0.0))
        tp = float(position.get("take_profit", 0.0))
        opened_at = position.get("opened_at", datetime.now(timezone.utc))

        # 1. Stop-loss breached → EXIT immediately
        if side == "BUY" and sl > 0.0 and current_price <= sl:
            return PositionRecommendation(pid, symbol, PositionAction.EXIT,
                                          f"Price {current_price} ≤ SL {sl}", urgency="CRITICAL")
        if side == "SELL" and sl > 0.0 and current_price >= sl:
            return PositionRecommendation(pid, symbol, PositionAction.EXIT,
                                          f"Price {current_price} ≥ SL {sl}", urgency="CRITICAL")

        # 2. Take-profit distance — if within 0.5× ATR of TP, reduce to lock profit
        if tp > 0.0:
            dist_to_tp = abs(tp - current_price)
            if current_atr > 0.0 and dist_to_tp < 0.5 * current_atr:
                return PositionRecommendation(pid, symbol, PositionAction.REDUCE_POSITION,
                                              f"Within 0.5×ATR of TP {tp:.2f}", urgency="MEDIUM")

        # 3. Trend reversal against position → EXIT
        if side == "BUY" and trend_direction == "bearish":
            return PositionRecommendation(pid, symbol, PositionAction.EXIT,
                                          "Trend reversed to bearish against long position", urgency="HIGH")
        if side == "SELL" and trend_direction == "bullish":
            return PositionRecommendation(pid, symbol, PositionAction.EXIT,
                                          "Trend reversed to bullish against short position", urgency="HIGH")

        # 4. Time limit exceeded → EXIT
        if isinstance(opened_at, datetime):
            hours_open = (datetime.now(timezone.utc) - opened_at).total_seconds() / 3600.0
            if hours_open > self.max_time_in_trade_hours:
                return PositionRecommendation(pid, symbol, PositionAction.EXIT,
                                              f"Trade open {hours_open:.1f}h > limit {self.max_time_in_trade_hours}h",
                                              urgency="MEDIUM")

        # 5. Strong trend in-favour → trail stop closer
        if side == "BUY" and trend_direction == "bullish" and current_atr > 0.0:
            new_sl = current_price - self.trailing_atr_multiplier * current_atr
            if new_sl > sl:
                return PositionRecommendation(pid, symbol, PositionAction.MOVE_STOP,
                                              f"Trail SL up to {new_sl:.2f}", urgency="LOW")

        # All clear
        return PositionRecommendation(pid, symbol, PositionAction.HOLD, "Position healthy", urgency="LOW")

    def review_all(
        self,
        positions: List[Dict[str, Any]],
        prices: Dict[str, float],
        atrs: Dict[str, float],
        trends: Dict[str, str],
    ) -> List[PositionRecommendation]:
        """Review a list of positions and return one recommendation per position."""
        recs = []
        for pos in positions:
            sym = pos.get("symbol", "UNKNOWN")
            rec = self.review_position(
                position=pos,
                current_price=prices.get(sym, 0.0),
                current_atr=atrs.get(sym, 0.0),
                trend_direction=trends.get(sym, "neutral"),
            )
            if rec.action != PositionAction.HOLD:
                logger.info("[Guardian] %s → %s: %s", sym, rec.action.value, rec.reason)
            recs.append(rec)
        return recs
