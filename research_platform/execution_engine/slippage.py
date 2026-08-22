"""Slippage Engine — estimates market impact from order size and volatility."""

from __future__ import annotations


class SlippageEngine:
    """Estimates the price slippage incurred when filling an order.

    Slippage grows with order size (relative to market volume) and
    volatility (ATR-derived).  The resulting *slippage_cost* is the
    total USDT impact on the trade.
    """

    def __init__(
        self,
        base_slippage_bps: float = 5.0,   # baseline slippage in basis-points (0.05 %)
        impact_factor: float = 0.10,       # market-impact coefficient (order/volume)
        volatility_factor: float = 0.20,   # volatility coefficient
    ) -> None:
        self.base_slippage_bps = base_slippage_bps
        self.impact_factor = impact_factor
        self.volatility_factor = volatility_factor

    def calculate_slippage(
        self,
        price: float,
        order_qty: float,
        market_volume: float,
        atr: float,
        side: str = "BUY",
    ) -> dict:
        """Return slippage in price units and total USDT cost.

        Args:
            price:          Mid-market price at decision time.
            order_qty:      Order size in base asset units (e.g. BTC).
            market_volume:  Recent market volume in same units.
            atr:            Current ATR value (same currency as price).
            side:           BUY (slips up) or SELL (slips down).

        Returns dict with keys:
            fill_price, slippage_abs, slippage_pct, slippage_cost
        """
        if price <= 0.0:
            return {"fill_price": price, "slippage_abs": 0.0,
                    "slippage_pct": 0.0, "slippage_cost": 0.0}

        # 1. Base slippage (bps → fraction)
        base_pct = self.base_slippage_bps / 10_000.0

        # 2. Size impact: larger orders consume deeper book levels
        size_ratio = (order_qty / market_volume) if market_volume > 0.0 else 0.0
        size_impact = self.impact_factor * size_ratio

        # 3. Volatility impact: high ATR → wider fills
        vol_ratio = (atr / price) if price > 0.0 else 0.0
        vol_impact = self.volatility_factor * vol_ratio

        total_pct = base_pct + size_impact + vol_impact

        # 4. Direction: BUY pays a higher price, SELL gets a lower price
        if side.upper() == "BUY":
            fill_price = price * (1.0 + total_pct)
        else:
            fill_price = price * (1.0 - total_pct)

        slippage_abs = abs(fill_price - price)
        slippage_cost = slippage_abs * order_qty

        return {
            "fill_price": round(fill_price, 2),
            "slippage_abs": round(slippage_abs, 4),
            "slippage_pct": round(total_pct * 100.0, 4),
            "slippage_cost": round(slippage_cost, 4),
        }
