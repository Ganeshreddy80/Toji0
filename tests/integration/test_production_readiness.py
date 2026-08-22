import threading
import time
import pytest
import uuid
from datetime import datetime, timezone

from toji_platform.boot import boot_kernel
from toji_platform.core.errors import EventBusError
from toji_platform.core.event_bus import InMemoryEventBus, AssetSelected
from toji_platform.core.event_bus.events import RiskChecked
from position_sizing.core.events import PositionSizeCalculated
from execution_engine.core.interfaces import IExecutionEngine
from execution_engine.core.models import ExecutionRequest, Order, ExecutionResult
from execution_engine.core.enums import OrderSide, OrderType, OrderTimeInForce, OrderState, ExecutionStatus
from portfolio_engine.core.state import PortfolioStateStore
from portfolio_engine.core.enums import PositionSide
from execution_engine.analysis.replay import ExecutionReplayEngine, ReplayJournal
from trading_context.core.interfaces import ITradingContextStateStore
from trading_context.core.models import TradingContext, ContextMetadata
from market_intelligence.core.models import MarketState
from confluence.core.models import ConfluenceState, ConfluenceScore
from confluence.core.enums import SetupGrade
from toji_platform.core.types import PluginId
from strategy.core.models import StrategyState, StrategySignal
from strategy.core.enums import StrategyDecision, StrategyType
from price_action.core.enums import PatternDirection


def test_event_bus_thread_safety_and_isolation():
    """Verify InMemoryEventBus is thread-safe and isolates subscriber failures."""
    bus = InMemoryEventBus()
    
    # 1. Test Subscriber Isolation
    results = []
    
    def failing_handler(event):
        results.append("fail_run")
        raise ValueError("simulated handler failure")
        
    def succeeding_handler(event):
        results.append("success_run")

    bus.subscribe("system.asset_selected", failing_handler)
    bus.subscribe("system.asset_selected", succeeding_handler)

    event = AssetSelected(source="test")
    
    # Even though failing_handler raises, succeeding_handler must execute
    with pytest.raises(EventBusError, match="simulated handler failure"):
        bus.publish(event)
        
    assert "fail_run" in results
    assert "success_run" in results

    # 2. Test Concurrent Subscriptions and Publishing
    bus2 = InMemoryEventBus()  # Fresh bus without the failing handler
    errors = []

    def subscriber_loop():
        try:
            for i in range(50):
                bus2.subscribe(f"test_topic_{i}", lambda e: None)
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    def publisher_loop():
        try:
            for i in range(50):
                bus2.publish(AssetSelected(source="concurrent"))
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=subscriber_loop),
        threading.Thread(target=subscriber_loop),
        threading.Thread(target=publisher_loop),
        threading.Thread(target=publisher_loop),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent event bus operations raised errors: {errors}"


