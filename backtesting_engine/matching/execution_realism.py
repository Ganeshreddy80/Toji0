"""Execution realism engines for Spread, Slippage, Commission, Market Impact, and Liquidity (Sprint 7B)."""

from __future__ import annotations

import math
import threading
from typing import Optional

from backtesting_engine.core.enums import (
    CommissionModel,
    MarketImpactModel,
    OrderType,
    PositionSide,
    SlippageModel,
    SpreadModel,
)
from backtesting_engine.core.models import BacktestConfig, MarketBar, SyntheticQuote


class SpreadEngine:
    """Deterministic synthetic bid/ask spread generator."""

    @staticmethod
    def calculate_quote(bar: MarketBar, config: BacktestConfig, base_price: Optional[float] = None) -> SyntheticQuote:
        if base_price is not None and base_price > 0.0:
            mid = base_price
        else:
            mid = bar.open if bar.open > 0.0 else bar.close

        model = config.spread_model.upper() if isinstance(config.spread_model, str) else config.spread_model.value

        if model == "NONE" or config.spread_value <= 0.0:
            spread = 0.0
        elif model == "FIXED":
            spread = config.spread_value
        elif model == "PERCENTAGE":
            spread = mid * config.spread_value
        elif model == "VOLATILITY_BASED":
            # Spread proportional to High-Low bar range
            spread = max((bar.high - bar.low) * config.spread_value, config.tick_size)
        else:
            spread = 0.0

        spread = round(spread, config.tick_precision)
        half = spread / 2.0
        bid = round(mid - half, config.tick_precision)
        ask = round(mid + half, config.tick_precision)

        # Defensive guard: Ensure bid is strictly positive (> 0.0)
        if bid <= 0.0:
            bid = config.tick_size if config.tick_size > 0.0 else 0.01

        return SyntheticQuote(
            symbol=bar.symbol,
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
            timestamp=bar.timestamp,
        )


class SlippageEngine:
    """Deterministic slippage model engine."""

    @staticmethod
    def calculate_slippage(
        base_price: float,
        side: PositionSide,
        order_qty: float,
        bar: MarketBar,
        config: BacktestConfig,
        quote: Optional[SyntheticQuote] = None,
    ) -> tuple[float, float]:
        """Returns (executed_price, absolute_slippage)."""
        model = config.slippage_model.upper() if isinstance(config.slippage_model, str) else config.slippage_model.value
        val = config.slippage_value

        if model == "NONE" or val <= 0.0:
            slippage = 0.0
        elif model == "FIXED" or model == "FIXED_TICKS":
            slippage = val * config.tick_size if model == "FIXED_TICKS" else val
        elif model == "FIXED_PERCENT" or model == "PERCENTAGE":
            slippage = base_price * val
        elif model == "SPREAD_BASED":
            spr = quote.spread if quote else (base_price * 0.0002)
            slippage = spr * val
        elif model == "VOLUME_BASED":
            vol = bar.volume if bar.volume > 0.0 else 1.0
            vol_ratio = min(order_qty / vol, 1.0)
            slippage = base_price * val * vol_ratio
        else:
            slippage = 0.0

        slippage = round(slippage, config.tick_precision)
        executed_price = base_price + slippage if side == PositionSide.LONG else base_price - slippage
        executed_price = round(executed_price, config.tick_precision)

        return executed_price, slippage


class MarketImpactEngine:
    """Deterministic order size market impact engine."""

    @staticmethod
    def calculate_impact(
        base_price: float,
        side: PositionSide,
        order_qty: float,
        bar: MarketBar,
        config: BacktestConfig,
    ) -> float:
        """Returns price impact adjustment."""
        model = config.market_impact_model.upper() if isinstance(config.market_impact_model, str) else config.market_impact_model.value
        factor = config.market_impact_factor

        if model == "NONE" or factor <= 0.0 or bar.volume <= 0.0:
            return 0.0

        participation_rate = order_qty / bar.volume

        if model == "LINEAR":
            impact_pct = factor * participation_rate
        elif model == "SQUARE_ROOT":
            impact_pct = factor * math.sqrt(participation_rate)
        else:
            impact_pct = 0.0

        impact_amount = round(base_price * impact_pct, config.tick_precision)
        return impact_amount if side == PositionSide.LONG else -impact_amount


class CommissionEngine:
    """Deterministic commission fee engine."""

    @staticmethod
    def calculate_fee(
        fill_qty: float,
        fill_price: float,
        order_type: OrderType,
        config: BacktestConfig,
    ) -> float:
        model = config.commission_model.upper() if isinstance(config.commission_model, str) else config.commission_model.value
        trade_value = fill_qty * fill_price

        if model == "FIXED":
            fee = config.commission_rate
        elif model == "PERCENTAGE":
            fee = trade_value * config.commission_rate
        elif model == "MAKER_TAKER":
            rate = config.maker_commission_rate if order_type == OrderType.LIMIT else config.taker_commission_rate
            fee = trade_value * rate
        else:
            fee = trade_value * config.commission_rate

        # Apply min / max commission bounds
        if config.min_commission > 0.0 and fee < config.min_commission:
            fee = config.min_commission

        if config.max_commission > 0.0 and fee > config.max_commission:
            fee = config.max_commission

        return round(fee, 4)


class LiquidityEngine:
    """Bar liquidity budget tracker per replay bar."""

    def __init__(self, max_volume_pct: float = 1.0) -> None:
        self._max_volume_pct = max_volume_pct
        self._available_volume: float = 0.0
        self._lock = threading.RLock()

    def reset_bar(self, bar: MarketBar, config: BacktestConfig) -> None:
        with self._lock:
            pct = config.max_volume_pct if config and config.max_volume_pct > 0.0 else self._max_volume_pct
            self._available_volume = bar.volume * pct if bar.volume > 0.0 else float("inf")

    def allocate_fill_quantity(self, requested_qty: float) -> tuple[float, bool]:
        """Returns (allocated_qty, liquidity_restricted_flag)."""
        with self._lock:
            if requested_qty <= self._available_volume:
                self._available_volume -= requested_qty
                return requested_qty, False
            else:
                allocated = self._available_volume
                self._available_volume = 0.0
                return allocated, True
