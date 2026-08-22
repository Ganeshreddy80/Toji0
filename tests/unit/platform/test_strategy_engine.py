import pytest
from datetime import datetime, timezone
from toji_platform.strategy_engine.engine import StrategyEngine
from toji_platform.strategy_engine.strategy import BaseStrategy
from toji_platform.strategy_engine.models import TradeIdea
from toji_platform.market_scanner.models import MarketMetrics, MarketScan
from toji_platform.core.types import HealthStatus

class MockStrategy(BaseStrategy):
    def analyze(self, scan: MarketScan) -> list[TradeIdea]:
        return [
            TradeIdea(
                symbol=scan.symbol,
                direction="LONG",
                confidence=0.9,
                reason="Mock trigger",
                timestamp=datetime.now(timezone.utc),
                risk_notes="No risk"
            )
        ]

class CrashingStrategy(BaseStrategy):
    def analyze(self, scan: MarketScan) -> list[TradeIdea]:
        raise RuntimeError("Crash simulated")

def test_strategy_registration():
    engine = StrategyEngine()
    s = MockStrategy("TestStrategy")
    engine.register_strategy(s)
    
    assert engine.registry.get("TestStrategy") is s
    assert len(engine.registry.list_strategies()) == 1

def test_duplicate_registration():
    engine = StrategyEngine()
    s1 = MockStrategy("TestStrategy")
    s2 = MockStrategy("TestStrategy")
    
    engine.register_strategy(s1)
    with pytest.raises(ValueError, match="already registered"):
        engine.register_strategy(s2)

def test_strategy_unloading():
    engine = StrategyEngine()
    s = MockStrategy("TestStrategy")
    shutdown_called = False
    
    def mock_shutdown():
        nonlocal shutdown_called
        shutdown_called = True
        
    s.shutdown = mock_shutdown
    engine.register_strategy(s)
    engine.unregister_strategy("TestStrategy")
    
    assert engine.registry.get("TestStrategy") is None
    assert shutdown_called is True

def test_strategy_execution():
    engine = StrategyEngine()
    s = MockStrategy("TestStrategy")
    engine.register_strategy(s)
    
    metrics = MarketMetrics(0.0, 0.0, 50.0, 1.0, 0.0, 1000.0, 0.0)
    scans = [MarketScan("BTCUSDT", datetime.now(timezone.utc), [], metrics, 1.0, 1.0, {})]
    
    results = engine.execute_all(scans)
    assert len(results) == 1
    assert results[0].strategy_name == "TestStrategy"
    assert results[0].success is True
    assert len(results[0].trade_ideas) == 1
    assert results[0].trade_ideas[0].symbol == "BTCUSDT"

def test_strategy_isolation():
    engine = StrategyEngine()
    s1 = CrashingStrategy("Crashing")
    s2 = MockStrategy("Healthy")
    
    engine.register_strategy(s1)
    engine.register_strategy(s2)
    
    metrics = MarketMetrics(0.0, 0.0, 50.0, 1.0, 0.0, 1000.0, 0.0)
    scans = [MarketScan("BTCUSDT", datetime.now(timezone.utc), [], metrics, 1.0, 1.0, {})]
    
    results = engine.execute_all(scans)
    assert len(results) == 2
    
    # Verify crashing strategy failed isolated
    r_crash = next(r for r in results if r.strategy_name == "Crashing")
    assert r_crash.success is False
    assert r_crash.error_message == "Crash simulated"
    assert len(r_crash.trade_ideas) == 0
    
    # Verify healthy strategy succeeded unaffected
    r_health = next(r for r in results if r.strategy_name == "Healthy")
    assert r_health.success is True
    assert len(r_health.trade_ideas) == 1

def test_plugin_health():
    s = MockStrategy("Test")
    assert s.health_check() == HealthStatus.HEALTHY


