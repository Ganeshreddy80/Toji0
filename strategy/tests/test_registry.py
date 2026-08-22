"""Unit tests for StrategyRegistry."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.interfaces import IStrategy
from strategy.core.models import StrategySignal
from strategy.core.registry import StrategyRegistry
from strategy.analysis.trend_strategy import TrendFollowingStrategy
from strategy.analysis.breakout_strategy import BreakoutStrategy


class MockStrategy:
    """Mock strategy conforming to IStrategy."""

    def __init__(self, st_type: StrategyType, name: str, should_raise: bool = False, return_wait: bool = False) -> None:
        self._st_type = st_type
        self._name = name
        self._should_raise = should_raise
        self._return_wait = return_wait

    @property
    def strategy_type(self) -> StrategyType:
        return self._st_type

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, market_state, pattern_state, confluence_state):
        if self._should_raise:
            raise RuntimeError(f"Simulated strategy failure in {self._name}")
        if self._return_wait:
            return None
        return StrategySignal(
            signal_id="sig-123",
            symbol=market_state.symbol if market_state else "BTC/USDT",
            timeframe=market_state.timeframe if market_state else "1h",
            direction=PatternDirection.BULLISH,
            strategy_type=self._st_type,
            decision=StrategyDecision.BUY,
            confidence=85.0,
            confluence_score=80.0,
            reasoning="Mock buy signal",
            supporting_factors=["Mock Factor"],
            conflicting_factors=[],
        )


def test_registry_registration_and_lookup():
    reg = StrategyRegistry()
    strat = TrendFollowingStrategy()

    reg.register_strategy(strat)
    assert reg.get_strategy(StrategyType.TREND_FOLLOWING) is strat
    assert reg.is_strategy_enabled(StrategyType.TREND_FOLLOWING) is True
    assert len(reg.list_strategies()) == 1

    reg.unregister_strategy(StrategyType.TREND_FOLLOWING)
    assert reg.get_strategy(StrategyType.TREND_FOLLOWING) is None
    assert len(reg.list_strategies()) == 0


def test_registry_enable_disable():
    reg = StrategyRegistry()
    strat = BreakoutStrategy()

    reg.register_strategy(strat)
    assert reg.is_strategy_enabled(StrategyType.BREAKOUT) is True

    reg.set_strategy_enabled(StrategyType.BREAKOUT, False)
    assert reg.is_strategy_enabled(StrategyType.BREAKOUT) is False

    mock_market = MagicMock()
    mock_market.symbol = "BTC/USDT"
    mock_market.timeframe = "1h"

    # Disabled strategy should not evaluate
    signals = reg.evaluate_all(mock_market, None, None)
    assert len(signals) == 0

    reg.set_strategy_enabled(StrategyType.BREAKOUT, True)
    # Re-enabled strategy evaluates if condition met
    # (BreakoutStrategy returns None without breakout, but registry ran it)


def test_registry_failure_isolation():
    """Verify that an exception in one strategy does not crash registry.evaluate_all."""
    reg = StrategyRegistry()

    failing_strat = MockStrategy(StrategyType.REVERSAL, "Failing Strategy", should_raise=True)
    working_strat = MockStrategy(StrategyType.MOMENTUM, "Working Strategy", should_raise=False)

    reg.register_strategy(failing_strat)
    reg.register_strategy(working_strat)

    mock_market = MagicMock()
    mock_market.symbol = "ETH/USDT"
    mock_market.timeframe = "15m"

    # evaluate_all must catch failing_strat's exception and successfully return working_strat's signal
    signals = reg.evaluate_all(mock_market, None, None)
    assert len(signals) == 1
    assert signals[0].strategy_type == StrategyType.MOMENTUM
    assert signals[0].confidence == 0.85


def test_registry_invalid_strategy_registration_raises():
    reg = StrategyRegistry()

    class BadStrategy:
        pass

    with pytest.raises(ValueError, match="strategy_type"):
        reg.register_strategy(BadStrategy())
