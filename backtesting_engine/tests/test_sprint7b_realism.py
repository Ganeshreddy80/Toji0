"""Comprehensive unit and integration tests for Sprint 7B Advanced Execution Realism."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from backtesting_engine.broker.simulated_broker import SimulatedBroker
from backtesting_engine.core.enums import (
    CommissionModel,
    MarketImpactModel,
    OrderType,
    PositionSide,
    SimulatedOrderStatus,
    SlippageModel,
    SpreadModel,
    TimeInForce,
)
from backtesting_engine.core.models import (
    BacktestConfig,
    MarketBar,
    SimulatedOrder,
)
from backtesting_engine.core.orchestrator import BacktestOrchestrator
from backtesting_engine.matching.execution_realism import (
    CommissionEngine,
    LiquidityEngine,
    MarketImpactEngine,
    SlippageEngine,
    SpreadEngine,
)
from backtesting_engine.matching.order_matching_engine import OrderMatchingEngine
from toji_platform.core.event_bus import InMemoryEventBus


# ============================================================================
# Feature 1: Slippage Engine Tests
# ============================================================================

def test_slippage_engine_models():
    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0, volume=100.0)

    # 1. FIXED_TICKS: 2 ticks * $0.01 tick_size = $0.02
    cfg1 = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), slippage_model="FIXED_TICKS", slippage_value=2.0, tick_size=0.01)
    px1, sl1 = SlippageEngine.calculate_slippage(50000.0, PositionSide.LONG, 1.0, bar, cfg1)
    assert px1 == 50000.02
    assert sl1 == 0.02

    # 2. FIXED_PERCENT: 0.001 (0.1%) -> $50.0
    cfg2 = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), slippage_model="FIXED_PERCENT", slippage_value=0.001)
    px2, sl2 = SlippageEngine.calculate_slippage(50000.0, PositionSide.LONG, 1.0, bar, cfg2)
    assert px2 == 50050.0

    # 3. SPREAD_BASED: multiplier on spread
    quote = SpreadEngine.calculate_quote(bar, BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), spread_model="FIXED", spread_value=10.0))
    cfg3 = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), slippage_model="SPREAD_BASED", slippage_value=0.5)
    px3, sl3 = SlippageEngine.calculate_slippage(50000.0, PositionSide.LONG, 1.0, bar, cfg3, quote=quote)
    assert sl3 == 5.0
    assert px3 == 50005.0


# ============================================================================
# Feature 2: Spread Simulation Tests
# ============================================================================

def test_spread_simulation_quotes():
    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=52000.0, low=48000.0, close=50000.0)

    # 1. FIXED spread = 20.0 -> bid = 49990.0, ask = 50010.0
    cfg1 = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), spread_model="FIXED", spread_value=20.0)
    q1 = SpreadEngine.calculate_quote(bar, cfg1)
    assert q1.spread == 20.0
    assert q1.bid == 49990.0
    assert q1.ask == 50010.0

    # 2. VOLATILITY_BASED spread = (High-Low)*0.01 = 4000 * 0.01 = 40.0
    cfg2 = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), spread_model="VOLATILITY_BASED", spread_value=0.01)
    q2 = SpreadEngine.calculate_quote(bar, cfg2)
    assert q2.spread == 40.0
    assert q2.bid == 49980.0
    assert q2.ask == 50020.0


# ============================================================================
# Feature 3: Liquidity Model & Volume Capping Tests
# ============================================================================

def test_liquidity_model_volume_capping():
    liq = LiquidityEngine(max_volume_pct=0.10)
    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50500.0, volume=100.0)

    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), max_volume_pct=0.10)
    liq.reset_bar(bar, cfg)

    # Requested 25.0 qty, but max volume cap is 10.0 (10% of 100 volume)
    alloc1, restr1 = liq.allocate_fill_quantity(25.0)
    assert alloc1 == 10.0
    assert restr1 is True

    # Next order on same bar gets 0 alloc
    alloc2, restr2 = liq.allocate_fill_quantity(5.0)
    assert alloc2 == 0.0
    assert restr2 is True


# ============================================================================
# Feature 4: Partial Fill Multi-Bar Tracking Tests
# ============================================================================

def test_partial_fill_multi_bar_pipeline():
    orch = BacktestOrchestrator()
    orch.initialize()

    # 10% volume limit on 100 vol bars -> max 10.0 fill per bar
    cfg = BacktestConfig(
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 1, 13, 0, tzinfo=timezone.utc),
        max_volume_pct=0.10,
        slippage_model="NONE",
        spread_model="NONE",
    )

    bars = [
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0, volume=100.0),
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc), open=51000.0, high=52000.0, low=50000.0, close=51000.0, volume=100.0),
    ]

    # Order requesting 20.0 quantity
    orders = [{"symbol": "BTC/USDT", "side": "LONG", "quantity": 20.0, "order_type": "MARKET"}]

    res = orch.run_backtest(config=cfg, bars=bars, orders_to_place=orders)

    # Order filled across 2 bars: 10.0 on bar 1, 10.0 on bar 2
    assert len(res.fills) == 2
    assert res.fills[0].fill_quantity == 10.0
    assert res.fills[1].fill_quantity == 10.0


# ============================================================================
# Feature 5: Queue Priority (FIFO Ordering) Tests
# ============================================================================

def test_queue_priority_fifo_ordering():
    matching_engine = OrderMatchingEngine()
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), max_volume_pct=0.10, spread_model="NONE", slippage_model="NONE")

    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0, volume=100.0)

    # Order A created earlier (10:00:00), Order B created later (10:05:00)
    ord_b = SimulatedOrder(order_id="ord-B", symbol="BTC/USDT", side=PositionSide.LONG, quantity=10.0, order_type=OrderType.MARKET, created_at=datetime(2025, 1, 1, 10, 5, tzinfo=timezone.utc))
    ord_a = SimulatedOrder(order_id="ord-A", symbol="BTC/USDT", side=PositionSide.LONG, quantity=10.0, order_type=OrderType.MARKET, created_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc))

    liq = LiquidityEngine(max_volume_pct=0.10)
    liq.reset_bar(bar, cfg)

    # Pass [ord_b, ord_a] out of order -> queue priority must execute ord_a first
    fills = matching_engine.match_orders([ord_b, ord_a], bar, cfg, liquidity_engine=liq)
    assert len(fills) == 1
    assert fills[0].order_id == "ord-A"


# ============================================================================
# Feature 6: Latency Simulation Tests
# ============================================================================

def test_latency_simulation_bar_delay():
    bus = InMemoryEventBus()
    orch = BacktestOrchestrator(event_bus=bus)
    orch.initialize()

    # Latency = 1 bar delay
    cfg = BacktestConfig(
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 1, 13, 0, tzinfo=timezone.utc),
        latency_bars=1,
        slippage_model="NONE",
        spread_model="NONE",
    )

    bars = [
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0, volume=100.0),
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc), open=51000.0, high=52000.0, low=50000.0, close=51000.0, volume=100.0),
    ]

    orders = [{"symbol": "BTC/USDT", "side": "LONG", "quantity": 1.0, "order_type": "MARKET"}]

    res = orch.run_backtest(config=cfg, bars=bars, orders_to_place=orders)

    # Fill occurs on bar 2 (11:00) due to 1 bar latency delay
    assert len(res.fills) == 1
    assert res.fills[0].timestamp == datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc)


# ============================================================================
# Feature 7: Commission Engine Tests
# ============================================================================

def test_commission_engine_models():
    # 1. MAKER_TAKER: LIMIT = maker rate 0.0005, MARKET = taker rate 0.0010
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), commission_model="MAKER_TAKER", maker_commission_rate=0.0005, taker_commission_rate=0.0010)

    fee_maker = CommissionEngine.calculate_fee(1.0, 50000.0, OrderType.LIMIT, cfg)
    fee_taker = CommissionEngine.calculate_fee(1.0, 50000.0, OrderType.MARKET, cfg)
    assert fee_maker == 25.0   # 50000 * 0.0005
    assert fee_taker == 50.0   # 50000 * 0.0010

    # 2. Min / Max Commission caps
    cfg_cap = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), commission_model="PERCENTAGE", commission_rate=0.001, min_commission=5.0, max_commission=10.0)
    fee_min = CommissionEngine.calculate_fee(0.01, 100.0, OrderType.MARKET, cfg_cap)   # calc 0.001 -> capped to min 5.0
    fee_max = CommissionEngine.calculate_fee(100.0, 1000.0, OrderType.MARKET, cfg_cap)  # calc 100.0 -> capped to max 10.0
    assert fee_min == 5.0
    assert fee_max == 10.0


# ============================================================================
# Feature 8: Execution Constraints Tests
# ============================================================================

def test_execution_constraints_validation():
    broker = SimulatedBroker()
    cfg = BacktestConfig(
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 2, tzinfo=timezone.utc),
        min_quantity=0.10,
        max_quantity=50.0,
        lot_size=0.05,
        tick_size=0.10,
        lot_precision=2,
        tick_precision=1,
    )

    # 1. Order below min_quantity (0.01 < 0.10) -> REJECTED
    ord_rej = broker.place_order(symbol="BTC/USDT", side=PositionSide.LONG, quantity=0.01, order_type=OrderType.MARKET, config=cfg)
    assert ord_rej.status == SimulatedOrderStatus.REJECTED

    # 2. Order quantity rounded to lot_size multiple (1.13 -> 1.15)
    ord_ok = broker.place_order(symbol="BTC/USDT", side=PositionSide.LONG, quantity=1.13, order_type=OrderType.LIMIT, price=50000.04, config=cfg)
    assert ord_ok.status == SimulatedOrderStatus.ACCEPTED
    assert ord_ok.quantity == 1.15
    assert ord_ok.price == 50000.0  # rounded to tick_size 0.10


# ============================================================================
# Feature 9: Market Impact Tests
# ============================================================================

def test_market_impact_large_orders():
    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0, volume=100.0)

    # Linear impact: factor = 0.1, order 10.0 / 100.0 vol = 10% participation -> impact = 50000 * 0.1 * 0.1 = +$500.0 for LONG
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), market_impact_model="LINEAR", market_impact_factor=0.1)
    impact = MarketImpactEngine.calculate_impact(50000.0, PositionSide.LONG, 10.0, bar, cfg)
    assert impact == 500.0


# ============================================================================
# Feature 10: Execution Determinism Across Replay Runs
# ============================================================================

def test_execution_determinism_identical_runs():
    orch1 = BacktestOrchestrator()
    orch2 = BacktestOrchestrator()

    cfg = BacktestConfig(
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        slippage_model="FIXED_TICKS",
        slippage_value=2.0,
        spread_model="FIXED",
        spread_value=10.0,
        commission_model="MAKER_TAKER",
        seed=42,
    )

    bars = [
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0, volume=100.0),
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc), open=50000.0, high=52000.0, low=49500.0, close=51000.0, volume=100.0),
    ]

    orders = [{"symbol": "BTC/USDT", "side": "LONG", "quantity": 1.0, "order_type": "MARKET"}]

    res1 = orch1.run_backtest(config=cfg, bars=bars, orders_to_place=orders)
    res2 = orch2.run_backtest(config=cfg, bars=bars, orders_to_place=orders)

    assert res1.final_equity == res2.final_equity
    assert len(res1.fills) == len(res2.fills)
    assert res1.fills[0].fill_price == res2.fills[0].fill_price
    assert res1.fills[0].fee == res2.fills[0].fee


# ============================================================================
# Hardening Tests (Sprint 7B Production Hardening)
# ============================================================================

def test_volume_based_slippage():
    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0, volume=100.0)
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), slippage_model="VOLUME_BASED", slippage_value=0.01)
    px, sl = SlippageEngine.calculate_slippage(50000.0, PositionSide.LONG, 50.0, bar, cfg)
    assert sl == 250.0
    assert px == 50250.0


def test_percentage_spread():
    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0)
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), spread_model="PERCENTAGE", spread_value=0.002)
    quote = SpreadEngine.calculate_quote(bar, cfg)
    assert quote.spread == 100.0
    assert quote.bid == 49950.0
    assert quote.ask == 50050.0


def test_square_root_market_impact():
    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0, volume=100.0)
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), market_impact_model="SQUARE_ROOT", market_impact_factor=0.1)
    impact = MarketImpactEngine.calculate_impact(50000.0, PositionSide.LONG, 25.0, bar, cfg)
    assert impact == 2500.0


def test_fixed_commission_model():
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), commission_model="FIXED", commission_rate=2.50)
    fee = CommissionEngine.calculate_fee(10.0, 50000.0, OrderType.MARKET, cfg)
    assert fee == 2.50


def test_zero_latency_immediate_execution():
    orch = BacktestOrchestrator()
    orch.initialize()
    cfg = BacktestConfig(
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        latency_bars=0,
        slippage_model="NONE",
        spread_model="NONE",
    )
    bars = [
        MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0, volume=100.0),
    ]
    orders = [{"symbol": "BTC/USDT", "side": "LONG", "quantity": 1.0, "order_type": "MARKET"}]
    res = orch.run_backtest(config=cfg, bars=bars, orders_to_place=orders)
    assert len(res.fills) == 1
    assert res.fills[0].timestamp == datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)


def test_negative_bid_clamping_guard():
    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=1.0, high=2.0, low=0.5, close=1.0)
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), spread_model="FIXED", spread_value=10.0, tick_size=0.01)
    quote = SpreadEngine.calculate_quote(bar, cfg)
    assert quote.bid > 0.0
    assert quote.bid == 0.01


def test_rejected_order_not_in_broker_state():
    broker = SimulatedBroker()
    cfg = BacktestConfig(
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 2, tzinfo=timezone.utc),
        min_quantity=1.0,
        max_quantity=10.0,
    )
    order = broker.place_order(symbol="BTC/USDT", side=PositionSide.LONG, quantity=0.1, order_type=OrderType.MARKET, config=cfg)
    assert order.status == SimulatedOrderStatus.REJECTED
    assert broker.get_order(order.order_id) is None
    assert len(broker.list_orders()) == 0


def test_liquidity_engine_concurrent_allocation():
    import threading

    liq = LiquidityEngine(max_volume_pct=0.50)
    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50000.0, volume=100.0)
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), max_volume_pct=0.50)

    liq.reset_bar(bar, cfg)  # available volume = 50.0

    allocated_totals = []

    def worker():
        alloc, _ = liq.allocate_fill_quantity(10.0)
        allocated_totals.append(alloc)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(allocated_totals) == 50.0

