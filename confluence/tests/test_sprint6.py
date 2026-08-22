"""Comprehensive unit and integration tests for TOJI Sprint 6 — Confluence Engine Pro."""

from __future__ import annotations

import collections
import threading
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from market_intelligence.core.enums import TrendDirection, MarketRegime as MarketRegimeEnum, VolumeExpansionState
from market_intelligence.core.models import (
    MarketState,
    TrendState,
    TrendAnalysis,
    MarketRegime,
    VolatilityAnalysis,
    LiquidityAnalysis,
    OrderFlowAnalysis,
    VolumeProfileAnalysis,
    CorrelationAnalysis,
    MarketConfidence,
    MarketIntelligence,
    VolumeState,
)
from price_action.core.enums import PatternDirection
from price_action.core.models import PatternState, PatternMatch

from confluence.core.enums import SetupGrade, RiskFlagType
from confluence.core.models import (
    SupportingFactor,
    ConflictingFactor,
    RiskFlag,
    OpportunityScore,
    TradeExplanation,
    ConfluenceScore,
    ConfluenceState,
    ConfluenceSnapshot,
)
from confluence.core.interfaces import IConfluenceStateStore, IConfluenceRepository, IConfluenceEngine
from confluence.analysis.grade_engine import GradeEngine
from confluence.analysis.opportunity_engine import OpportunityEngine
from confluence.analysis.risk_flag_engine import RiskFlagEngine
from confluence.analysis.explanation_engine import ExplanationEngine
from confluence.analysis.confluence_engine import ConfluenceEngine
from confluence.core.orchestrator import ConfluenceOrchestrator
from confluence.core.state import ConfluenceStateStore
from confluence.core.repository import ConfluenceRepository

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus as EventBus, BaseEvent
from toji_platform.core.event_bus.interfaces import IEventBus

# Dashboard API testing imports
from dashboard.core.models import DashboardSnapshot
from dashboard.core.state import DashboardStateStore
from dashboard.core.repository import DashboardRepository
from dashboard.health.health_monitor import HealthMonitor
from dashboard.websocket.websocket_manager import WebSocketManager
from dashboard.aggregator.event_aggregator import DashboardEventAggregator
from dashboard.backend.app import create_app


