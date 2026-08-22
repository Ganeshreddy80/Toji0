"""Unit and integration tests for Sprint 3.1 Strategy Engine Hardening."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from strategy.core.enums import SignalLifecycleState, StrategyDecision, StrategyType
from strategy.core.interfaces import ISignalScorer
from strategy.core.models import StrategySignal, StrategyState, StrategySnapshot
from strategy.core.orchestrator import StrategyOrchestrator
from strategy.core.state import StrategyStateStore
from strategy.core.registry import StrategyRegistry
from strategy.core.repository import StrategyRepository
from strategy.analysis.strategy_engine import StrategyEngine
from strategy.analysis.strategy_selector import StrategySelector
from strategy.analysis.signal_scorer import CompositeSignalScorer


# ===========================================================================
# 1. Confidence Normalization (0.0 - 1.0)
# ===========================================================================

def test_confidence_normalization_auto_converts_percentage():
    """Verify that a confidence score > 1.0 (e.g. 85.0) is auto-normalized to [0.0, 1.0]."""
    sig = StrategySignal(
        signal_id="sig-norm-1",
        symbol="BTC/USDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=85.0,  # Percentage format
        confluence_score=80.0,
        reasoning="Test normalization",
    )
    assert sig.confidence == 0.85
    assert 0.0 <= sig.confidence <= 1.0


def test_confidence_normalization_preserves_normalized_value():
    """Verify that a pre-normalized confidence score (e.g. 0.85) remains 0.85."""
    sig = StrategySignal(
        signal_id="sig-norm-2",
        symbol="ETH/USDT",
        timeframe="15m",
        direction=PatternDirection.BEARISH,
        strategy_type=StrategyType.BREAKOUT,
        decision=StrategyDecision.SELL,
        confidence=0.85,
        confluence_score=75.0,
        reasoning="Pre-normalized confidence",
    )
    assert sig.confidence == 0.85


# ===========================================================================
# 2. Configurable Minimum Confidence Threshold
# ===========================================================================

def test_configurable_min_confidence_threshold():
    """Verify that StrategySelector filters signals below min_confidence threshold via StrategyRegistry."""
    mock_market = MagicMock()
    mock_market.symbol = "SOL/USDT"
    mock_market.timeframe = "1h"
    mock_market.trend = None

    # Strategy returns a signal with confidence 0.50
    low_conf_signal = StrategySignal(
        signal_id="sig-low",
        symbol="SOL/USDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.RANGE,
        decision=StrategyDecision.BUY,
        confidence=0.50,
        confluence_score=60.0,
        reasoning="Low confidence signal",
    )

    mock_strategy = MagicMock()
    mock_strategy.strategy_type = StrategyType.RANGE
    mock_strategy.name = "LowConfStrategy"
    mock_strategy.evaluate.return_value = low_conf_signal

    registry = StrategyRegistry()
    registry.register_strategy(mock_strategy)

    # Selector configured with min_confidence = 0.65
    selector = StrategySelector(registry=registry, min_confidence=0.65)
    selected = selector.select_best_signal(mock_market, None, None)

    # Low confidence signal must be rejected -> fallback to WAIT posture
    assert selected.decision == StrategyDecision.WAIT
    assert selected.confidence == 0.0


# ===========================================================================
# 3. Complete StrategySignal Metadata
# ===========================================================================

def test_strategy_signal_metadata_fields():
    """Verify all required metadata fields are populated on StrategySignal."""
    now = datetime.now(timezone.utc)
    sig = StrategySignal(
        signal_id="sig-meta-100",
        strategy_id="strat_trend_v1",
        strategy_version="1.2.0",
        symbol="BTC/USDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=0.92,
        confluence_score=88.0,
        market_regime="TRENDING_UP",
        reasoning="Metadata test signal",
        lifecycle_state=SignalLifecycleState.NEW,
        generated_at=now,
    )
    assert sig.strategy_id == "strat_trend_v1"
    assert sig.strategy_version == "1.2.0"
    assert sig.strategy_type == StrategyType.TREND_FOLLOWING
    assert sig.generated_at == now
    assert sig.market_regime == "TRENDING_UP"
    assert sig.reasoning == "Metadata test signal"
    assert sig.lifecycle_state == SignalLifecycleState.NEW


# ===========================================================================
# 4 & 5. Duplicate Signal Suppression & Signal Lifecycle States
# ===========================================================================

def test_duplicate_signal_suppression_and_lifecycle_transitions():
    """
    Verify lifecycle transitions:
    - 1st trigger: NEW (StrategySignalEvent published)
    - 2nd identical tick: ACTIVE (StrategySignalEvent SUPPRESSED)
    - 3rd update with confidence change: UPDATED (StrategySignalEvent published)
    - Drop to WAIT: EXPIRED
    """
    mock_event_bus = MagicMock()
    orch = StrategyOrchestrator()
    state_store = StrategyStateStore()
    repository = StrategyRepository()

    mock_engine = MagicMock()
    mock_market_store = MagicMock()

    mock_market = MagicMock()
    mock_market.symbol = "BTC/USDT"
    mock_market.timeframe = "1h"
    mock_market_snap = MagicMock()
    mock_market_snap.states = {"1h": mock_market}
    mock_market_store.get_snapshot.return_value = mock_market_snap

    orch.initialize(
        strategy_engine=mock_engine,
        state_store=state_store,
        repository=repository,
        event_bus=mock_event_bus,
        market_state_store=mock_market_store,
    )

    # 1. First evaluation yields BUY signal (confidence = 0.85)
    sig1 = StrategySignal(
        signal_id="sig-1",
        symbol="BTC/USDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=0.85,
        confluence_score=80.0,
        reasoning="First buy trigger",
    )
    mock_engine.evaluate.return_value = sig1

    state1 = orch.process_strategy("BTC/USDT", "1h")
    assert state1.latest_signal.lifecycle_state == SignalLifecycleState.NEW
    pub1 = [type(c.args[0]).__name__ for c in mock_event_bus.publish.call_args_list]
    assert "StrategySignalEvent" in pub1

    # 2. Second evaluation yields identical BUY signal (confidence = 0.85) -> ACTIVE (duplicate suppressed)
    mock_event_bus.reset_mock()
    sig2 = StrategySignal(
        signal_id="sig-2",
        symbol="BTC/USDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=0.85,
        confluence_score=80.0,
        reasoning="Duplicate buy trigger",
    )
    mock_engine.evaluate.return_value = sig2

    state2 = orch.process_strategy("BTC/USDT", "1h")
    assert state2.latest_signal.lifecycle_state == SignalLifecycleState.ACTIVE
    pub2 = [type(c.args[0]).__name__ for c in mock_event_bus.publish.call_args_list]
    # StrategySignalEvent MUST be suppressed for ACTIVE duplicate!
    assert "StrategySignalEvent" not in pub2
    assert "StrategyUpdated" in pub2

    # 3. Third evaluation yields material confidence change (0.85 -> 0.95) -> UPDATED
    mock_event_bus.reset_mock()
    sig3 = StrategySignal(
        signal_id="sig-3",
        symbol="BTC/USDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=0.95,
        confluence_score=80.0,
        reasoning="Updated buy trigger",
    )
    mock_engine.evaluate.return_value = sig3

    state3 = orch.process_strategy("BTC/USDT", "1h")
    assert state3.latest_signal.lifecycle_state == SignalLifecycleState.UPDATED
    pub3 = [type(c.args[0]).__name__ for c in mock_event_bus.publish.call_args_list]
    assert "StrategySignalEvent" in pub3


# ===========================================================================
# 6. Extensible Scoring Interface (ISignalScorer)
# ===========================================================================

def test_extensible_signal_scorer():
    """Verify CompositeSignalScorer calculates composite rank score weighting regime alignment."""
    scorer = CompositeSignalScorer()

    mock_market = MagicMock()
    mock_market.symbol = "BTC/USDT"
    mock_market.timeframe = "1h"
    mock_market.trend = MagicMock()
    mock_market.trend.direction.value = "UP"

    sig_aligned = StrategySignal(
        signal_id="sig-aligned",
        symbol="BTC/USDT",
        timeframe="1h",
        direction=PatternDirection.BULLISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.BUY,
        confidence=0.80,
        confluence_score=80.0,
        reasoning="Aligned signal",
    )

    sig_counter = StrategySignal(
        signal_id="sig-counter",
        symbol="BTC/USDT",
        timeframe="1h",
        direction=PatternDirection.BEARISH,
        strategy_type=StrategyType.REVERSAL,
        decision=StrategyDecision.SELL,
        confidence=0.80,
        confluence_score=80.0,
        reasoning="Counter-trend signal",
    )

    score_aligned = scorer.score_signal(sig_aligned, mock_market)
    score_counter = scorer.score_signal(sig_counter, mock_market)

    # Aligned signal gets regime bonus -> higher composite score
    assert score_aligned > score_counter


# ===========================================================================
# 7. Engine Exception Fail-Closed Handling (Sprint 3.2 P1 Regression Test)
# ===========================================================================

def test_orchestrator_engine_crash_fails_closed_without_raising():
    """
    Verify Sprint 3.2 P1 fix:
    Engine crash -> WAIT persisted -> StrategyUpdated published -> StrategyGenerated published -> No StrategySignalEvent -> No exception escapes.
    """
    mock_event_bus = MagicMock()
    orch = StrategyOrchestrator()
    state_store = StrategyStateStore()
    repository = StrategyRepository()

    # Engine that raises an unhandled exception during evaluation
    mock_engine = MagicMock()
    mock_engine.evaluate.side_effect = RuntimeError("Simulated StrategyEngine crash during evaluation")

    mock_market_store = MagicMock()
    mock_market = MagicMock()
    mock_market.symbol = "BTC/USDT"
    mock_market.timeframe = "1h"
    mock_market_snap = MagicMock()
    mock_market_snap.states = {"1h": mock_market}
    mock_market_store.get_snapshot.return_value = mock_market_snap

    orch.initialize(
        strategy_engine=mock_engine,
        state_store=state_store,
        repository=repository,
        event_bus=mock_event_bus,
        market_state_store=mock_market_store,
    )

    # 1. No exception must escape process_strategy
    try:
        returned_state = orch.process_strategy("BTC/USDT", "1h")
    except Exception as exc:
        pytest.fail(f"Orchestrator allowed exception to escape runtime evaluation: {exc}")

    # 2. WAIT state returned and persisted
    assert returned_state.latest_signal is not None
    assert returned_state.latest_signal.decision == StrategyDecision.WAIT
    assert returned_state.latest_signal.confidence == 0.0
    assert "Fail-Closed" in returned_state.latest_signal.reasoning

    # Verify persisted state in state_store and repository
    persisted_snap = state_store.get_snapshot("BTC/USDT")
    assert persisted_snap is not None
    assert persisted_snap.states["1h"].latest_signal.decision == StrategyDecision.WAIT

    latest_repo_snap = repository.load_latest_snapshot("BTC/USDT")
    assert latest_repo_snap is not None
    assert latest_repo_snap.states["1h"].latest_signal.decision == StrategyDecision.WAIT

    # 3. Verify event publications
    pub_events = [type(c.args[0]).__name__ for c in mock_event_bus.publish.call_args_list]
    assert "StrategyUpdated" in pub_events
    assert "StrategyGenerated" in pub_events
    assert "StrategySignalEvent" not in pub_events

