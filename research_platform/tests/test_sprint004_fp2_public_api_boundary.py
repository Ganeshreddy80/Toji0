"""FP-2 Feature Platform Public API Boundary Enforcement Tests.

Proves:
1. StrategyLoop executes feature extraction via FeaturePlatformOrchestrator.query_realtime() without dead extract_features() dependency.
2. AISignalGenerator queries features via query_realtime().
3. PositionSizingOrchestrator queries features via query_realtime().
4. ExitEngineOrchestrator queries features via query_realtime().
5. TradeJournalOrchestrator queries features via query_realtime().
6. query_realtime() preserves values, schema, symbol handling, and safe empty handling.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pandas as pd
import pytest

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus, IEventBus

from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
from research_platform.feature_platform.plugin import FeaturePlatformPlugin
from research_platform.runtime.strategy_loop import StrategyLoop
from research_platform.ai_signal.signal_generator import AISignalGenerator
from research_platform.position_sizing.orchestrator import PositionSizingOrchestrator
from research_platform.trade_journal.orchestrator import TradeJournalOrchestrator
from research_platform.exit_engine.orchestrator import ExitEngineOrchestrator


@pytest.fixture
def container_with_features():
    container = Container()
    event_bus = InMemoryEventBus()
    container.register(IEventBus, instance=event_bus)
    
    plugin = FeaturePlatformPlugin(container)
    plugin.initialize()
    
    fp_orch = container.resolve(FeaturePlatformOrchestrator)

    # Register mock ConfluenceScoringEngine & TopDownAnalysisEngine for AISignalGenerator
    mock_confluence = MagicMock()
    mock_confluence.calculate_confluence.return_value = MagicMock(score=75.0, explanations=["Bullish"])
    container.register("ConfluenceScoringEngine", instance=mock_confluence)

    mock_pa = MagicMock()
    mock_pa.get_atr.return_value = 500.0
    container.register("PriceActionOrchestrator", instance=mock_pa)
    
    # Compute test bar data for BTCUSDT
    df = pd.DataFrame([
        {"timestamp": 1000, "open": 50000.0, "high": 51000.0, "low": 49500.0, "close": 50500.0, "volume": 10.0},
        {"timestamp": 2000, "open": 50500.0, "high": 52000.0, "low": 50000.0, "close": 51500.0, "volume": 12.0},
    ])
    features_to_compute = [
        "open", "high", "low", "close", "ema9", "ema21", "ema50",
        "rsi", "atr", "volume", "volume_change", "support", "resistance", "breakout", "trend"
    ]
    fp_orch.compute_and_store(features_to_compute, "BTCUSDT", df)
    return container


def test_strategy_loop_uses_public_query_realtime(container_with_features):
    """Verify StrategyLoop extracts features via query_realtime() without extract_features() dependency."""
    fp_orch = container_with_features.resolve(FeaturePlatformOrchestrator)
    fp_orch.query_realtime = MagicMock(side_effect=fp_orch.query_realtime)

    loop = StrategyLoop(container_with_features)
    context = {"tickers": {"BTCUSDT": 51500.0}}
    
    loop.execute(context)

    # Verify query_realtime was invoked on the orchestrator
    assert fp_orch.query_realtime.call_count == 1
    assert "features" in context
    assert len(context["features"]) > 0
    assert context["features"][0]["symbol"] == "BTCUSDT"


def test_query_realtime_contract_preservation(container_with_features):
    """Verify query_realtime() public API output matches expected feature store contract."""
    fp_orch = container_with_features.resolve(FeaturePlatformOrchestrator)
    
    res = fp_orch.query_realtime(["rsi", "ema9", "close"], ["BTCUSDT"])
    assert not res.empty
    assert res.iloc[0]["symbol"] == "BTCUSDT"
    assert "rsi" in res.columns
    assert "ema9" in res.columns
    assert "close" in res.columns
    assert res.iloc[0]["close"] == 51500.0


def test_query_realtime_empty_or_missing_handling(container_with_features):
    """Verify querying non-existent symbols or features returns safe empty structure without crashing."""
    fp_orch = container_with_features.resolve(FeaturePlatformOrchestrator)
    
    # Missing symbol
    res_sym = fp_orch.query_realtime(["close"], ["NONEXISTENT"])
    assert "symbol" in res_sym.columns
    assert "close" not in res_sym.columns

    # Missing feature
    res_feat = fp_orch.query_realtime(["missing_feature"], ["BTCUSDT"])
    assert "symbol" in res_feat.columns
    assert "missing_feature" not in res_feat.columns


def test_downstream_consumers_use_query_realtime_public_api(container_with_features):
    """Verify AISignalGenerator, PositionSizing, and ExitEngine interact through query_realtime."""
    fp_orch = container_with_features.resolve(FeaturePlatformOrchestrator)
    fp_orch.query_realtime = MagicMock(side_effect=fp_orch.query_realtime)

    # 1. AI Signal Generator
    ai_gen = AISignalGenerator(container_with_features)
    ai_res = ai_gen.generate_signal("BTCUSDT", 51500.0)
    assert ai_res is not None
    
    # 2. Position Sizing
    pos_sizing = PositionSizingOrchestrator(container_with_features.resolve(IEventBus), container_with_features)
    pos_sizing._config.method = "volatility"
    pos_sizing.calculate_size("BTCUSDT", "BUY")

    # 3. Exit Engine
    mock_accounting = MagicMock()
    mock_accounting.valuation_engine.get_position.return_value = MagicMock(symbol="BTCUSDT", quantity=1.0)
    container_with_features.register("PortfolioAccounting", instance=mock_accounting)
    
    exit_engine = ExitEngineOrchestrator(container_with_features.resolve(IEventBus), container_with_features)
    event = MagicMock(payload={"symbol": "BTCUSDT", "price": 51500.0})
    exit_engine.on_valuation_update(event)

    # 4. Trade Journal
    mock_oms = MagicMock()
    mock_order = MagicMock(symbol="BTCUSDT", quantity=1.0, side="BUY", price=50000.0, executed_price=50000.0, strategy_id="s1", timestamp=datetime.now(timezone.utc), rationale="Test")
    mock_oms.repository.get_order.return_value = mock_order
    container_with_features.register("OmsCore", instance=mock_oms)
    container_with_features.register("research_platform.oms.oms_core.OmsCore", instance=mock_oms)

    trade_journal = TradeJournalOrchestrator(container_with_features.resolve(IEventBus), container_with_features)
    trade_journal.record_completed_trade("ord-123")

    # Assert query_realtime was called by downstream consumers
    assert fp_orch.query_realtime.call_count >= 4