@pytest.fixture
def mock_market_state() -> MarketState:
    """Provide a complete mock MarketState with all necessary sub-components."""
    dt = datetime.now(timezone.utc)
    
    vol_analysis = VolatilityAnalysis(
        symbol="BTCUSDT",
        timeframe="1h",
        atr=2.5,
        historical_volatility=0.15,
        realized_volatility=0.18,
        bollinger_width=0.08,
        volatility_percentile=55.0,
        daily_range=500.0,
        timestamp=dt,
    )
    
    liq_analysis = LiquidityAnalysis(
        symbol="BTCUSDT",
        timeframe="1h",
        bid_ask_spread=0.02,
        depth=1000.0,
        market_impact_estimate=0.001,
        slippage_estimate=0.0005,
        volume_score=85.0,
        liquidity_score=90.0,
        buy_side_pools=[9900.0, 9800.0],
        sell_side_pools=[10100.0, 10200.0],
        swept_levels=[],
        timestamp=dt,
    )
    
    of_analysis = OrderFlowAnalysis(
        symbol="BTCUSDT",
        timeframe="1h",
        trade_delta=150.0,
        buy_volume=500.0,
        sell_volume=350.0,
        large_trades=5,
        aggressive_buyers=300.0,
        aggressive_sellers=200.0,
        order_imbalance=0.15,
        timestamp=dt,
    )
    
    vp_analysis = VolumeProfileAnalysis(
        symbol="BTCUSDT",
        timeframe="1h",
        poc=10000.0,
        vah=10200.0,
        val=9800.0,
        high_volume_nodes=[10000.0, 9900.0],
        low_volume_nodes=[10100.0],
        acceptance_zones=[(9800.0, 10200.0)],
        rejection_zones=[(9700.0, 9800.0)],
        timestamp=dt,
    )
    
    corr_analysis = CorrelationAnalysis(
        symbol="BTCUSDT",
        timeframe="1h",
        correlations={"ETHUSDT": 0.75, "SOLUSDT": 0.45},
        matrix={},
        timestamp=dt,
    )
    
    conf = MarketConfidence(
        symbol="BTCUSDT",
        timeframe="1h",
        confidence_score=80.0,
        risk_score=20.0,
        opportunity_score=85.0,
        market_health="Healthy",
        timestamp=dt,
    )
    
    regime_model = MarketRegime(
        symbol="BTCUSDT",
        timeframe="1h",
        regime=MarketRegimeEnum.TRENDING,
        confidence=0.9,
        trend_strength=0.85,
        volatility_level=0.18,
        timestamp=dt,
    )

    trend_analysis = TrendAnalysis(
        symbol="BTCUSDT",
        timeframe="1h",
        direction=TrendDirection.UP,
        strength=0.85,
        duration_bars=10,
        slope=0.5,
        acceleration=0.01,
        ema20=10000.0,
        ema50=9950.0,
        ema100=9900.0,
        ema200=9800.0,
        start_time=dt,
        end_time=dt,
    )

    mil = MarketIntelligence(
        symbol="BTCUSDT",
        timeframe="1h",
        regime=regime_model,
        trend=trend_analysis,
        volatility=vol_analysis,
        liquidity=liq_analysis,
        order_flow=of_analysis,
        volume_profile=vp_analysis,
        correlation=corr_analysis,
        confidence=conf,
        timestamp=dt,
    )

    return MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        trend=TrendState(
            symbol="BTCUSDT",
            timeframe="1h",
            direction=TrendDirection.UP,
            strength=0.85,
            start_time=dt,
            end_time=dt,
        ),
        volume=VolumeState(
            symbol="BTCUSDT",
            timeframe="1h",
            volume_ma=1000.0,
            normalized_volume=1.2,
            expansion_state=VolumeExpansionState.NORMAL,
            atr=2.5,
        ),
        regime_analysis=regime_model,
        volatility_analysis=vol_analysis,
        liquidity_analysis=liq_analysis,
        order_flow_analysis=of_analysis,
        volume_profile_analysis=vp_analysis,
        correlation_analysis=corr_analysis,
        market_confidence=conf,
        market_intelligence=mil,
        updated_at=dt,
    )


def test_grade_enum_migration() -> None:
    """Verify B_PLUS and NO_TRADE enums, and check that REJECT alias works."""
    assert SetupGrade.B_PLUS.value == "B+"
    assert SetupGrade.NO_TRADE.value == "No Trade"
    assert SetupGrade.REJECT.value == "No Trade"
    assert SetupGrade("B+") == SetupGrade.B_PLUS
    assert SetupGrade("No Trade") == SetupGrade.NO_TRADE


def test_grade_engine() -> None:
    """Verify all grade thresholds and demotion logic."""
    engine = GradeEngine()

    # Threshold checks
    assert engine.assign_grade(96.0) == SetupGrade.A_PLUS
    assert engine.assign_grade(89.0) == SetupGrade.A
    assert engine.assign_grade(81.0) == SetupGrade.B_PLUS
    assert engine.assign_grade(72.0) == SetupGrade.B
    assert engine.assign_grade(56.0) == SetupGrade.C
    assert engine.assign_grade(45.0) == SetupGrade.NO_TRADE

    # High severity risk flags demotion checks
    flags_with_one_high_risk = [
        RiskFlag(
            flag_type=RiskFlagType.LOW_LIQUIDITY,
            severity=0.85,
            description="Highly severe low liquidity",
            active=True,
        )
    ]
    flags_with_one_inactive_high_risk = [
        RiskFlag(
            flag_type=RiskFlagType.LOW_LIQUIDITY,
            severity=0.85,
            description="Inactive highly severe low liquidity",
            active=False,
        )
    ]
    flags_with_two_high_risks = [
        RiskFlag(
            flag_type=RiskFlagType.LOW_LIQUIDITY,
            severity=0.9,
            description="High risk 1",
            active=True,
        ),
        RiskFlag(
            flag_type=RiskFlagType.HIGH_VOLATILITY,
            severity=0.8,
            description="High risk 2",
            active=True,
        ),
    ]

    # No demotion if flag is inactive
    assert engine.assign_grade(96.0, flags_with_one_inactive_high_risk) == SetupGrade.A_PLUS
    # 1 demotion step: A+ -> A
    assert engine.assign_grade(96.0, flags_with_one_high_risk) == SetupGrade.A
    # 2 demotion steps: A+ -> A -> B+
    assert engine.assign_grade(96.0, flags_with_two_high_risks) == SetupGrade.B_PLUS
    # Demotion below lowest grade -> NO_TRADE
    assert engine.assign_grade(56.0, flags_with_one_high_risk) == SetupGrade.NO_TRADE


