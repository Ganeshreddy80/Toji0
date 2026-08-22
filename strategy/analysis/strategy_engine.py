"""Strategy Engine coordinating context validation and strategy selection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.interfaces import IStrategyEngine
from strategy.core.models import StrategySignal
from strategy.analysis.setup_validator import SetupValidator
from strategy.analysis.strategy_selector import StrategySelector


import logging

logger = logging.getLogger(__name__)


class StrategyEngine(IStrategyEngine):
    """Authoritative strategy engine to calculate setup signals."""

    def __init__(
        self,
        selector: StrategySelector | None = None,
        validator: SetupValidator | None = None,
        container: Any | None = None,
    ) -> None:
        self._selector = selector or StrategySelector()
        self._validator = validator or SetupValidator()
        self._container = container

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal:
        """Evaluate strategy signals from market, pattern, and confluence states."""
        # 1. Fail-Closed Guard: Validate required market_state input
        if market_state is None or not getattr(market_state, "symbol", None) or not getattr(market_state, "timeframe", None):
            symbol = getattr(market_state, "symbol", "UNKNOWN") if market_state else "UNKNOWN"
            timeframe = getattr(market_state, "timeframe", "UNKNOWN") if market_state else "UNKNOWN"
            logger.error("StrategyEngine: RE_STATE_001 — Missing or corrupted MarketState. Failing closed to WAIT posture.")
            return StrategySignal(
                signal_id=str(uuid.uuid4()),
                symbol=symbol,
                timeframe=timeframe,
                direction=PatternDirection.BULLISH,
                strategy_type=StrategyType.TREND_FOLLOWING,
                decision=StrategyDecision.WAIT,
                confidence=0.0,
                confluence_score=0.0,
                reasoning="Fail-Closed: Missing or corrupted MarketState context.",
                supporting_factors=[],
                conflicting_factors=["Missing MarketState Context"],
                detected_at=datetime.now(timezone.utc),
            )

        try:
            # 2. Run baseline context validation
            if not self._validator.is_valid_context(market_state, confluence_state):
                confluence_score = confluence_state.score.overall_score if confluence_state else 50.0
                return StrategySignal(
                    signal_id=str(uuid.uuid4()),
                    symbol=market_state.symbol,
                    timeframe=market_state.timeframe,
                    direction=PatternDirection.BULLISH,
                    strategy_type=StrategyType.TREND_FOLLOWING,
                    decision=StrategyDecision.WAIT,
                    confidence=0.0,
                    confluence_score=round(confluence_score, 2),
                    reasoning="Setup context failed baseline validation filters.",
                    supporting_factors=[],
                    conflicting_factors=["Failed Context Validation"],
                    detected_at=datetime.now(timezone.utc),
                )

            # 3. Select optimal strategy signal
            return self._selector.select_best_signal(market_state, pattern_state, confluence_state)
        except Exception as e:
            logger.error("StrategyEngine: Unexpected evaluation failure: %s. Failing closed.", e, exc_info=True)
            confluence_score = confluence_state.score.overall_score if confluence_state else 0.0
            return StrategySignal(
                signal_id=str(uuid.uuid4()),
                symbol=market_state.symbol,
                timeframe=market_state.timeframe,
                direction=PatternDirection.BULLISH,
                strategy_type=StrategyType.TREND_FOLLOWING,
                decision=StrategyDecision.WAIT,
                confidence=0.0,
                confluence_score=round(confluence_score, 2),
                reasoning=f"Fail-Closed: Strategy evaluation error: {e}",
                supporting_factors=[],
                conflicting_factors=["Strategy Evaluation Error"],
                detected_at=datetime.now(timezone.utc),
            )
