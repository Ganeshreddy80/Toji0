"""Strategy Selector for choosing the optimal signal from multiple strategy rules."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.models import StrategySignal
from strategy.analysis.trend_strategy import TrendFollowingStrategy
from strategy.analysis.breakout_strategy import BreakoutStrategy
from strategy.analysis.reversal_strategy import ReversalStrategy
from strategy.analysis.continuation_strategy import ContinuationStrategy
from strategy.analysis.range_strategy import RangeStrategy
from strategy.analysis.mean_reversion_strategy import MeanReversionStrategy
from strategy.analysis.momentum_strategy import MomentumStrategy


from strategy.core.interfaces import ISignalScorer, IStrategyRegistry
from strategy.core.registry import StrategyRegistry
from strategy.analysis.signal_scorer import CompositeSignalScorer


class StrategySelector:
    """Coordinates evaluating all strategy rules via StrategyRegistry and selecting the optimal setup using ISignalScorer."""

    def __init__(
        self,
        registry: IStrategyRegistry | None = None,
        scorer: ISignalScorer | None = None,
        min_confidence: float = 0.0,
    ) -> None:
        if registry is not None:
            self._registry = registry
        else:
            self._registry = StrategyRegistry()
            # Register standard built-in strategies
            self._registry.register_strategy(TrendFollowingStrategy())
            self._registry.register_strategy(BreakoutStrategy())
            self._registry.register_strategy(ReversalStrategy())
            self._registry.register_strategy(ContinuationStrategy())
            self._registry.register_strategy(RangeStrategy())
            self._registry.register_strategy(MeanReversionStrategy())
            self._registry.register_strategy(MomentumStrategy())

        self._scorer = scorer or CompositeSignalScorer()
        self._min_confidence = min_confidence

    @property
    def registry(self) -> IStrategyRegistry:
        return self._registry

    @property
    def scorer(self) -> ISignalScorer:
        return self._scorer

    def select_best_signal(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal:
        """Run all active strategies via the registry and rank signals using ISignalScorer."""
        signals = self._registry.evaluate_all(
            market_state=market_state,
            pattern_state=pattern_state,
            confluence_state=confluence_state,
            min_confidence=self._min_confidence,
        )

        if not signals:
            confluence_score = confluence_state.score.overall_score if confluence_state else 50.0
            regime_str = (
                str(market_state.trend.direction.value)
                if market_state and hasattr(market_state, "trend") and market_state.trend
                else "UNKNOWN"
            )
            return StrategySignal(
                signal_id=str(uuid.uuid4()),
                symbol=market_state.symbol,
                timeframe=market_state.timeframe,
                direction=PatternDirection.BULLISH,
                strategy_type=StrategyType.TREND_FOLLOWING,
                decision=StrategyDecision.WAIT,
                confidence=0.0,
                confluence_score=round(confluence_score, 2),
                market_regime=regime_str,
                reasoning="No valid buy/sell setups passed minimum confidence and scoring filters. Maintain wait posture.",
                supporting_factors=[],
                conflicting_factors=[],
                generated_at=datetime.now(timezone.utc),
                detected_at=datetime.now(timezone.utc),
            )

        # Rank valid signals by ISignalScorer composite score descending
        signals.sort(
            key=lambda s: self._scorer.score_signal(s, market_state, confluence_state),
            reverse=True,
        )
        return signals[0]
