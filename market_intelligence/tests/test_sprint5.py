"""Unit and integration tests for Phase 12B — Sprint 5."""

from __future__ import annotations

import concurrent.futures
import time
import uuid
from datetime import datetime, timezone, timedelta
import pytest

from data.schemas.market_data import OHLCV
from market_intelligence.core.analysis.engine import CoreAnalysisEngine
from market_intelligence.core.analysis.confidence import ConfidenceEngine
from market_intelligence.core.analysis.story import StoryGenerator
from market_intelligence.core.orchestrator import MarketIntelligenceOrchestrator
from market_intelligence.core.replay import ReplayVerifier, hash_state
from market_intelligence.core.health import HealthMonitor
from market_intelligence.core.performance import PerformanceMonitor
from market_intelligence.core.repository import MarketIntelligenceRepository
from market_intelligence.core.state import MarketIntelligenceState
from market_intelligence.core.plugin import MarketIntelligencePlugin
from market_intelligence.core.enums import HealthState, ReplayStatus, SessionName, TrendDirection, MarketRegime
from market_intelligence.core.models import (
    MarketSnapshot,
    MarketState,
    ReplayReport,
    PerformanceReport,
    HealthReport,
)
from market_intelligence.core.exceptions import OrchestratorError
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.dependency_injection import Container
from toji_platform.core.types import HealthStatus


def make_candle(
    idx: int,
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    vol: float = 100.0,
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    hour_override: int | None = None,
) -> OHLCV:
    """Helper to generate deterministic OHLCV candles."""
    dt = datetime(2026, 6, 26, 10, 0, tzinfo=timezone.utc) + timedelta(hours=idx)
    if hour_override is not None:
        dt = dt.replace(hour=hour_override)
    return OHLCV(
        symbol=symbol,
        timestamp=dt,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=vol,
        interval=interval,
    )


# ─── CONFIDENCE ENGINE TESTS ─────────────────────────────────────────────────