def test_opportunity_engine(mock_market_state: MarketState) -> None:
    """Verify opportunity engine scoring formula."""
    engine = OpportunityEngine()
    
    confluence_score = ConfluenceScore(
        overall_score=85.0,
        setup_grade=SetupGrade.B_PLUS,
        trend_score=80.0,
        structure_score=75.0,
        liquidity_score=90.0,
        zone_score=80.0,
        volume_score=85.0,
        regime_score=80.0,
        session_score=70.0,
        mtf_score=80.0,
        correlation_score=80.0,
        pattern_score=80.0,
        quality_score=90.0,
        conflict_penalty=0.0,
        supporting_factors=[
            SupportingFactor(name="S1", category="TREND", value=10.0, description="desc"),
            SupportingFactor(name="S2", category="LIQUIDITY", value=10.0, description="desc"),
        ],
        conflicting_factors=[],
    )
    
    opp = engine.evaluate(mock_market_state, confluence_score)
    assert opp.setup_quality > 80.0
    assert opp.execution_quality > 80.0
    assert opp.expected_rr >= 1.0
    assert 0.0 <= opp.opportunity_score <= 100.0


def test_risk_flag_engine(mock_market_state: MarketState) -> None:
    """Verify all 7 flag types under different market conditions."""
    engine = RiskFlagEngine()
    
    confluence_score = ConfluenceScore(
        overall_score=85.0,
        setup_grade=SetupGrade.B_PLUS,
        trend_score=80.0,
        structure_score=75.0,
        liquidity_score=90.0,
        zone_score=80.0,
        volume_score=85.0,
        regime_score=80.0,
        session_score=70.0,
        mtf_score=80.0,
        correlation_score=80.0,
        pattern_score=80.0,
        quality_score=90.0,
        conflict_penalty=0.0,
    )
    
    # 1. Normal conditions
    flags = engine.evaluate(mock_market_state, confluence_score)
    assert len(flags) == 7
    # Weekend, funding, news, and spread are false by default in these states
    for f in flags:
        if f.flag_type in (RiskFlagType.FUNDING_RISK, RiskFlagType.NEWS_EVENT_RISK):
            assert not f.active
            assert f.severity == 0.0

    # 2. Trigger Low Liquidity flag (liquidity score < 40)
    low_liq_score = confluence_score.model_copy(update={"liquidity_score": 30.0})
    flags = engine.evaluate(mock_market_state, low_liq_score)
    low_liq_flag = next(f for f in flags if f.flag_type == RiskFlagType.LOW_LIQUIDITY)
    assert low_liq_flag.active
    assert low_liq_flag.severity == 0.7

    # 3. Trigger High Volatility flag (volatility percentile > 90)
    high_vol_state = mock_market_state.model_copy(
        update={
            "volatility_analysis": VolatilityAnalysis(
                symbol="BTCUSDT",
                timeframe="1h",
                atr=5.0,
                historical_volatility=0.15,
                realized_volatility=0.3,
                bollinger_width=0.2,
                volatility_percentile=95.0,
                daily_range=1500.0,
                timestamp=datetime.now(timezone.utc),
            )
        }
    )
    flags = engine.evaluate(high_vol_state, confluence_score)
    high_vol_flag = next(f for f in flags if f.flag_type == RiskFlagType.HIGH_VOLATILITY)
    assert high_vol_flag.active
    assert high_vol_flag.severity > 0.5

    # 4. Trigger Correlation Risk (|max correlation| > 0.85)
    high_corr_state = mock_market_state.model_copy(
        update={
            "correlation_analysis": CorrelationAnalysis(
                symbol="BTCUSDT",
                timeframe="1h",
                correlations={"ETHUSDT": 0.92, "SOLUSDT": 0.2},
                matrix={},
                timestamp=datetime.now(timezone.utc),
            )
        }
    )
    flags = engine.evaluate(high_corr_state, confluence_score)
    corr_flag = next(f for f in flags if f.flag_type == RiskFlagType.CORRELATION_RISK)
    assert corr_flag.active
    assert corr_flag.severity > 0.5

    # 5. Trigger Weekend Risk (UTC Saturday)
    saturday_time = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)  # Saturday
    flags = engine.evaluate(mock_market_state, confluence_score, evaluation_time=saturday_time)
    weekend_flag = next(f for f in flags if f.flag_type == RiskFlagType.WEEKEND_RISK)
    assert weekend_flag.active
    assert weekend_flag.severity == 0.4

    # 6. Trigger Spread Risk (spread > 0.5)
    high_spread_state = mock_market_state.model_copy(
        update={
            "liquidity_analysis": LiquidityAnalysis(
                symbol="BTCUSDT",
                timeframe="1h",
                bid_ask_spread=0.75,
                depth=1000.0,
                market_impact_estimate=0.001,
                slippage_estimate=0.0005,
                volume_score=85.0,
                liquidity_score=90.0,
                buy_side_pools=[9900.0, 9800.0],
                sell_side_pools=[10100.0, 10200.0],
                swept_levels=[],
                timestamp=datetime.now(timezone.utc),
            )
        }
    )
    flags = engine.evaluate(high_spread_state, confluence_score)
    spread_flag = next(f for f in flags if f.flag_type == RiskFlagType.SPREAD_RISK)
    assert spread_flag.active
    assert spread_flag.severity > 0.5


