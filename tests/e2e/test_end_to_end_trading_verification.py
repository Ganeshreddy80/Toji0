"""End-to-End Trading Pipeline Verification tests for TOJI.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# Mock redis globally to prevent any connection attempts during platform bootstrap/test execution
sys.modules["redis"] = MagicMock()

import os
import uuid
import pandas as pd
import pytest
from datetime import datetime, timezone, timedelta

from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.service_registry import ServiceRegistry
from data.schemas.market_data import OHLCV
from market_gateway.normalizer.normalizer import MarketDataNormalizer
from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
from research_platform.feature_platform.models import FeatureRecord
from research_platform.strategy_framework.composer import StrategyComposer
from research_platform.ai_signal.signal_generator import AISignalGenerator
from research_platform.oms.oms_core import OmsCore
from research_platform.risk_management.orchestrator import RiskManagementOrchestrator
from research_platform.alerting.models import Alert, AlertSeverity, AlertChannel


@pytest.fixture(scope="module")
def app():
    # Setup test env variables
    os.environ["TELEGRAM_ENABLED"] = "true"
    os.environ["TELEGRAM_BOT_TOKEN"] = "mock_telegram_token"
    os.environ["TELEGRAM_CHAT_ID"] = "mock_chat_id"
    os.environ["DATABASE_MODE"] = "DEV"

    # Patch the BinanceDemoGateway.start method so no background thread runs during tests
    with patch("research_platform.live_trading.binance_demo.BinanceDemoGateway.start"):
        app_instance = bootstrap_platform()
        yield app_instance
        app_instance.shutdown()


def test_market_tick_generates_feature_snapshot(app):
    container = ServiceRegistry().get_service("Container")
    feature_platform = container.resolve(FeaturePlatformOrchestrator)

    # 1. Raw WebSocket candle payload (Binance)
    raw_candle = {
        "s": "BTCUSDT",
        "k": {
            "t": int(datetime.now(timezone.utc).timestamp() * 1000),
            "o": "60000.0",
            "h": "60500.0",
            "l": "59900.0",
            "c": "60200.0",
            "v": "250.5",
            "i": "1m"
        }
    }

    # 2. Normalize raw candle using normalizer
    candle = MarketDataNormalizer.normalize_binance_candle(raw_candle)
    assert candle.symbol == "BTCUSDT"
    assert candle.close == 60200.0

    # 3. Construct input DataFrame
    df = pd.DataFrame([candle.model_dump()])

    # 4. Register close feature definition if not exists
    record = FeatureRecord(
        uuid=str(uuid.uuid4()),
        name="close",
        display_name="Close Price",
        description="Tick close price",
        formula="close",
        category="Price",
        subcategory="Raw",
        owner="quants",
        author="CTO",
        version="1.0.0",
        update_frequency="1m",
        warmup_length=0,
        lookback_window=0,
        required_resolution="1m"
    )
    try:
        feature_platform.register_feature(record)
    except ValueError:
        pass  # already registered

    # 5. Compute feature snapshots
    output_df = feature_platform.compute_and_store(["close"], "BTCUSDT", df)
    assert "close" in output_df.columns

    # 6. Verify feature is persisted in store
    stored = feature_platform.store.query_latest(["close"], ["BTCUSDT"])
    assert not stored.empty
    assert stored.iloc[-1]["close"] == 60200.0


def test_feature_snapshot_reaches_strategy(app):
    container = ServiceRegistry().get_service("Container")
    feature_platform = container.resolve(FeaturePlatformOrchestrator)
    strategy_composer = container.resolve(StrategyComposer)

    # 1. Retrieve the calculated feature snapshot value
    stored = feature_platform.store.query_latest(["close"], ["BTCUSDT"])
    latest_close = float(stored.iloc[-1]["close"])

    # 2. Compose Mean Reversion strategy
    strategy = strategy_composer.compose(
        strategy_id="mean_reversion_e2e",
        name="Mean Reversion E2E Strategy",
        strategy_type="MEAN_REVERSION",
        version="1.0.0",
        symbols=["BTCUSDT"],
        parameters={"deviation": 2.0}
    )

    # 3. Simulate indicators based on feature snapshot value (Price broke lower band)
    indicators = {
        "vwap": latest_close + 800.0,
        "atr": 200.0
    }

    # 4. Check strategy composer decision output
    decision = strategy_composer.generate_decision(
        strategy=strategy,
        symbol="BTCUSDT",
        current_price=latest_close,
        indicators=indicators
    )

    from strategy.core.enums import StrategyDecision
    # Price is 60200, VWAP is 61000, lower_band = 61000 - 2 * 200 = 60600
    # Price is below lower band (60200 < 60600) -> triggers BUY
    assert decision == StrategyDecision.BUY


def test_strategy_ai_confluence_decision(app):
    container = ServiceRegistry().get_service("Container")
    ai_generator = container.resolve(AISignalGenerator)
    confluence_engine = container.resolve("ConfluenceScoringEngine")

    # 1. Bullish Confluence (Score >= 70)
    from research_platform.confluence.models import ConfluenceResult
    mock_bullish = ConfluenceResult(
        symbol="BTCUSDT",
        score=80.0,
        direction="BULLISH",
        confidence="HIGH",
        strength="STRONG",
        explanations=["Strong trend"]
    )

    with patch.object(confluence_engine, "calculate_confluence", return_value=mock_bullish):
        ai_signal = ai_generator.generate_signal("BTCUSDT", 60200.0)
        assert ai_signal.signal == "BUY"
        assert ai_signal.confidence == 0.8
        assert "Strong trend" in ai_signal.reasoning

    # 2. Bearish Confluence (Score <= 30)
    mock_bearish = ConfluenceResult(
        symbol="BTCUSDT",
        score=20.0,
        direction="BEARISH",
        confidence="HIGH",
        strength="STRONG",
        explanations=["Weak structures"]
    )

    with patch.object(confluence_engine, "calculate_confluence", return_value=mock_bearish):
        ai_signal = ai_generator.generate_signal("BTCUSDT", 60200.0)
        assert ai_signal.signal == "SELL"
        assert ai_signal.confidence == 0.8
        assert "Weak structures" in ai_signal.reasoning


def test_low_confidence_returns_wait(app):
    container = ServiceRegistry().get_service("Container")
    ai_generator = container.resolve(AISignalGenerator)
    confluence_engine = container.resolve("ConfluenceScoringEngine")

    # Neutral score (30 < Score < 70)
    from research_platform.confluence.models import ConfluenceResult
    mock_neutral = ConfluenceResult(
        symbol="BTCUSDT",
        score=55.0,
        direction="NEUTRAL",
        confidence="MEDIUM",
        strength="WEAK",
        explanations=["No pattern"]
    )

    with patch.object(confluence_engine, "calculate_confluence", return_value=mock_neutral):
        ai_signal = ai_generator.generate_signal("BTCUSDT", 60200.0)
        assert ai_signal.signal == "WAIT"
        assert ai_signal.confidence == 0.5


def test_order_uses_oms_safety_gateway(app):
    container = ServiceRegistry().get_service("Container")
    oms_core = container.resolve(OmsCore)

    order = oms_core.submit_order(
        strategy_id="strat-123",
        symbol="BTCUSDT",
        quantity=0.5,
        price=60200.0,
        order_type="MARKET",
        side="BUY",
        rationale="E2E test order"
    )
    
    # Retrieve order state transition history
    history = oms_core.repository.get_order_history(order.order_id)
    assert "NEW" in history
    assert "VALIDATED" in history
    assert "QUEUED" in history


def test_killswitch_blocks_pipeline(app):
    container = ServiceRegistry().get_service("Container")
    oms_orch = container.resolve("OrderManagementSystemOrchestrator")
    risk_orch = container.resolve(RiskManagementOrchestrator)

    # 1. Activate Manual Kill Switch
    risk_orch.kill_switch.activate("E2E manual halt")
    assert risk_orch.kill_switch.is_activated is True

    # 2. Attempt to ingest order
    from research_platform.oms.models import OrderRequest
    req = OrderRequest(
        order_id=f"ord-{uuid.uuid4().hex[:6]}",
        symbol="BTCUSDT",
        direction="BUY",
        quantity=1.0,
        order_type="LIMIT",
        price=60200.0
    )

    # 3. Verify compliance fails closed when KillSwitch is active
    with pytest.raises(ValueError) as excinfo:
        oms_orch.ingest_order(req)
    assert "KillSwitch activated" in str(excinfo.value)

    # 4. Release Kill Switch
    risk_orch.kill_switch.release()
    assert risk_orch.kill_switch.is_activated is False


def test_telegram_alert_mock(app):
    container = ServiceRegistry().get_service("Container")
    alert_orch = container.resolve("AlertOrchestrator")

    alert = Alert(
        title="Sprint Finalization Alert",
        message="Running E2E tests for Live Pipeline validation.",
        severity=AlertSeverity.HIGH,
        channels=[AlertChannel.TELEGRAM]
    )

    # Mock the telegram channel send method
    telegram_chan = alert_orch._dispatcher._channels[AlertChannel.TELEGRAM]
    with patch.object(telegram_chan, "send") as mock_send:
        from research_platform.alerting.models import NotificationResult
        mock_send.return_value = NotificationResult(alert_id=alert.alert_id, channel=AlertChannel.TELEGRAM, success=True)

        alert_orch.fire(alert)
        mock_send.assert_called_once_with(alert)


def test_sprint2_pipeline_authoritative_consistency(app):
    # Hook listener to capture system.paper_order_filled events (Single-event guarantee verification)
    paper_order_filled_events = []
    
    container = ServiceRegistry().get_service("Container")
    event_bus = ServiceRegistry().get_service("EventBus")
    
    def on_paper_order_filled(event) -> None:
        paper_order_filled_events.append(event)
        
    event_bus.subscribe("system.paper_order_filled", on_paper_order_filled)
    
    from toji_platform.runtime.state import RuntimeStateManager
    state_manager = RuntimeStateManager()
    state_manager.load()
    
    # Save starting counts
    start_ticks = state_manager.processed_ticks
    start_trades = state_manager.trades_filled
    
    # Get components
    pa_orch = container.resolve("PriceActionOrchestrator")
    fp_orch = container.resolve("FeaturePlatformOrchestrator")
    strategy_composer = container.resolve("StrategyComposer")
    ai_generator = container.resolve("AISignalGenerator")
    oms_core = container.resolve(OmsCore)
    
    # Clean price action cache
    pa_orch._bars.clear()
    pa_orch._tick_history.clear()
    
    # Generate mock ticks to trigger strategy BUY decision
    symbol = "BTCUSDT"
    start_price = 50000.0
    tick_time = datetime.now(timezone.utc)
    
    features_to_compute = [
        "open", "high", "low", "close", "ema9", "ema21", "ema50",
        "rsi", "atr", "volume", "volume_change", "support", "resistance", "breakout", "trend"
    ]
    
    for name in features_to_compute:
        record = FeatureRecord(
            uuid=str(uuid.uuid4()), name=name, display_name=name.upper(), description="", formula=name,
            dependencies=[], category="Indicator", subcategory="Raw",
            owner="quants", author="CTO", version="1.0.0", update_frequency="1m",
            warmup_length=0, lookback_window=0, required_resolution="1m"
        )
        try:
            fp_orch.register_feature(record)
        except ValueError:
            pass
            
    # Mock ConfluenceScoringEngine to return a bullish confluence result and bypass network calls
    confluence_engine = container.resolve("ConfluenceScoringEngine")
    from research_platform.confluence.models import ConfluenceResult
    mock_bullish = ConfluenceResult(
        symbol=symbol,
        score=85.0,
        direction="BULLISH",
        confidence="HIGH",
        strength="STRONG",
        explanations=["Strong breakout"]
    )
    
    # Mock Telegram alert dispatcher to prevent outgoing network requests
    alert_orch = container.resolve("AlertOrchestrator")
    telegram_chan = alert_orch._dispatcher._channels[AlertChannel.TELEGRAM]
    
    with patch.object(confluence_engine, "calculate_confluence", return_value=mock_bullish), \
         patch("redis.Redis.from_url", return_value=None), \
         patch.object(telegram_chan, "send") as mock_alert_send:
         
        from research_platform.alerting.models import NotificationResult
        mock_alert_send.return_value = NotificationResult(alert_id="mock_id", channel=AlertChannel.TELEGRAM, success=True)
         
        # Drive the pipeline sequentially for 25 mock ticks
        for i in range(25):
            if i < 15:
                price = start_price - (i * 200.0)  # down from 50k to 47k
            else:
                price = start_price - (15 * 200.0) + ((i - 15) * 600.0)  # up from 47k to 53k
                
            # 1. Price action update
            pa_orch.process_tick(symbol, price, tick_time, 2.5)
            
            # 2. Features calculation
            bars_list = pa_orch.get_bars(symbol)
            if len(bars_list) > 1:
                df = pd.DataFrame(bars_list)
            else:
                candle = OHLCV(symbol=symbol, timestamp=tick_time, open=price, high=price, low=price, close=price, volume=2.5, interval="1m")
                df = pd.DataFrame([candle.model_dump()])
            output_df = fp_orch.compute_and_store(features_to_compute, symbol, df)
            clean_features = output_df.iloc[-1].to_dict()
            
            # 3. Strategy decision
            strategy = strategy_composer.compose(
                strategy_id=f"strat_{symbol}",
                name="Mean Reversion Paper E2E",
                strategy_type="MEAN_REVERSION",
                version="1.0.0",
                symbols=[symbol],
                parameters={"deviation": 2.0}
            )
            indicators = clean_features.copy()
            indicators["vwap"] = pa_orch.get_vwap(symbol)
            indicators["atr"] = pa_orch.get_atr(symbol)
            
            strategy_decision = strategy_composer.generate_decision(
                strategy=strategy,
                symbol=symbol,
                current_price=price,
                indicators=indicators
            )
            
            from strategy.core.enums import StrategyDecision
            decision_str = strategy_decision.value if isinstance(strategy_decision, StrategyDecision) else str(strategy_decision)
            if decision_str not in ("BUY", "SELL"):
                decision_str = "HOLD"
                
            if decision_str == "HOLD":
                continue
                
            # 4. AI Confluence & Signal
            ai_signal = ai_generator.generate_signal(symbol, price)
            if ai_signal.signal not in ("BUY", "SELL"):
                continue
                
            # 5. OMS & Paper Execution (authoritative single-path pipeline test)
            order = oms_core.submit_order(
                strategy_id=strategy.metadata.strategy_id,
                symbol=symbol,
                quantity=0.5,
                price=price,
                order_type="MARKET",
                side=ai_signal.signal,
                rationale=ai_signal.reasoning
            )
            if order and order.status == "FILLED":
                state_manager.record_trade()
        
    state_manager.load()
    
    # Assertions
    added_trades = state_manager.trades_filled - start_trades
    assert added_trades > 0, "No trades were filled during the E2E simulation!"
    
    # Get database connection and query counts using raw SQL (bypasses repository class imports)
    db = ServiceRegistry().get_service("Database")
    assert db is not None
    
    with db.connection.engine.connect() as conn:
        from sqlalchemy import text
        db_trades_count = conn.execute(text("SELECT COUNT(*) FROM trades")).scalar()
        db_ledger_count = conn.execute(text("SELECT COUNT(*) FROM trade_ledger")).scalar()
        db_orders_count = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        db_filled_count = conn.execute(text("SELECT COUNT(*) FROM orders WHERE status = 'FILLED'")).scalar()
        
    # Verification 1: Single-event guarantee (Exactly one paper_order_filled event per filled trade)
    assert len(paper_order_filled_events) == added_trades, \
        f"Single-event guarantee failure: Captured events ({len(paper_order_filled_events)}) != State trades increment ({added_trades})"
        
    # Verification 2: Runtime vs Database consistency
    assert db_trades_count == db_ledger_count, \
        f"Database inconsistency: Trades row count ({db_trades_count}) != Ledger row count ({db_ledger_count})"
    assert state_manager.trades_filled == db_trades_count, \
        f"Database vs State manager inconsistency: State Trades ({state_manager.trades_filled}) != DB Trades ({db_trades_count})"
        
    # Verification 3: OMS status transitions
    assert db_filled_count == state_manager.trades_filled, \
        f"OMS Status transitions failed: FILLED orders ({db_filled_count}) != State Trades ({state_manager.trades_filled})"

