"""Unit tests for PortfolioConstructionOrchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock
from portfolio_construction.core.enums import PortfolioDecision
from portfolio_construction.core.models import PortfolioConstraintConfig
from portfolio_construction.core.orchestrator import PortfolioConstructionOrchestrator
from portfolio_construction.core.state import PortfolioConstructionStateStore
from portfolio_construction.core.repository import PortfolioConstructionRepository
from portfolio_construction.analysis.construction_engine import PortfolioConstructionEngine
from strategy.core.models import StrategySignal
from price_action.core.enums import PatternDirection
from strategy.core.enums import StrategyDecision, StrategyType


def test_orchestrator_full_coordination():
    mock_event_bus = MagicMock()
    orch = PortfolioConstructionOrchestrator()
    orch.initialize(
        engine=PortfolioConstructionEngine(),
        state_store=PortfolioConstructionStateStore(),
        repository=PortfolioConstructionRepository(),
        event_bus=mock_event_bus,
    )

    sig1 = StrategySignal(
        signal_id="sig-1", symbol="BTC/USDT", timeframe="1h", direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING, decision=StrategyDecision.BUY, confidence=0.85, confluence_score=80.0, reasoning="Buy BTC"
    )
    sig2 = StrategySignal(
        signal_id="sig-2", symbol="ETH/USDT", timeframe="1h", direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.BREAKOUT, decision=StrategyDecision.BUY, confidence=0.80, confluence_score=80.0, reasoning="Buy ETH"
    )

    config = PortfolioConstraintConfig(max_sector_exposure=0.90)
    state = orch.process_signals([sig1, sig2], config=config)

    assert state.active_portfolio.decision == PortfolioDecision.REBALANCE
    assert len(state.active_portfolio.target_weights) == 2
    assert "BTC/USDT" in state.active_portfolio.target_weights
    assert "ETH/USDT" in state.active_portfolio.target_weights

    # Check event broadcasts
    events_published = [type(c.args[0]).__name__ for c in mock_event_bus.publish.call_args_list]
    assert "PortfolioUpdated" in events_published
    assert "PortfolioGenerated" in events_published
    assert "PortfolioConstructionApproved" in events_published


def test_orchestrator_fails_closed_on_unhandled_engine_exception():
    mock_event_bus = MagicMock()
    orch = PortfolioConstructionOrchestrator()

    mock_engine = MagicMock()
    mock_engine.construct_portfolio.side_effect = RuntimeError("Critical engine failure")

    orch.initialize(
        engine=mock_engine,
        state_store=PortfolioConstructionStateStore(),
        repository=PortfolioConstructionRepository(),
        event_bus=mock_event_bus,
    )

    sig1 = StrategySignal(
        signal_id="sig-1", symbol="BTC/USDT", timeframe="1h", direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING, decision=StrategyDecision.BUY, confidence=0.85, confluence_score=80.0, reasoning="Buy BTC"
    )

    # Must NOT raise exception! Must return fail-closed state
    state = orch.process_signals([sig1])

    assert state.active_portfolio.decision == PortfolioDecision.HOLD
    assert state.active_portfolio.target_weights == {}
    assert "Fail-Closed" in state.active_portfolio.reasoning

    events_published = [type(c.args[0]).__name__ for c in mock_event_bus.publish.call_args_list]
    assert "PortfolioConstructionRejected" in events_published
