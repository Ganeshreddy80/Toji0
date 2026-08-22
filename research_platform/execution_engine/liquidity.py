"""Liquidity Engine — rejects orders that exceed safe market depth limits."""

from __future__ import annotations

from dataclasses import dataclass


# Maximum fraction of recent volume that a single order is permitted to consume.
DEFAULT_MAX_VOLUME_PCT = 0.20   # 20 %


@dataclass
class LiquidityCheckResult:
    passed: bool
    order_qty: float
    market_volume: float
    volume_consumed_pct: float
    reason: str


class LiquidityEngine:
    """Analyses market depth and rejects orders that create excessive impact.

    A trade is rejected when:
        order_qty / market_volume  >  max_volume_pct
    """

    def __init__(self, max_volume_pct: float = DEFAULT_MAX_VOLUME_PCT) -> None:
        self.max_volume_pct = max_volume_pct

    def check_liquidity(
        self,
        order_qty: float,
        market_volume: float,
    ) -> LiquidityCheckResult:
        """Validate that the order size is within safe liquidity bounds.

        Args:
            order_qty:      Requested order size (base asset units, e.g. BTC).
            market_volume:  Recent market volume in the same units.

        Returns:
            LiquidityCheckResult with *passed=True* when acceptable.
        """
        if market_volume <= 0.0:
            return LiquidityCheckResult(
                passed=False,
                order_qty=order_qty,
                market_volume=market_volume,
                volume_consumed_pct=100.0,
                reason="Market volume unavailable — cannot verify liquidity",
            )

        consumed_pct = (order_qty / market_volume) * 100.0

        if consumed_pct > self.max_volume_pct * 100.0:
            return LiquidityCheckResult(
                passed=False,
                order_qty=order_qty,
                market_volume=market_volume,
                volume_consumed_pct=round(consumed_pct, 2),
                reason=(
                    f"Order exceeds liquidity limit: {order_qty:.4f} / "
                    f"{market_volume:.4f} = {consumed_pct:.1f}% "
                    f"(limit {self.max_volume_pct * 100:.0f}%)"
                ),
            )

        return LiquidityCheckResult(
            passed=True,
            order_qty=order_qty,
            market_volume=market_volume,
            volume_consumed_pct=round(consumed_pct, 2),
            reason="PASS",
        )
