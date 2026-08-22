"""Strategy composer templates for institutional trading logic."""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from research_platform.strategy_framework.models import StrategyMetadata, ComposedStrategy

logger = logging.getLogger(__name__)


class StrategyComposer:
    """Composes modular strategy rules based on predefined templates."""

    def compose(
        self,
        strategy_id: str,
        name: str,
        strategy_type: str,
        version: str,
        symbols: List[str],
        parameters: Dict[str, Any]
    ) -> ComposedStrategy:
        valid_types = {
            "TREND_FOLLOWING", "BREAKOUT", "MEAN_REVERSION", "MOMENTUM",
            "SCALPING", "SWING", "VOLATILITY", "GRID", "AI"
        }
        if strategy_type.upper() not in valid_types:
            raise ValueError(f"Invalid strategy type: {strategy_type}. Must be one of {valid_types}")

        meta = StrategyMetadata(
            strategy_id=strategy_id,
            name=name,
            strategy_type=strategy_type.upper(),
            version=version,
            parameters=parameters
        )
        return ComposedStrategy(
            metadata=meta,
            symbols=symbols,
            active=True
        )

    def evaluate_strategy(self, strategy: ComposedStrategy, symbol: str, current_price: float, indicators: Dict[str, Any]) -> str:
        """Evaluates composed strategy rules, returning BUY, SELL, or WAIT."""
        stype = strategy.metadata.strategy_type
        params = strategy.metadata.parameters

        if stype == "TREND_FOLLOWING":
            # Rule: Buy if price > daily moving average or trend bias is bullish
            trend = indicators.get("trend", "NEUTRAL")
            return "BUY" if trend == "BULLISH" else ("SELL" if trend == "BEARISH" else "WAIT")

        elif stype == "MEAN_REVERSION":
            # Rule: Buy if price is below lower band (e.g. price < VWAP - 2 * ATR)
            vwap = indicators.get("vwap", current_price)
            atr = indicators.get("atr", current_price * 0.01)
            lower_band = vwap - (params.get("deviation", 2.0) * atr)
            upper_band = vwap + (params.get("deviation", 2.0) * atr)
            if current_price < lower_band:
                return "BUY"
            elif current_price > upper_band:
                return "SELL"
            return "WAIT"

        elif stype == "BREAKOUT":
            # Rule: Buy if price exceeds last swing high
            swing_high = indicators.get("swing_high", float('inf'))
            swing_low = indicators.get("swing_low", float('-inf'))
            if current_price > swing_high:
                return "BUY"
            elif current_price < swing_low:
                return "SELL"
            return "WAIT"

        elif stype == "AI":
            # Rule: Directly follow AI Signal Engine output
            return indicators.get("ai_signal", "WAIT")

        # Fallback wait for other types (Grid, Volatility, Momentum, Scalping, Swing)
        return "WAIT"

    def generate_decision(
        self,
        strategy: ComposedStrategy,
        symbol: str,
        current_price: float,
        indicators: Dict[str, Any]
    ) -> Any:
        """Evaluates strategy and returns StrategyDecision enum."""
        from strategy.core.enums import StrategyDecision
        decision_str = self.evaluate_strategy(strategy, symbol, current_price, indicators)
        return StrategyDecision(decision_str)
