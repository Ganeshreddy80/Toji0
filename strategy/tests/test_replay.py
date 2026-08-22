"""Integration tests for deterministic replay and thread safety of the Strategy Subsystem."""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import TrendDirection, VolumeExpansionState
from market_intelligence.core.models import MarketState, TrendState, VolumeState, BOSRecord
from price_action.core.enums import PatternDirection
from confluence.core.enums import SetupGrade
from confluence.core.models import ConfluenceState, ConfluenceScore
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.state import StrategyStateStore
from strategy.core.repository import StrategyRepository
from strategy.analysis.strategy_engine import StrategyEngine
from strategy.core.orchestrator import StrategyOrchestrator


def test_strategy_deterministic_replay():
    """Verify that strategy engine evaluations are 100% deterministic and replay-safe."""
    engine = StrategyEngine()
    dt = datetime.now(timezone.utc)

    # Prepare inputs
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
        trend=TrendState(
            symbol="BTCUSDT",
            timeframe="1h",
            direction=TrendDirection.UP,
            strength=0.9,
            start_time=dt,
            end_time=dt,
        ),
        bos_history=[
            BOSRecord(
                symbol="BTCUSDT",
                timeframe="1h",
                level_breached=100.0,
                direction="UP",
                break_timestamp=dt,
                volume_at_break=1000.0,
            )
        ],
    )

    confluence_state = ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1h",
        score=ConfluenceScore(
            overall_score=85.0,
            setup_grade=SetupGrade.A,
            trend_score=80.0,
            structure_score=80.0,
            liquidity_score=80.0,
            zone_score=80.0,
            volume_score=80.0,
            regime_score=80.0,
            session_score=80.0,
            mtf_score=80.0,
            correlation_score=80.0,
            pattern_score=80.0,
            quality_score=80.0,
            conflict_penalty=0.0,
            supporting_factors=[],
            conflicting_factors=[],
        ),
        updated_at=dt,
    )

    # Evaluate multiple times and compare
    sig1 = engine.evaluate(market_state, None, confluence_state)
    sig2 = engine.evaluate(market_state, None, confluence_state)

    # Assert exactly identical outputs
    assert sig1.signal_id != sig2.signal_id  # UUIDs should be unique
    assert sig1.symbol == sig2.symbol
    assert sig1.timeframe == sig2.timeframe
    assert sig1.direction == sig2.direction
    assert sig1.strategy_type == sig2.strategy_type
    assert sig1.decision == sig2.decision
    assert sig1.confidence == sig2.confidence
    assert sig1.confluence_score == sig2.confluence_score
    assert sig1.reasoning == sig2.reasoning
    assert sig1.supporting_factors == sig2.supporting_factors
    assert sig1.conflicting_factors == sig2.conflicting_factors


def test_strategy_orchestrator_thread_safety():
    """Verify that processing updates in parallel threads is thread-safe and free from races."""
    state_store = StrategyStateStore(history_limit=1000)
    repo = StrategyRepository()
    engine = StrategyEngine()
    
    # We will construct a dummy state store wrapper that is populated
    from market_intelligence.core.state import MarketIntelligenceState
    from market_intelligence.core.models import MarketSnapshot
    
    market_store = MarketIntelligenceState()
    
    orch = StrategyOrchestrator()
    orch.initialize(
        strategy_engine=engine,
        state_store=state_store,
        repository=repo,
        market_state_store=market_store,
    )

    # Populate market state
    dt = datetime.now(timezone.utc)
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        updated_at=dt,
    )
    market_snapshot = MarketSnapshot(
        snapshot_id="ms-thread",
        symbol="BTCUSDT",
        timestamp=dt,
        states={"1h": market_state},
    )
    market_store.update_snapshot(market_snapshot)

    # Concurrently execute process_strategy
    num_threads = 10
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [
            executor.submit(orch.process_strategy, "BTCUSDT", "1h")
            for _ in range(20)
        ]
        
        # Verify no thread raises an exception
        results = [f.result() for f in futures]
        assert len(results) == 20
        for r in results:
            assert r.symbol == "BTCUSDT"
            assert r.timeframe == "1h"
            assert r.latest_signal.decision == StrategyDecision.WAIT
