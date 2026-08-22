"""Extensible signal scoring engine implementing ISignalScorer."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.models import MarketState
from confluence.core.models import ConfluenceState
from strategy.core.interfaces import ISignalScorer
from strategy.core.models import StrategySignal

logger = logging.getLogger(__name__)


class CompositeSignalScorer(ISignalScorer):
    """
    Extensible composite signal scorer weighting normalized confidence,
    confluence scores, and market regime alignment.
    """

    def __init__(
        self,
        confidence_weight: float = 0.5,
        confluence_weight: float = 0.3,
        regime_weight: float = 0.2,
    ) -> None:
        total = confidence_weight + confluence_weight + regime_weight
        self.confidence_weight = confidence_weight / total
        self.confluence_weight = confluence_weight / total
        self.regime_weight = regime_weight / total

    def score_signal(
        self,
        signal: StrategySignal,
        market_state: MarketState,
        confluence_state: ConfluenceState | None = None,
    ) -> float:
        """Calculate composite rank score [0.0, 1.0] for a candidate signal."""
        # 1. Normalized confidence [0.0, 1.0]
        conf_score = signal.confidence if signal.confidence <= 1.0 else signal.confidence / 100.0

        # 2. Normalized confluence score [0.0, 1.0]
        raw_confluence = (
            confluence_state.score.overall_score
            if confluence_state and hasattr(confluence_state, "score")
            else signal.confluence_score
        )
        conf_score_norm = raw_confluence / 100.0 if raw_confluence > 1.0 else raw_confluence
        conf_score_norm = max(0.0, min(1.0, conf_score_norm))

        # 3. Market regime alignment bonus [0.0, 1.0]
        regime_bonus = 0.5
        if market_state and hasattr(market_state, "trend") and market_state.trend:
            t_dir = getattr(market_state.trend, "direction", None)
            trend_str = str(getattr(t_dir, "value", t_dir) or "").upper()
            sig_dir = str(getattr(signal.direction, "value", signal.direction) or "").upper()

            if ("UP" in trend_str or "BULLISH" in trend_str) and "BULLISH" in sig_dir:
                regime_bonus = 1.0
            elif ("DOWN" in trend_str or "BEARISH" in trend_str) and "BEARISH" in sig_dir:
                regime_bonus = 1.0
            elif "SIDEWAYS" in trend_str and signal.strategy_type.value in ("Range", "Mean Reversion"):
                regime_bonus = 0.9

        composite_score = (
            (conf_score * self.confidence_weight)
            + (conf_score_norm * self.confluence_weight)
            + (regime_bonus * self.regime_weight)
        )
        return round(max(0.0, min(1.0, composite_score)), 4)