def test_legacy_strategy_adapter_buy():
    from toji_platform.strategy_engine.adapter import LegacyStrategyAdapter
    from strategy.analysis.trend_strategy import TrendFollowingStrategy
    from market_intelligence.core.interfaces import IStateStore
    from price_action.core.interfaces import IPatternStateStore
    from confluence.core.interfaces import IConfluenceStateStore
    
    from market_intelligence.core.models import MarketState, TrendState, BOSRecord
    from market_intelligence.core.enums import TrendDirection
    from confluence.core.models import ConfluenceState, ConfluenceScore
    
    # 1. Setup mock states
    trend_state = TrendState(
        symbol="BTCUSDT",
        timeframe="1m",
        direction=TrendDirection.UP,
        strength=0.8,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc)
    )
    bos_record = BOSRecord(
        symbol="BTCUSDT",
        timeframe="1m",
        level_breached=100.0,
        direction="UP",
        break_timestamp=datetime.now(timezone.utc),
        volume_at_break=1000.0
    )
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1m",
        trend=trend_state,
        bos_history=[bos_record],
        timestamp=datetime.now(timezone.utc)
    )
    
    from confluence.core.enums import SetupGrade
    confluence_state = ConfluenceState(
        symbol="BTCUSDT",
        timeframe="1m",
        score=ConfluenceScore(
            overall_score=85.0,
            setup_grade=SetupGrade.A,
            trend_score=85.0,
            structure_score=85.0,
            liquidity_score=85.0,
            zone_score=85.0,
            volume_score=85.0,
            regime_score=85.0,
            session_score=85.0,
            mtf_score=85.0,
            correlation_score=85.0,
            pattern_score=85.0,
            quality_score=85.0,
            conflict_penalty=0.0
        ),
        timestamp=datetime.now(timezone.utc)
    )
    
    class MockSnapshot:
        def __init__(self, state):
            self.states = {"1m": state}
            
    class MockStore:
        def __init__(self, state):
            self.state = state
        def get_snapshot(self, symbol):
            return MockSnapshot(self.state)
            
    services = {
        IStateStore: MockStore(market_state),
        IPatternStateStore: MockStore(None),
        IConfluenceStateStore: MockStore(confluence_state)
    }
    
    class MockContainer:
        def has(self, key):
            return key in services
        def resolve(self, key):
            return services[key]
            
    # 2. Instantiate TrendFollowingStrategy & Adapter
    legacy_trend = TrendFollowingStrategy(confluence_min=75.0, quality_min=70.0, conflict_max=2.0)
    adapter = LegacyStrategyAdapter(
        name="LegacyTrendFollowing",
        legacy_strategy=legacy_trend,
        container=MockContainer()
    )
    
    # 3. Analyze scan
    metrics = MarketMetrics(0.0, 0.0, 50.0, 1.0, 0.0, 10000.0, 0.0)
    scan = MarketScan(
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        market_states=[],
        metrics=metrics,
        confidence_score=1.0,
        quality_score=1.0,
        diagnostics={"timeframe": "1m"}
    )
    
    ideas = adapter.analyze(scan)
    assert len(ideas) == 1
    assert ideas[0].symbol == "BTCUSDT"
    assert ideas[0].direction == "LONG"
    assert ideas[0].confidence > 0.5


def test_legacy_strategy_adapter_wait():
    from toji_platform.strategy_engine.adapter import LegacyStrategyAdapter
    from strategy.analysis.trend_strategy import TrendFollowingStrategy
    from market_intelligence.core.interfaces import IStateStore
    from price_action.core.interfaces import IPatternStateStore
    from confluence.core.interfaces import IConfluenceStateStore
    
    from market_intelligence.core.models import MarketState, TrendState
    from market_intelligence.core.enums import TrendDirection
    
    # Confluence too low -> wait posture
    trend_state = TrendState(
        symbol="BTCUSDT",
        timeframe="1m",
        direction=TrendDirection.UP,
        strength=0.8,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc)
    )
    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1m",
        trend=trend_state,
        bos_history=[],
        timestamp=datetime.now(timezone.utc)
    )
    
    class MockSnapshot:
        def __init__(self, state):
            self.states = {"1m": state}
            
    class MockStore:
        def __init__(self, state):
            self.state = state
        def get_snapshot(self, symbol):
            return MockSnapshot(self.state)
            
    services = {
        IStateStore: MockStore(market_state),
        IPatternStateStore: MockStore(None),
        IConfluenceStateStore: MockStore(None)
    }
    
    class MockContainer:
        def has(self, key):
            return key in services
        def resolve(self, key):
            return services[key]
            
    legacy_trend = TrendFollowingStrategy()
    adapter = LegacyStrategyAdapter(
        name="LegacyTrendFollowing",
        legacy_strategy=legacy_trend,
        container=MockContainer()
    )
    
    metrics = MarketMetrics(0.0, 0.0, 50.0, 1.0, 0.0, 10000.0, 0.0)
    scan = MarketScan(
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        market_states=[],
        metrics=metrics,
        confidence_score=1.0,
        quality_score=1.0,
        diagnostics={"timeframe": "1m"}
    )
    
    ideas = adapter.analyze(scan)
    assert len(ideas) == 0

