"""Unit tests for Sprint 1 Task 3: Position Sizing Pipeline Short-Circuit on RiskDecision.BLOCK."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch

from toji_platform.core.dependency_injection.container import Container
from toji_platform.core.event_bus.interfaces import IEventBus
from trading_context.core.models import TradingContext
from trading_context.core.interfaces import ITradingContextStateStore
from market_intelligence.core.models import MarketState, VolumeState
from market_intelligence.core.enums import VolumeExpansionState
from strategy.core.models import StrategyState
from risk_engine.core.events import RiskRejected
from risk_engine.core.models import RiskState, RiskAssessment, RiskViolation
from risk_engine.core.enums import RiskDecision, RiskSeverity
from position_sizing.core.enums import SizingStatus
from position_sizing.core.models import PositionSizingResult
from position_sizing.core.plugin import PositionSizingPlugin
from position_sizing.analysis.position_engine import PositionSizingEngine
from position_sizing.core.orchestrator import PositionSizingOrchestrator


@pytest.fixture
def dummy_context() -> TradingContext:
    dt = datetime.now(timezone.utc)
    volume_state = VolumeState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume_ma=100.0,
        normalized_volume=1.0,
        expansion_state=VolumeExpansionState.NORMAL,
        atr=2.5,
    )
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        volume=volume_state,
        updated_at=dt,
    )
    strategy_state = StrategyState(symbol="BTCUSDT", timeframe="1h", updated_at=dt)
    return TradingContext(
        symbol="BTCUSDT",
        timeframe="1h",
        market_state=market_state,
        strategy_state=strategy_state,
        generated_at=dt,
    )


def test_task3_engine_short_circuit_on_block(dummy_context):
    """Verify PositionSizingEngine returns immediately on RiskDecision.BLOCK without executing calculators."""
    engine = PositionSizingEngine()

    violation = RiskViolation(
        rule_id="DRAWDOWN_MAX",
        severity=RiskSeverity.CRITICAL,
        message="Maximum daily drawdown limit breached.",
    )
    risk_assessment = RiskAssessment(
        overall_score=0.0,
        decision=RiskDecision.BLOCK,
        violations=[violation],
    )

    with patch.object(engine, "_selector") as mock_selector, \
         patch.object(engine, "_leverage_calc") as mock_leverage, \
         patch.object(engine, "_margin_calc") as mock_margin, \
         patch.object(engine, "_validator") as mock_validator, \
         patch("position_sizing.analysis.position_engine.logger") as mock_logger:

        result = engine.calculate_size(
            dummy_context,
            risk_assessment,
            account_balance=100000.0,
            entry_price=100.0,
            stop_distance=5.0,
            take_profit_distance=10.0,
        )

        # 1. Assert result properties
        assert not result.success
        assert result.status == SizingStatus.REJECTED
        assert result.position_size is None

        # 2. Verify violations and reasons preserved
        assert "Maximum daily drawdown limit breached." in result.violations
        assert any("Maximum daily drawdown limit breached." in r for r in result.reasons)

        # 3. Verify downstream components were NOT invoked
        mock_selector.select_calculator.assert_not_called()
        mock_leverage.calculate_leverage.assert_not_called()
        mock_margin.calculate_margin.assert_not_called()
        mock_validator.validate.assert_not_called()

        # 4. Verify logger was invoked
        mock_logger.warning.assert_called()


def test_task3_engine_allow_executes_normal_sizing(dummy_context):
    """Verify RiskDecision.ALLOW proceeds to calculate position size normally."""
    engine = PositionSizingEngine()
    risk_assessment = RiskAssessment(overall_score=95.0, decision=RiskDecision.ALLOW)

    result = engine.calculate_size(
        dummy_context,
        risk_assessment,
        account_balance=100000.0,
        entry_price=100.0,
        stop_distance=5.0,
        take_profit_distance=10.0,
        risk_percent=0.01,
    )

    assert result.success
    assert result.status == SizingStatus.APPROVED
    assert result.position_size is not None
    assert result.position_size.quantity == 200.0


def test_task3_plugin_short_circuit_on_block_event():
    """Verify PositionSizingPlugin short-circuits on RiskDecision.BLOCK event without state/repo mutation or event emission."""
    container = Container()
    event_bus = MagicMock()
    container.register(IEventBus, instance=event_bus)

    tc_store = MagicMock()
    container.register(ITradingContextStateStore, instance=tc_store)

    mock_orchestrator = MagicMock()

    plugin = PositionSizingPlugin(
        event_bus=event_bus,
        container=container,
        orchestrator=mock_orchestrator,
    )
    plugin.initialize()

    dt = datetime.now(timezone.utc)
    violation_msg = "Account leverage hard cap exceeded."
    risk_assessment = RiskAssessment(
        overall_score=10.0,
        decision=RiskDecision.BLOCK,
        violations=[violation_msg],
    )
    risk_state = RiskState(
        symbol="BTCUSDT",
        timeframe="1h",
        assessment=risk_assessment,
        updated_at=dt,
    )

    event = RiskRejected(
        source="risk_engine.orchestrator",
        payload={
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "state": risk_state.model_dump(mode="json"),
        },
    )

    # Dispatch to plugin handler
    res = plugin._on_risk_rejected(event)

    # 1. Assert result returned by plugin early exit
    assert isinstance(res, PositionSizingResult)
    assert not res.success
    assert res.status == SizingStatus.REJECTED
    assert res.position_size is None
    assert violation_msg in res.violations
    assert any(violation_msg in r for r in res.reasons)

    # 2. Verify orchestrator was NOT called
    mock_orchestrator.process_context.assert_not_called()


def test_task3_orchestrator_short_circuit_no_state_repo_event_mutation(dummy_context):
    """Verify PositionSizingOrchestrator short-circuits on BLOCK without updating state store, writing repo, or publishing events."""
    mock_state_store = MagicMock()
    mock_repository = MagicMock()
    mock_engine = PositionSizingEngine()
    mock_event_bus = MagicMock()

    orchestrator = PositionSizingOrchestrator()
    orchestrator.initialize(
        state_store=mock_state_store,
        repository=mock_repository,
        sizing_engine=mock_engine,
        event_bus=mock_event_bus,
    )

    risk_assessment = RiskAssessment(
        overall_score=0.0,
        decision=RiskDecision.BLOCK,
        violations=["Portfolio risk threshold exceeded."],
    )

    state = orchestrator.process_context(dummy_context, risk_assessment)

    # Assert returned state contains rejected result
    assert not state.result.success
    assert state.result.status == SizingStatus.REJECTED
    assert "Portfolio risk threshold exceeded." in state.result.violations

    # Assert NO state store update, repo write, or event dispatch occurred
    mock_state_store.update_timeframe_state.assert_not_called()
    mock_repository.save_snapshot.assert_not_called()
    mock_event_bus.publish.assert_not_called()