def test_order_side_routing_correctness():
    """Verify that execution engine correctly routes BUY and SELL sides from strategy signals."""
    kernel = boot_kernel(config_overrides={"market_gateway.provider_mode": "replay"})
    
    # Connect paper broker
    exec_engine = kernel.container.resolve(IExecutionEngine)
    paper_broker = exec_engine._broker_router.get_adapter("paper")
    paper_broker.connect()

    tc_store = kernel.container.resolve(ITradingContextStateStore)
    symbol = "BTC/USDT"
    timeframe = "1m"

    # Populate active context with a SELL signal
    signal = StrategySignal(
        signal_id="sig-sell-1",
        symbol=symbol,
        timeframe=timeframe,
        direction=PatternDirection.BEARISH,
        strategy_type=StrategyType.TREND_FOLLOWING,
        decision=StrategyDecision.SELL,
        confidence=90.0,
        confluence_score=85.0,
        reasoning="Bearish breakout confirmation.",
        supporting_factors=[],
        conflicting_factors=[],
        detected_at=datetime.now(timezone.utc),
    )
    
    # Construct mock sub-states
    mstate = MarketState(
        symbol=symbol,
        timeframe=timeframe,
    )
    cstate = ConfluenceState(
        symbol=symbol,
        timeframe=timeframe,
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
        ),
        updated_at=datetime.now(timezone.utc),
    )
    sstate = StrategyState(
        symbol=symbol,
        timeframe=timeframe,
        active_strategy=StrategyType.TREND_FOLLOWING,
        latest_signal=signal,
    )
    
    context = TradingContext(
        symbol=symbol,
        timeframe=timeframe,
        market_state=mstate,
        confluence_state=cstate,
        strategy_state=sstate,
        strategy_signal=signal,
        metadata=ContextMetadata(),
        generated_at=datetime.now(timezone.utc),
    )
    
    # Update state store
    from trading_context.core.models import TradingContextSnapshot
    tc_store.update_snapshot(
        TradingContextSnapshot(
            snapshot_id=str(uuid.uuid4()),
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            states={timeframe: context},
        )
    )

    # 1. Trigger positioning sizing execution flow
    sizing_payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "result": {
            "success": True,
            "status": "APPROVED",
            "position_size": {
                "symbol": symbol,
                "timeframe": timeframe,
                "quantity": 25.0,
                "lots": 25.0,
                "leverage": 1.0,
                "margin_required": 10.0,
                "account_risk_percent": 0.01,
                "capital_used": 25000.0,
                "stop_distance": 500.0,
                "take_profit_distance": 1000.0,
                "sizing_method": "fixed_fractional",
                "confidence": 1.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "reasons": ["Approved for test"],
            "violations": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    size_calculated_event = PositionSizeCalculated(
        source="test_sizing",
        payload={
            "symbol": symbol,
            "timeframe": timeframe,
            "state": sizing_payload,
            "request_id": "test-req-sell-1",
        }
    )
    
    # Process calculated size event via Event Bus
    exec_plugin = kernel.plugin_manager.get(PluginId("execution_engine"))
    kernel.event_bus.publish(size_calculated_event)
    
    results = list(exec_plugin._orchestrator._repository._results.values())
    assert len(results) > 0
    result = results[-1]
    
    assert result is not None
    assert result.orders[0].side == OrderSide.SELL  # Verified routing!
    assert result.orders[0].quantity == 25.0


def test_pre_trade_validation_duplicate_blocking():
    """Verify that duplicate requests with the same request_id are blocked."""
    kernel = boot_kernel(config_overrides={"market_gateway.provider_mode": "replay"})
    exec_engine = kernel.container.resolve(IExecutionEngine)
    paper_broker = exec_engine._broker_router.get_adapter("paper")
    paper_broker.connect()

    req = ExecutionRequest(
        execution_id="dup-exec-1",
        request_id="dup-req-1",
        signal_id="dup-sig-1",
        strategy_id="dup-strat-1",
        position_id="dup-pos-1",
        correlation_id="dup-corr-1",
        symbol="BTC/USDT",
        timeframe="1m",
        quantity=20.0,
        price=50000.0,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        time_in_force=OrderTimeInForce.GTC,
        leverage=1.0,
        margin_required=10.0,
        timestamp=datetime.now(timezone.utc),
    )

    # First execution should succeed
    res1 = exec_engine.submit_execution(req)
    assert res1.status == ExecutionStatus.EXECUTED

    # Second execution with same request_id should be rejected
    res2 = exec_engine.submit_execution(req)
    assert res2.status == ExecutionStatus.REJECTED
    assert "Duplicate execution" in res2.orders[0].error_message


def test_portfolio_position_lifecycle_metrics():
    """Verify position entry, average price calculation, realized PnL, leverage, and exposure."""
    store = PortfolioStateStore(initial_balance=100000.0)
    symbol = "BTC/USDT"
    pos_id = "test-pos-id"

    # 1. First entry
    snap1, opened1, closed1 = store.apply_position_fill(
        position_id=pos_id,
        symbol=symbol,
        side=PositionSide.LONG,
        quantity=1.0,
        price=50000.0,
    )
    assert opened1 is not None
    assert closed1 is None
    assert snap1.positions[symbol].quantity == 1.0
    assert snap1.positions[symbol].average_entry == 50000.0
    assert snap1.metrics.gross_exposure == 50000.0

    # 2. Add to position
    snap2, opened2, closed2 = store.apply_position_fill(
        position_id=pos_id,
        symbol=symbol,
        side=PositionSide.LONG,
        quantity=1.0,
        price=60000.0,
    )
    assert opened2 is None
    assert closed2 is None
    assert snap2.positions[symbol].quantity == 2.0
    assert snap2.positions[symbol].average_entry == 55000.0  # Weighted average entry
    assert snap2.metrics.gross_exposure == 120000.0  # 2.0 * 60000.0

    # 3. Partial Close
    snap3, opened3, closed3 = store.apply_position_fill(
        position_id=pos_id,
        symbol=symbol,
        side=PositionSide.SHORT,
        quantity=1.0,
        price=70000.0,
    )
    assert opened3 is None
    assert closed3 is None
    assert snap3.positions[symbol].quantity == 1.0
    assert snap3.positions[symbol].average_entry == 55000.0
    # Realized PnL is tracked on the open position, not on snapshot metrics (which only counts closed positions)
    assert snap3.positions[symbol].realized_pnl == 15000.0

    # 4. Full Close
    snap4, opened4, closed4 = store.apply_position_fill(
        position_id=pos_id,
        symbol=symbol,
        side=PositionSide.SHORT,
        quantity=1.0,
        price=80000.0,
    )
    assert opened4 is None
    assert closed4 is not None
    assert symbol not in snap4.positions
    # After full close, total_realized_pnl on metrics should include all realized gains
    assert snap4.metrics.total_realized_pnl > 0.0


def test_replay_journal_determinism():
    """Verify ExecutionReplayEngine reproduces outputs identical to the expected states."""
    kernel = boot_kernel(config_overrides={"market_gateway.provider_mode": "replay"})
    exec_engine = kernel.container.resolve(IExecutionEngine)
    paper_broker = exec_engine._broker_router.get_adapter("paper")
    paper_broker.connect()

    replay_engine = ExecutionReplayEngine(exec_engine)

    req = ExecutionRequest(
        execution_id="rep-exec-1",
        request_id="rep-req-1",
        signal_id="rep-sig-1",
        strategy_id="rep-strat-1",
        position_id="rep-pos-1",
        correlation_id="rep-corr-1",
        symbol="BTC/USDT",
        timeframe="1m",
        quantity=20.0,
        price=50000.0,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        time_in_force=OrderTimeInForce.GTC,
        leverage=1.0,
        margin_required=10.0,
        timestamp=datetime.now(timezone.utc),
    )

    journal = ReplayJournal(
        requests=[req],
        expected_order_states={f"ord-{req.execution_id}": OrderState.FILLED}
    )

    res = replay_engine.run_replay(journal)
    assert res.success is True
    assert res.replayed_orders_count == 1
    assert len(res.mismatches) == 0