def test_confidence_engine_scoring_weights():
    """Verify confidence score calculations, factor values, and weight normalization."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)
    
    # Check default weights initialization
    conf_engine = ConfidenceEngine(event_bus=bus)
    assert abs(sum(conf_engine._weights.values()) - 1.0) < 1e-9

    # Generate a single candle to produce context and state
    candle = make_candle(0, 100.0, 105.0, 95.0, 102.0)
    state = engine.analyze_candle(candle)

    # Evaluate
    conf_state = conf_engine.calculate(state, state.market_context, candle.timestamp)
    
    assert conf_state.symbol == "BTCUSDT"
    assert conf_state.timeframe == "1h"
    assert 0.0 <= conf_state.score <= 1.0
    assert len(conf_state.contribution_breakdown) == 12
    assert abs(sum(conf_state.contribution_breakdown.values()) - conf_state.score) < 1e-9


def test_confidence_engine_regime_impact():
    """Verify that volatile regime reductions and strong trends affect confidence scores appropriately."""
    bus = InMemoryEventBus()
    
    conf_engine = ConfidenceEngine(event_bus=bus)

    # Generate a single candle to produce context and state
    engine = CoreAnalysisEngine(event_bus=bus, k=2)
    candle = make_candle(0, 100.0, 105.0, 95.0, 102.0)
    state = engine.analyze_candle(candle)

    # 1. Volatile regime test (mocked context)
    mock_context_volatile = state.market_context.model_copy(update={"regime": MarketRegime.VOLATILE})
    mock_state_volatile = state.model_copy(update={"market_context": mock_context_volatile})
    conf_state_volatile = conf_engine.calculate(mock_state_volatile, mock_context_volatile, candle.timestamp)
    assert conf_state_volatile.factors["regime_weight"] == 0.3

    # 2. Trending regime test (mocked context)
    mock_context_trending = state.market_context.model_copy(update={"regime": MarketRegime.TRENDING})
    mock_state_trending = state.model_copy(update={"market_context": mock_context_trending})
    conf_state_trending = conf_engine.calculate(mock_state_trending, mock_context_trending, candle.timestamp)
    assert conf_state_trending.factors["regime_weight"] == 1.0


# ─── STORY GENERATOR TESTS ───────────────────────────────────────────────────

def test_story_generator_sections_and_no_recommendations():
    """Verify that the Story Generator produces all 9 sections and contains zero trading advice/recommendations."""
    bus = InMemoryEventBus()
    engine = CoreAnalysisEngine(event_bus=bus, k=2)
    conf_engine = ConfidenceEngine(event_bus=bus)
    story_gen = StoryGenerator(event_bus=bus)

    candle = make_candle(0, 100.0, 105.0, 95.0, 102.0)
    state = engine.analyze_candle(candle)
    conf_state = conf_engine.calculate(state, state.market_context, candle.timestamp)

    story_state = story_gen.generate(state, state.market_context, conf_state, candle.timestamp)

    # 9 sections must exist
    assert len(story_state.sections) == 9
    expected_sections = [
        "Current Trend", "Current Structure", "Liquidity", "Important Zones",
        "Volume Context", "Market Regime", "Higher Timeframe Context",
        "Correlation Summary", "Overall Confidence"
    ]
    for section in expected_sections:
        assert section in story_state.sections
        assert len(story_state.sections[section]) > 0

    # Narrative must contain markdown formatting and all section headers
    for section in expected_sections:
        assert f"## {section}" in story_state.narrative

    # Adversarial audit: Ensure no recommendations / buy / sell words are present in advisory context
    assert "should buy" not in story_state.narrative.lower()
    assert "should sell" not in story_state.narrative.lower()
    assert "buy now" not in story_state.narrative.lower()
    assert "sell now" not in story_state.narrative.lower()
    assert "recommend" not in story_state.narrative.lower()
    assert len(story_state.supporting_events) > 0


# ─── HEALTH MONITOR TESTS ─────────────────────────────────────────────────────

def test_health_monitor_aggregation():
    """Verify HealthMonitor aggregates statuses correctly across healthy, degraded, and failed transitions."""
    bus = InMemoryEventBus()
    monitor = HealthMonitor(bus)

    # Start healthy
    report = monitor.get_report()
    assert report.overall_status == HealthState.HEALTHY

    # Transition one engine to degraded
    monitor.set_engine_status("confidence_engine", HealthState.DEGRADED)
    report = monitor.get_report()
    assert report.overall_status == HealthState.DEGRADED

    # Transition an engine to failed
    monitor.set_engine_status("core_analysis_engine", HealthState.FAILED)
    report = monitor.get_report()
    assert report.overall_status == HealthState.FAILED

    # Add dependency failure
    monitor.set_engine_status("core_analysis_engine", HealthState.HEALTHY)
    monitor.set_engine_status("confidence_engine", HealthState.HEALTHY)
    monitor.add_dependency_failure("repository")
    report = monitor.get_report()
    assert report.overall_status == HealthState.FAILED


# ─── PERFORMANCE MONITOR TESTS ─────────────────────────────────────────────────

def test_performance_monitor():
    """Verify that PerformanceMonitor accurately measures latency metrics and throughput."""
    monitor = PerformanceMonitor(track_memory=True)

    monitor.record_candle_processed(2.5)
    monitor.record_candle_processed(4.5)
    monitor.record_candle_processed(8.0)
    monitor.record_event_published()
    monitor.record_event_published()

    report = monitor.get_report("BTCUSDT")
    assert report.total_candles == 3
    assert report.symbol == "BTCUSDT"
    assert report.mean_latency_ms == pytest.approx(5.0)
    assert report.p99_latency_ms == pytest.approx(8.0)
    assert report.events_per_sec > 0.0
    assert report.memory_usage_mb >= 0.0


# ─── ORCHESTRATOR & REPLAY TESTS ───────────────────────────────────────────────

def test_orchestrator_streaming_and_replay():
    """Verify streaming candle processing, health reporting, and replay verification in the Orchestrator."""
    bus = InMemoryEventBus()
    state_store = MarketIntelligenceState()
    repo = MarketIntelligenceRepository()
    engine = CoreAnalysisEngine(event_bus=bus, k=2, state_store=state_store)
    conf_engine = ConfidenceEngine(event_bus=bus)
    story_gen = StoryGenerator(event_bus=bus)

    orchestrator = MarketIntelligenceOrchestrator(
        engine=engine,
        confidence_engine=conf_engine,
        story_generator=story_gen,
        event_bus=bus,
        state_store=state_store,
        repository=repo,
    )

    # 1. Process streaming candle
    candle = make_candle(0, 100.0, 105.0, 95.0, 102.0)
    state = orchestrator.process_candle(candle)

    assert state.confidence is not None
    assert state.story is not None
    assert state.confidence.score > 0.0
    assert len(state.story.sections) == 9

    # Verify state was saved to state store & repository
    snapshot = state_store.get_snapshot("BTCUSDT")
    assert snapshot is not None
    assert snapshot.states["1h"].confidence is not None

    latest_repo_snapshot = repo.load_latest_snapshot("BTCUSDT")
    assert latest_repo_snapshot is not None

    # 2. Replay Verification
    candles = [
        make_candle(0, 100.0, 105.0, 95.0, 102.0),
        make_candle(1, 102.0, 110.0, 99.0, 108.0),
        make_candle(2, 108.0, 112.0, 105.0, 107.0),
    ]

    # Clean run for live simulation
    orchestrator.restart()
    live_states = []
    for c in candles:
        live_states.append(orchestrator.process_candle(c))

    # Replay verifier
    verifier = ReplayVerifier(bus)
    report = verifier.verify(orchestrator, candles, live_states)

    assert report.matched is True
    assert report.status == ReplayStatus.PASSED
    assert report.total_candles == 3
    assert report.divergence_at is None


def test_replay_verifier_divergence_detection():
    """Verify that ReplayVerifier detects state mismatches (divergence) correctly."""
    bus = InMemoryEventBus()
    state_store = MarketIntelligenceState()
    repo = MarketIntelligenceRepository()
    engine = CoreAnalysisEngine(event_bus=bus, k=2, state_store=state_store)
    conf_engine = ConfidenceEngine(event_bus=bus)
    story_gen = StoryGenerator(event_bus=bus)

    orchestrator = MarketIntelligenceOrchestrator(
        engine=engine,
        confidence_engine=conf_engine,
        story_generator=story_gen,
        event_bus=bus,
        state_store=state_store,
        repository=repo,
    )

    candles = [
        make_candle(0, 100.0, 105.0, 95.0, 102.0),
        make_candle(1, 102.0, 110.0, 99.0, 108.0),
    ]

    # Process live simulation
    live_states = []
    for c in candles:
        live_states.append(orchestrator.process_candle(c))

    # Create a slightly different state list to trigger divergence
    modified_live_states = list(live_states)
    modified_live_states[1] = live_states[1].model_copy(
        update={"market_phase_state": "DIVERGENT_PHASE"}
    )

    verifier = ReplayVerifier(bus)
    report = verifier.verify(orchestrator, candles, modified_live_states)

    assert report.matched is False
    assert report.status == ReplayStatus.FAILED
    assert report.divergence_at == 1


# ─── REPOSITORY REPORTS PERSISTENCE TESTS ─────────────────────────────────────

def test_repository_reports_persistence():
    """Verify saving and loading Replay, Performance, and Health reports in the Repository."""
    repo = MarketIntelligenceRepository()

    # Replay report
    rep_report = ReplayReport(
        report_id=str(uuid.uuid4()),
        symbol="BTCUSDT",
        total_candles=10,
        hash_live="livehash",
        hash_replay="replayhash",
        matched=True,
        divergence_at=None,
        status=ReplayStatus.PASSED,
        duration_ms=15.0,
        timestamp=datetime.now(timezone.utc),
    )
    repo.save_replay_report(rep_report)
    loaded_rep = repo.load_latest_replay_report("BTCUSDT")
    assert loaded_rep is not None
    assert loaded_rep.report_id == rep_report.report_id
    assert loaded_rep.status == ReplayStatus.PASSED

    # Performance report
    perf_report = PerformanceReport(
        report_id=str(uuid.uuid4()),
        symbol="BTCUSDT",
        mean_latency_ms=1.5,
        p99_latency_ms=3.0,
        events_per_sec=100.0,
        memory_usage_mb=10.0,
        total_candles=100,
        timestamp=datetime.now(timezone.utc),
    )
    repo.save_performance_report(perf_report)
    loaded_perf = repo.load_latest_performance_report("BTCUSDT")
    assert loaded_perf is not None
    assert loaded_perf.report_id == perf_report.report_id
    assert loaded_perf.mean_latency_ms == pytest.approx(1.5)

    # Health report
    health_report = HealthReport(
        engine_statuses={"core_analysis_engine": HealthState.HEALTHY},
        dependency_failures=[],
        last_update=datetime.now(timezone.utc),
        processing_latency_ms=2.0,
        replay_status=ReplayStatus.PASSED,
        overall_status=HealthState.HEALTHY,
        timestamp=datetime.now(timezone.utc),
    )
    repo.save_health_report(health_report)
    assert repo._latest_health_report.overall_status == HealthState.HEALTHY


# ─── THREAD SAFETY TESTS ──────────────────────────────────────────────────────

def test_orchestrator_thread_safety():
    """Verify concurrent candle processing through the orchestrator under thread contention."""
    bus = InMemoryEventBus()
    state_store = MarketIntelligenceState()
    repo = MarketIntelligenceRepository()
    engine = CoreAnalysisEngine(event_bus=bus, k=2, state_store=state_store)
    conf_engine = ConfidenceEngine(event_bus=bus)
    story_gen = StoryGenerator(event_bus=bus)

    orchestrator = MarketIntelligenceOrchestrator(
        engine=engine,
        confidence_engine=conf_engine,
        story_generator=story_gen,
        event_bus=bus,
        state_store=state_store,
        repository=repo,
    )

    candles = [make_candle(i, 100.0, 105.0, 95.0, 100.0 + i, symbol=f"SYM_{i}") for i in range(10)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(orchestrator.process_candle, c) for c in candles]
        results = [f.result() for f in futures]

    assert len(results) == 10
    for idx, state in enumerate(results):
        assert state is not None
        assert state.confidence is not None
        assert state.story is not None


# ─── PLUGIN LIFE CYCLE INTEGRATION ───────────────────────────────────────────

def test_plugin_lifecycle_wiring():
    """Verify the entire plugin registration, lifecycle, and event bus wiring."""
    container = Container()
    bus = InMemoryEventBus()
    container.register(InMemoryEventBus, instance=bus)
    # The DI container has resolve mapped to type names or specific interface strings
    from toji_platform.core.event_bus.interfaces import IEventBus
    container.register(IEventBus, instance=bus)

    plugin = MarketIntelligencePlugin(container=container, event_bus=bus)
    plugin.initialize()

    # Verify Sprint 5 DI registration
    assert container.has(MarketIntelligenceOrchestrator)
    assert container.has(HealthMonitor)
    assert container.has(PerformanceMonitor)
    assert container.has(ReplayVerifier)

    # Resolve from container and assert health
    orch = container.resolve(MarketIntelligenceOrchestrator)
    assert orch is not None
    assert plugin.health_check() == HealthStatus.HEALTHY

    plugin.shutdown()


# ─── SPRINT 5 NEW SUB-ENGINES TESTS ──────────────────────────────────────────

def test_volatility_engine():
    """Verify ATR, historical/realized volatility, Bollinger width and Daily Range."""
    from market_intelligence.core.analysis.volatility import VolatilityEngine
    from market_intelligence.core.models import VolatilityAnalysis
    
    engine = VolatilityEngine(event_bus=None, window=5)
    
    # Send 6 candles (rising prices)
    for i in range(6):
        candle = make_candle(i, 100.0 + i, 105.0 + i, 95.0 + i, 102.0 + i)
        analysis = engine.calculate_volatility(candle)
        assert isinstance(analysis, VolatilityAnalysis)
        assert analysis.symbol == "BTCUSDT"
        assert analysis.atr > 0
        assert analysis.daily_range == 10.0
        if i >= 2:
            assert analysis.realized_volatility >= 0.0
            assert analysis.bollinger_width >= 0.0


def test_order_flow_engine():
    """Verify trade delta, buy/sell volume split, and imbalance."""
    from market_intelligence.core.analysis.order_flow import OrderFlowEngine
    from market_intelligence.core.models import OrderFlowAnalysis
    
    engine = OrderFlowEngine(event_bus=None)
    
    # 1. Close in middle
    candle = make_candle(0, 100.0, 110.0, 90.0, 100.0, vol=1000.0)
    analysis = engine.calculate_order_flow(candle)
    assert isinstance(analysis, OrderFlowAnalysis)
    assert abs(analysis.buy_volume - 500.0) < 1e-5
    assert abs(analysis.sell_volume - 500.0) < 1e-5
    assert abs(analysis.trade_delta) < 1e-5
    assert abs(analysis.order_imbalance) < 1e-5

    # 2. Close at high
    candle2 = make_candle(1, 100.0, 110.0, 90.0, 110.0, vol=1000.0)
    analysis2 = engine.calculate_order_flow(candle2)
    assert analysis2.buy_volume == 1000.0
    assert analysis2.sell_volume == 0.0
    assert analysis2.trade_delta == 1000.0
    assert analysis2.order_imbalance == 1.0


def test_volume_profile_engine():
    """Verify Point of Control (POC), VAH, VAL calculation."""
    from market_intelligence.core.analysis.volume_profile import VolumeProfileEngine
    from market_intelligence.core.models import VolumeProfileAnalysis
    
    engine = VolumeProfileEngine(event_bus=None, window=10)
    
    # Send candles at different prices
    for i in range(10):
        # 5 candles at 100, 5 candles at 150
        price = 100.0 if i < 5 else 150.0
        candle = make_candle(i, price, price + 5.0, price - 5.0, price, vol=100.0)
        analysis = engine.calculate_volume_profile(candle)
        
    assert isinstance(analysis, VolumeProfileAnalysis)
    assert analysis.poc in (98.0, 152.0) # center of one of the bins
    assert analysis.val < analysis.vah


def test_market_sub_endpoints():
    """Verify the 9 new GET sub-endpoints in dashboard router."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from dashboard.api.router import create_api_router
    from dashboard.core.state import DashboardStateStore
    from dashboard.core.models import DashboardSnapshot

    state_store = DashboardStateStore()
    mock_snap = DashboardSnapshot(
        snapshot_id="test_id",
        symbol="BTCUSDT",
        timeframe="1h",
        market_state={
            "regime_analysis": {"regime": "TRENDING", "confidence": 0.8},
            "trend_analysis": {"direction": "UP", "strength": 0.9},
            "volatility_analysis": {"atr": 10.5},
            "liquidity_analysis": {"liquidity_score": 95.0},
            "order_flow_analysis": {"trade_delta": 1000.0},
            "volume_profile_analysis": {"poc": 100.0},
            "correlation_analysis": {"correlations": {"ETH": 0.8}},
            "market_confidence": {"confidence_score": 85.0},
            "market_intelligence": {"symbol": "BTCUSDT", "timeframe": "1h"}
        }
    )
    state_store.update_snapshot(mock_snap)
    
    app = FastAPI()
    router = create_api_router(state_store, None, None, None, None)
    app.include_router(router)
    client = TestClient(app)
    
    # 1. regime
    res = client.get("/market/regime")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["regime"]["regime"] == "TRENDING"
    
    # 2. trend
    res = client.get("/market/trend")
    assert res.status_code == 200
    assert res.json()[0]["trend"]["direction"] == "UP"

    # 3. volatility
    res = client.get("/market/volatility")
    assert res.status_code == 200
    assert res.json()[0]["volatility"]["atr"] == 10.5

    # 4. liquidity
    res = client.get("/market/liquidity")
    assert res.status_code == 200
    assert res.json()[0]["liquidity"]["liquidity_score"] == 95.0

    # 5. orderflow
    res = client.get("/market/orderflow")
    assert res.status_code == 200
    assert res.json()[0]["orderflow"]["trade_delta"] == 1000.0

    # 6. volume_profile
    res = client.get("/market/volume_profile")
    assert res.status_code == 200
    assert res.json()[0]["volume_profile"]["poc"] == 100.0

    # 7. correlation
    res = client.get("/market/correlation")
    assert res.status_code == 200
    assert res.json()[0]["correlation"]["correlations"]["ETH"] == 0.8

    # 8. confidence
    res = client.get("/market/confidence")
    assert res.status_code == 200
    assert res.json()[0]["confidence"]["confidence_score"] == 85.0

    # 9. intelligence
    res = client.get("/market/intelligence")
    assert res.status_code == 200
    assert res.json()[0]["intelligence"]["symbol"] == "BTCUSDT"

