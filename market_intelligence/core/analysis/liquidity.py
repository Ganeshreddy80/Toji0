"""Liquidity Sweep Engine for detecting buy-side and sell-side sweeps."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.enums import SwingType
from market_intelligence.core.events import LiquiditySwept, LiquidityUpdated
from market_intelligence.core.models import LiquidityState, SwingPoint, LiquidityAnalysis
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class LiquidityEngine:
    """Tracks active liquidity pools and detects wicking sweeps with volume filters."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        # Mapping: (symbol, timeframe) -> LiquidityState
        self._states: dict[tuple[str, str], LiquidityState] = {}
        # Mapping: (symbol, timeframe) -> LiquidityAnalysis Pydantic model
        self._pydantic_liquidity: dict[tuple[str, str], LiquidityAnalysis] = {}
        # Active pools tracking: (symbol, timeframe) -> list of SwingPoint
        self._active_highs: dict[tuple[str, str], list[SwingPoint]] = {}
        self._active_lows: dict[tuple[str, str], list[SwingPoint]] = {}

    def get_liquidity_state(self, symbol: str, timeframe: str) -> LiquidityState:
        """Get the current LiquidityState or return an empty default state."""
        key = (symbol, timeframe)
        if key not in self._states:
            self._states[key] = LiquidityState(
                symbol=symbol,
                timeframe=timeframe,
                buy_side_pools=[],
                sell_side_pools=[],
                swept_levels=[],
            )
        return self._states[key]

    def get_pydantic_liquidity(self, symbol: str, timeframe: str) -> LiquidityAnalysis | None:
        """Get the current Pydantic LiquidityAnalysis model."""
        return self._pydantic_liquidity.get((symbol, timeframe))

    def register_swing(self, swing: SwingPoint) -> None:
        """Register a newly confirmed swing point as an active liquidity pool."""
        symbol = swing.symbol
        timeframe = swing.timeframe
        key = (symbol, timeframe)

        if key not in self._active_highs:
            self._active_highs[key] = []
            self._active_lows[key] = []

        if swing.point_type == SwingType.HIGH:
            self._active_highs[key].append(swing)
        else:
            self._active_lows[key].append(swing)

        self._update_state(symbol, timeframe)

    def evaluate_sweeps(
        self,
        symbol: str,
        timeframe: str,
        current_candle: Any,
        volume_rvol: float,
    ) -> LiquidityState:
        """Check active pools against wicks and close price of the current candle, and update metrics."""
        key = (symbol, timeframe)
        state = self.get_liquidity_state(symbol, timeframe)

        active_highs = self._active_highs.get(key, [])
        active_lows = self._active_lows.get(key, [])

        remaining_highs: list[SwingPoint] = []
        remaining_lows: list[SwingPoint] = []
        swept_levels = list(state.swept_levels)

        close_price = current_candle.close
        high_price = current_candle.high
        low_price = current_candle.low

        # 1. Evaluate Buy-side Liquidity (swings high)
        for sh in active_highs:
            # Check for sweep
            if high_price > sh.price and close_price < sh.price:
                # Volume confirmation filter: RVOL > 1.5
                if volume_rvol > 1.5:
                    swept_levels.append(sh.price)
                    self._publish_sweep_event(symbol, timeframe, sh, "BUY_SIDE", current_candle)
                else:
                    # If volume is insufficient, we still remove it as it was wicked
                    pass
            elif close_price >= sh.price:
                # Clean breakout/breach, remove it silently
                pass
            else:
                remaining_highs.append(sh)

        # 2. Evaluate Sell-side Liquidity (swings low)
        for sl in active_lows:
            # Check for sweep
            if low_price < sl.price and close_price > sl.price:
                # Volume confirmation filter: RVOL > 1.5
                if volume_rvol > 1.5:
                    swept_levels.append(sl.price)
                    self._publish_sweep_event(symbol, timeframe, sl, "SELL_SIDE", current_candle)
                else:
                    pass
            elif close_price <= sl.price:
                # Clean breakout/breach, remove it silently
                pass
            else:
                remaining_lows.append(sl)

        self._active_highs[key] = remaining_highs
        self._active_lows[key] = remaining_lows

        # Limit swept history count
        if len(swept_levels) > 100:
            swept_levels = swept_levels[-100:]

        buy_side_pools = [sh.price for sh in remaining_highs]
        sell_side_pools = [sl.price for sl in remaining_lows]

        new_state = LiquidityState(
            symbol=symbol,
            timeframe=timeframe,
            buy_side_pools=buy_side_pools,
            sell_side_pools=sell_side_pools,
            swept_levels=swept_levels,
        )
        self._states[key] = new_state

        # Calculate Pydantic LiquidityAnalysis metrics
        bid_ask_spread = close_price * 0.0001 * (1.0 + volume_rvol * 0.5)
        depth = current_candle.volume * 2.5
        market_impact_estimate = 0.0005 * volume_rvol
        slippage_estimate = 0.0002 * volume_rvol
        volume_score = min(100.0, volume_rvol * 50.0)
        
        # Combined liquidity score (0 to 100)
        liquidity_score = max(0.0, min(100.0, 100.0 - (bid_ask_spread / close_price * 10000.0) - (slippage_estimate * 5000.0)))

        analysis = LiquidityAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            bid_ask_spread=bid_ask_spread,
            depth=depth,
            market_impact_estimate=market_impact_estimate,
            slippage_estimate=slippage_estimate,
            volume_score=volume_score,
            liquidity_score=liquidity_score,
            buy_side_pools=buy_side_pools,
            sell_side_pools=sell_side_pools,
            swept_levels=swept_levels,
            timestamp=current_candle.timestamp,
        )
        self._pydantic_liquidity[key] = analysis
        self._publish_liquidity_updated(analysis)

        return new_state

    def _update_state(self, symbol: str, timeframe: str) -> None:
        key = (symbol, timeframe)
        highs = self._active_highs.get(key, [])
        lows = self._active_lows.get(key, [])
        state = self.get_liquidity_state(symbol, timeframe)

        new_state = LiquidityState(
            symbol=symbol,
            timeframe=timeframe,
            buy_side_pools=[sh.price for sh in highs],
            sell_side_pools=[sl.price for sl in lows],
            swept_levels=state.swept_levels,
        )
        self._states[key] = new_state

    def _publish_sweep_event(
        self,
        symbol: str,
        timeframe: str,
        swing: SwingPoint,
        pool_type: str,
        candle: Any,
    ) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "level_swept": swing.price,
            "pool_type": pool_type,
            "candle_timestamp": candle.timestamp.isoformat(),
            "volume_at_sweep": candle.volume,
        }

        event = LiquiditySwept(
            source="market_intelligence.liquidity_engine",
            payload=payload,
        )
        self._event_bus.publish(event)

    def _publish_liquidity_updated(self, analysis: LiquidityAnalysis) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": analysis.symbol,
            "timeframe": analysis.timeframe,
            "bid_ask_spread": analysis.bid_ask_spread,
            "depth": analysis.depth,
            "market_impact_estimate": analysis.market_impact_estimate,
            "slippage_estimate": analysis.slippage_estimate,
            "volume_score": analysis.volume_score,
            "liquidity_score": analysis.liquidity_score,
            "buy_side_pools": analysis.buy_side_pools,
            "sell_side_pools": analysis.sell_side_pools,
            "swept_levels": analysis.swept_levels,
            "timestamp": analysis.timestamp.isoformat()
        }
        event = LiquidityUpdated(
            source="market_intelligence.liquidity_engine",
            payload=payload
        )
        self._event_bus.publish(event)
