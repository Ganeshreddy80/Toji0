"""Unit tests for Order Matching Engine (Sprint 7A)."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from backtesting_engine.core.enums import OrderType, PositionSide, SimulatedOrderStatus, TimeInForce
from backtesting_engine.core.models import BacktestConfig, MarketBar, SimulatedOrder
from backtesting_engine.matching.order_matching_engine import OrderMatchingEngine


def test_order_matching_market_order():
    engine = OrderMatchingEngine()
    cfg = BacktestConfig(
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 2, tzinfo=timezone.utc),
        slippage_model="NONE",
        commission_rate=0.001,
    )

    bar = MarketBar(symbol="ETH/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc), open=3000.0, high=3100.0, low=2950.0, close=3050.0, volume=50.0)
    ord1 = SimulatedOrder(symbol="ETH/USDT", side=PositionSide.LONG, quantity=2.0, order_type=OrderType.MARKET, status=SimulatedOrderStatus.ACCEPTED)

    fills = engine.match_orders([ord1], bar, cfg)
    assert len(fills) == 1
    assert fills[0].fill_quantity == 2.0
    assert fills[0].fill_price == 3000.0
    assert fills[0].fee == round(2.0 * 3000.0 * 0.001, 4)


def test_order_matching_limit_order():
    engine = OrderMatchingEngine()
    cfg = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), slippage_model="NONE")

    bar = MarketBar(symbol="ETH/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc), open=3000.0, high=3100.0, low=2950.0, close=3050.0, volume=50.0)

    # Buy Limit below Open
    ord_buy = SimulatedOrder(symbol="ETH/USDT", side=PositionSide.LONG, quantity=1.0, order_type=OrderType.LIMIT, price=2970.0, status=SimulatedOrderStatus.ACCEPTED)
    fills_buy = engine.match_orders([ord_buy], bar, cfg)
    assert len(fills_buy) == 1
    assert fills_buy[0].fill_price == 2970.0

    # Sell Limit above Open
    ord_sell = SimulatedOrder(symbol="ETH/USDT", side=PositionSide.SHORT, quantity=1.0, order_type=OrderType.LIMIT, price=3080.0, status=SimulatedOrderStatus.ACCEPTED)
    fills_sell = engine.match_orders([ord_sell], bar, cfg)
    assert len(fills_sell) == 1
    assert fills_sell[0].fill_price == 3080.0


def test_order_matching_slippage_models():
    engine = OrderMatchingEngine()

    # Fixed Slippage
    cfg_fixed = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), slippage_model="FIXED", slippage_value=5.0)
    bar = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49000.0, close=50500.0, volume=10.0)
    ord1 = SimulatedOrder(symbol="BTC/USDT", side=PositionSide.LONG, quantity=1.0, order_type=OrderType.MARKET, status=SimulatedOrderStatus.ACCEPTED)

    fills = engine.match_orders([ord1], bar, cfg_fixed)
    assert fills[0].fill_price == 50005.0  # 50000 + 5

    # Percentage Slippage
    cfg_pct = BacktestConfig(start_date=datetime(2025, 1, 1, tzinfo=timezone.utc), end_date=datetime(2025, 1, 2, tzinfo=timezone.utc), slippage_model="PERCENTAGE", slippage_value=0.001)
    fills_pct = engine.match_orders([ord1], bar, cfg_pct)
    assert fills_pct[0].fill_price == 50050.0  # 50000 * 1.001