def test_explanation_engine() -> None:
    """Verify deterministic explanations for different grades and scores."""
    engine = ExplanationEngine()
    
    confluence_score = ConfluenceScore(
        overall_score=96.0,
        setup_grade=SetupGrade.A_PLUS,
        trend_score=95.0,
        structure_score=90.0,
        liquidity_score=92.0,
        zone_score=88.0,
        volume_score=90.0,
        regime_score=95.0,
        session_score=90.0,
        mtf_score=90.0,
        correlation_score=90.0,
        pattern_score=90.0,
        quality_score=95.0,
        conflict_penalty=0.0,
        supporting_factors=[
            SupportingFactor(name="Bullish Trend Alignment", category="TREND", value=95.0, description="Highly aligned upward momentum"),
        ],
        conflicting_factors=[],
    )
    
    opp = OpportunityScore(
        setup_quality=98.0,
        execution_quality=95.0,
        expected_rr=2.5,
        opportunity_score=97.0,
    )
    
    flags = [
        RiskFlag(flag_type=RiskFlagType.WEEKEND_RISK, severity=0.0, description="Regular market day", active=False)
    ]
    
    expl = engine.explain(confluence_score, opp, flags, SetupGrade.A_PLUS)
    
    assert expl.recommendation == "STRONG_BUY"
    assert "96.0" in expl.grade_rationale
    assert len(expl.reasons) > 0
    assert "No active risk flags" in expl.risk_summary
    assert len(expl.key_factors) == 1
    assert "Bullish Trend Alignment" in expl.key_factors[0]


