"""Order Flow Engine for analyzing volume and order book imbalance metrics."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any

from market_intelligence.core.events import OrderFlowUpdated
from market_intelligence.core.models import OrderFlowAnalysis
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class OrderFlowEngine:
    """Estimates order flow delta, large trades, buyer/seller aggressiveness and imbalances."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        self._volume_history: dict[tuple[str, str], list[float]] = {}

    def calculate_order_flow(self, candle: Any) -> OrderFlowAnalysis:
        """Process a new candle and compute rolling order flow analysis."""
        symbol = candle.symbol
        timeframe = candle.interval
        key = (symbol, timeframe)

        if key not in self._volume_history:
            self._volume_history[key] = []

        history = self._volume_history[key]
        history.append(candle.volume)
        if len(history) > 100:
            history.pop(0)

        # 1. Buy and Sell volume estimation using wick/body ratios
        ran = candle.high - candle.low
        if ran > 0.0:
            # Fraction of volume going to buy side based on where the close is relative to the range
            buy_ratio = max(0.0, min(1.0, (candle.close - candle.low) / ran))
            buy_vol = candle.volume * buy_ratio
            sell_vol = max(0.0, candle.volume - buy_vol)
        else:
            buy_ratio = 0.5
            buy_vol = candle.volume * 0.5
            sell_vol = candle.volume * 0.5

        # 2. Trade Delta
        trade_delta = buy_vol - sell_vol

        # 3. Aggressive Buyers and Sellers
        aggressive_buyers = max(0.0, buy_vol if candle.close > candle.open else buy_vol * 0.3)
        aggressive_sellers = max(0.0, sell_vol if candle.close < candle.open else sell_vol * 0.3)

        # 4. Large Trades estimation (Volume > Mean + 2 StdDev)
        large_trades = 0
        n = len(history)
        if n >= 5:
            mean_vol = sum(history) / n
            variance = sum((v - mean_vol) ** 2 for v in history) / n
            std_vol = math.sqrt(variance)
            if std_vol > 0.0 and candle.volume > mean_vol + 2.0 * std_vol:
                large_trades = 1

        # 5. Order Imbalance
        order_imbalance = (trade_delta / candle.volume) if candle.volume > 0.0 else 0.0

        analysis = OrderFlowAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            trade_delta=trade_delta,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            large_trades=large_trades,
            aggressive_buyers=aggressive_buyers,
            aggressive_sellers=aggressive_sellers,
            order_imbalance=order_imbalance,
            timestamp=candle.timestamp
        )

        self._publish_event(analysis)
        return analysis

    def _publish_event(self, analysis: OrderFlowAnalysis) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": analysis.symbol,
            "timeframe": analysis.timeframe,
            "trade_delta": analysis.trade_delta,
            "buy_volume": analysis.buy_volume,
            "sell_volume": analysis.sell_volume,
            "large_trades": analysis.large_trades,
            "aggressive_buyers": analysis.aggressive_buyers,
            "aggressive_sellers": analysis.aggressive_sellers,
            "order_imbalance": analysis.order_imbalance,
            "timestamp": analysis.timestamp.isoformat()
        }
        event = OrderFlowUpdated(
            source="market_intelligence.order_flow_engine",
            payload=payload
        )
        self._event_bus.publish(event)
