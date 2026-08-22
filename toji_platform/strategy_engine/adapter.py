"""Legacy Strategy Adapter implementation."""

from __future__ import annotations
import logging
from typing import Any

from toji_platform.strategy_engine.strategy import BaseStrategy
from toji_platform.strategy_engine.models import TradeIdea
from toji_platform.market_scanner.models import MarketScan

from market_intelligence.core.interfaces import IStateStore
from price_action.core.interfaces import IPatternStateStore
from confluence.core.interfaces import IConfluenceStateStore
from strategy.core.enums import StrategyDecision

logger = logging.getLogger(__name__)

class LegacyStrategyAdapter(BaseStrategy):
    """Adapts a legacy strategy class to the new IStrategy scanning execution model."""

    def __init__(self, name: str, legacy_strategy: Any, container: Any | None = None) -> None:
        super().__init__(name=name)
        self.legacy_strategy = legacy_strategy
        self.container = container

    def analyze(self, scan: MarketScan) -> list[TradeIdea]:
        """Query DI state stores for symbol analysis and run the legacy strategy evaluation."""
        if not self.container:
            logger.warning("Container is not set on adapter '%s'. Skipping analysis.", self._name)
            return []

        timeframe = scan.diagnostics.get("timeframe", "1m")

        # Resolve state stores from container
        market_store = self.container.resolve(IStateStore) if self.container.has(IStateStore) else None
        pattern_store = self.container.resolve(IPatternStateStore) if self.container.has(IPatternStateStore) else None
        confluence_store = self.container.resolve(IConfluenceStateStore) if self.container.has(IConfluenceStateStore) else None

        # Fetch snapshots
        market_snapshot = market_store.get_snapshot(scan.symbol) if market_store else None
        market_state = market_snapshot.states.get(timeframe) if market_snapshot else None

        if not market_state:
            logger.debug("No MarketState found for %s (%s). Skipping evaluation.", scan.symbol, timeframe)
            return []

        pattern_snapshot = pattern_store.get_snapshot(scan.symbol) if pattern_store else None
        pattern_state = pattern_snapshot.states.get(timeframe) if pattern_snapshot else None

        confluence_snapshot = confluence_store.get_snapshot(scan.symbol) if confluence_store else None
        confluence_state = confluence_snapshot.states.get(timeframe) if confluence_snapshot else None

        try:
            signal = self.legacy_strategy.evaluate(market_state, pattern_state, confluence_state)
        except Exception as e:
            logger.error("Error evaluating legacy strategy '%s': %s", self._name, e)
            return []

        if not signal or signal.decision == StrategyDecision.WAIT:
            return []

        direction = "LONG" if signal.decision == StrategyDecision.BUY else "SHORT"

        # TradeIdea expects confidence in range [0.0, 1.0].
        # Mapped from signal confidence which is typically in range [0.0, 100.0] or [0.0, 1.0].
        # In trend_strategy: confidence is round(confidence, 2) which is up to 100.0.
        # Let's map it safely. If it is > 1.0, divide by 100.0.
        confidence = signal.confidence
        if confidence > 1.0:
            confidence = confidence / 100.0

        idea = TradeIdea(
            symbol=scan.symbol,
            direction=direction,
            confidence=round(confidence, 4),
            reason=signal.reasoning,
            timestamp=signal.detected_at,
            risk_notes=""
        )

        return [idea]