def test_confluence_engine_pro(mock_market_state: MarketState) -> None:
    """Verify that ConfluenceEngine.evaluate returns opportunity, risk flags, and explanation."""
    engine = ConfluenceEngine()
    score = engine.evaluate(mock_market_state, None)
    
    assert isinstance(score, ConfluenceScore)
    assert score.overall_score > 0
    assert score.opportunity is not None
    assert isinstance(score.opportunity, OpportunityScore)
    assert len(score.risk_flags) == 7
    assert score.explanation is not None
    assert isinstance(score.explanation, TradeExplanation)


def test_confluence_events(mock_market_state: MarketState) -> None:
    """Verify orchestrator publishes score, grade, and opportunity event updates to event bus."""
    event_bus = EventBus()
    state_store = ConfluenceStateStore()
    repo = ConfluenceRepository()
    
    # Track published events
    published_events = []
    
    def on_event(event: BaseEvent) -> None:
        published_events.append(event)
        
    event_bus.subscribe("system.confluence_score_updated", on_event)
    event_bus.subscribe("system.trade_grade_updated", on_event)
    event_bus.subscribe("system.opportunity_updated", on_event)
    
    # Mock Market State Store resolved by orchestrator
    class MockMarketStateStore:
        def get_snapshot(self, symbol: str):
            from market_intelligence.core.models import MarketSnapshot
            return MarketSnapshot(
                snapshot_id="mock-id",
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                states={"1h": mock_market_state},
            )
            
    orch = ConfluenceOrchestrator()
    orch.initialize(
        confluence_engine=ConfluenceEngine(),
        state_store=state_store,
        repository=repo,
        event_bus=event_bus,
        market_state_store=MockMarketStateStore(),
    )
    
    orch.process_confluence("BTCUSDT", "1h")
    
    event_types = [type(e).__name__ for e in published_events]
    assert "ConfluenceScoreUpdated" in event_types
    assert "OpportunityUpdated" in event_types
    # TradeGradeUpdated is only triggered on grade TRANSITION, but here it's first run (old_grade = None).
    # Let's run a second evaluation with a changed grade to verify TradeGradeUpdated
    
    # Retrieve first state and update it
    prev_snapshot = state_store.get_snapshot("BTCUSDT")
    prev_state = prev_snapshot.states["1h"]
    
    # Create an updated market state with high volatility to trigger a demotion / grade change
    low_liq_state = mock_market_state.model_copy(
        update={
            "volatility_analysis": VolatilityAnalysis(
                symbol="BTCUSDT",
                timeframe="1h",
                atr=5.0,
                historical_volatility=0.15,
                realized_volatility=0.3,
                bollinger_width=0.2,
                volatility_percentile=99.0,
                daily_range=1500.0,
                timestamp=datetime.now(timezone.utc),
            )
        }
    )
    
    class MockLowLiqMarketStateStore:
        def get_snapshot(self, symbol: str):
            from market_intelligence.core.models import MarketSnapshot
            return MarketSnapshot(
                snapshot_id="mock-id",
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                states={"1h": low_liq_state},
            )
            
    orch._market_state_store = MockLowLiqMarketStateStore()
    orch.process_confluence("BTCUSDT", "1h")
    
    event_types = [type(e).__name__ for e in published_events]
    assert "TradeGradeUpdated" in event_types


def test_confluence_rest_endpoints(mock_market_state: MarketState) -> None:
    """Verify new /confluence/* endpoints in dashboard router return expected structures."""
    # Set up DI container and mock stores
    container = Container()
    
    state_store = ConfluenceStateStore()
    repo = ConfluenceRepository()
    engine = ConfluenceEngine()
    
    container.register(IConfluenceStateStore, instance=state_store)
    container.register(IConfluenceRepository, instance=repo)
    container.register(IConfluenceEngine, instance=engine)
    
    # Add a mock ConfluenceState to store
    confluence_score = engine.evaluate(mock_market_state, None)
    c_state = ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1h",
        score=confluence_score,
        updated_at=datetime.now(timezone.utc),
    )
    c_snap = ConfluenceSnapshot(
        snapshot_id="snap-123",
        symbol="BTCUSDT",
        timestamp=c_state.updated_at,
        states={"1h": c_state},
    )
    state_store.update_snapshot(c_snap)
    
    # Set up dashboard state store containing this symbol
    dash_state_store = DashboardStateStore()
    dash_snap = DashboardSnapshot(
        snapshot_id="dash-123",
        symbol="BTCUSDT",
        timeframe="1h",
        confluence=confluence_score.model_dump(mode="json"),
        health_status={},
    )
    dash_state_store.update_snapshot(dash_snap)
    
    dash_repo = DashboardRepository()
    health_monitor = HealthMonitor()
    websocket_manager = WebSocketManager()
    
    event_aggregator = DashboardEventAggregator(
        orchestrator=None,
        health_monitor=health_monitor,
        websocket_manager=websocket_manager,
    )
    
    app = create_app(
        state_store=dash_state_store,
        repository=dash_repo,
        health_monitor=health_monitor,
        websocket_manager=websocket_manager,
        event_aggregator=event_aggregator,
        container=container,
    )
    
    client = TestClient(app)
    
    # 1. GET /confluence/score
    res = client.get("/confluence/score?symbol=BTCUSDT&timeframe=1h")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert "overall_score" in data[0]
    assert "trend_score" in data[0]
    
    # 2. GET /confluence/grade
    res = client.get("/confluence/grade?symbol=BTCUSDT")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert "grade" in data[0]
    
    # 3. GET /confluence/opportunity
    res = client.get("/confluence/opportunity")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert "opportunity" in data[0]
    
    # 4. GET /confluence/risk_flags
    res = client.get("/confluence/risk_flags")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert "risk_flags" in data[0]
    assert data[0]["active_count"] >= 0
    
    # 5. GET /confluence/explanation
    res = client.get("/confluence/explanation")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert "explanation" in data[0]
    
    # 6. GET /confluence/summary
    res = client.get("/confluence/summary")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert "scores" in data[0]
    assert "opportunity" in data[0]
    assert "risk_flags" in data[0]
    assert "explanation" in data[0]


def test_confluence_thread_safety(mock_market_state: MarketState) -> None:
    """Verify thread safety when concurrently processing confluence evaluations."""
    engine = ConfluenceEngine()
    state_store = ConfluenceStateStore()
    repo = ConfluenceRepository()
    
    # Mock Market State Store resolved by orchestrator
    class MockMarketStateStore:
        def get_snapshot(self, symbol: str):
            from market_intelligence.core.models import MarketSnapshot
            return MarketSnapshot(
                snapshot_id="mock-id",
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                states={"1h": mock_market_state},
            )
            
    orch = ConfluenceOrchestrator()
    orch.initialize(
        confluence_engine=engine,
        state_store=state_store,
        repository=repo,
        market_state_store=MockMarketStateStore(),
    )
    
    errors = []
    
    def run_worker(symbol: str) -> None:
        try:
            for _ in range(20):
                orch.process_confluence(symbol, "1h")
        except Exception as e:
            errors.append(e)
            
    threads = [
        threading.Thread(target=run_worker, args=(f"SYM{i}",)) for i in range(10)
    ]
    
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    assert not errors, f"Errors occurred during concurrent execution: {errors}"


def test_confluence_replay_determinism(mock_market_state: MarketState) -> None:
    """Verify that identical input states produce exactly identical confluence results."""
    engine = ConfluenceEngine()
    
    res1 = engine.evaluate(mock_market_state, None)
    res2 = engine.evaluate(mock_market_state, None)
    
    assert res1.overall_score == res2.overall_score
    assert res1.setup_grade == res2.setup_grade
    assert res1.opportunity == res2.opportunity
    assert res1.risk_flags == res2.risk_flags
    assert res1.explanation == res2.explanation
