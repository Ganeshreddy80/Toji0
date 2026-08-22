"""Unit tests for the backtesting engine models, runners, and costs."""

from __future__ import annotations

from datetime import datetime, UTC
import pytest
from pydantic import ValidationError

from analytics.backtesting.costs import (
    FixedCommissionModel,
    LinearCommissionModel,
    FixedSpreadSlippageModel,
    VolatilityScaledSlippageModel,
)
from analytics.backtesting.models import Order, Trade, Position, PortfolioState
from analytics.backtesting.runner import StrategyRunner


def test_backtesting_models_pydantic():
    """Verify validation boundaries of order and position models."""
    # Qty must be greater than zero for Order
    with pytest.raises(ValidationError):
        Order(
            symbol="BTC/USDT",
            qty=-5.0,
            side="buy",
            timestamp=datetime.now(UTC),
        )


def test_transaction_cost_models():
    """Verify commission and slippage calculation models."""
    comm_fixed = FixedCommissionModel(fee_per_trade=5.0)
    assert comm_fixed.calculate_commission(10, 100.0) == 5.0
    
    comm_linear = LinearCommissionModel(bps_rate=0.002) # 20 bps
    assert comm_linear.calculate_commission(10, 100.0) == 10 * 100.0 * 0.002
    
    slip_fixed = FixedSpreadSlippageModel(spread_fraction=0.001)
    assert slip_fixed.calculate_slippage(100.0, 10, "buy") == 0.1
    
    slip_vol = VolatilityScaledSlippageModel(base_slip_fraction=0.0005, vol_multiplier=2.0)
    assert slip_vol.calculate_slippage(100.0, 10, "buy", volatility=0.5) == 100.0 * 0.0005 * 2.0


def test_strategy_runner_long_execution():
    """Test StrategyRunner buying a position and reducing it."""
    runner = StrategyRunner(
        initial_cash=10000.0,
        commission_model=FixedCommissionModel(fee_per_trade=10.0),
        slippage_model=FixedSpreadSlippageModel(spread_fraction=0.001),  # buy price: price * 1.001
    )
    
    order = Order(
        symbol="AAPL",
        qty=10.0,
        side="buy",
        timestamp=datetime.now(UTC),
    )
    
    # Process buy
    # price = 100.0. Slippage = 0.1, fill price = 100.1. Commission = 10.0.
    # Total cost = 10 * 100.1 + 10.0 = 1011.0.
    # Cash left = 10000 - 1011 = 8989.0.
    trade = runner.submit_order(order, current_price=100.0)
    
    assert trade is not None
    assert trade.price == 100.1
    assert trade.commission == 10.0
    assert trade.slippage == 0.1
    assert runner.cash == 8989.0
    assert "AAPL" in runner.positions
    assert runner.positions["AAPL"].qty == 10.0
    assert runner.positions["AAPL"].avg_entry_price == 100.1
    
    # Process sell (reduce long by 4 units)
    # price = 110.0. Slippage = 0.11, fill price = 109.89. Commission = 10.0.
    # Revenue = 4 * 109.89 - 10.0 = 439.56 - 10 = 429.56.
    # Cash left = 8989.0 + 429.56 = 9418.56.
    # Realized PnL = (109.89 - 100.1) * 4 = 9.79 * 4 = 39.16.
    order_sell = Order(
        symbol="AAPL",
        qty=4.0,
        side="sell",
        timestamp=datetime.now(UTC),
    )
    trade_sell = runner.submit_order(order_sell, current_price=110.0)
    
    assert trade_sell is not None
    assert trade_sell.price == 109.89
    assert runner.cash == pytest.approx(9418.56)
    assert runner.positions["AAPL"].qty == 6.0
    assert runner.positions["AAPL"].avg_entry_price == 100.1
    assert trade_sell.realized_pnl == pytest.approx(39.16)


def test_strategy_runner_position_flip():
    """Test StrategyRunner flipping position from short to long."""
    runner = StrategyRunner(initial_cash=1000.0)  # zero commission/slippage
    
    # 1. Open short position of size 2 at 100.0 -> cash increases by 200.0 (total 1200.0)
    order1 = Order(symbol="BTC", qty=2.0, side="sell", timestamp=datetime.now(UTC))
    runner.submit_order(order1, current_price=100.0)
    
    assert runner.positions["BTC"].qty == -2.0
    assert runner.cash == 1200.0
    
    # 2. Buy size 5 at 80.0.
    # First 2 units close short at 80.0 -> realized PnL = (100 - 80) * 2 = +40.0.
    # Cash decreases by 5 * 80 = 400.0 -> Cash becomes 1200 - 400 = 800.0.
    # Position becomes +3 units at 80.0.
    order2 = Order(symbol="BTC", qty=5.0, side="buy", timestamp=datetime.now(UTC))
    trade = runner.submit_order(order2, current_price=80.0)
    
    assert runner.positions["BTC"].qty == 3.0
    assert runner.positions["BTC"].avg_entry_price == 80.0
    assert runner.cash == 800.0
    assert trade.realized_pnl == 40.0


def test_strategy_runner_valuation_tracking():
    """Test updating portfolio states and retrieving curves."""
    runner = StrategyRunner(initial_cash=1000.0)
    
    # Buy 2 units of asset at 50.0 -> cash drops to 900.0
    order = Order(symbol="ETH", qty=2.0, side="buy", timestamp=datetime.now(UTC))
    runner.submit_order(order, current_price=50.0)
    
    # Update valuations at price 60.0
    # Holdings value = 2 * 60 = 120.0
    # Total equity = 900 + 120 = 1020.0
    t = datetime.now(UTC)
    state = runner.update_valuations(t, {"ETH": 60.0})
    
    assert state.cash == 900.0
    assert state.holdings_value == 120.0
    assert state.total_equity == 1020.0
    
    eq_curve = runner.get_equity_curve()
    assert len(eq_curve) == 1
    assert eq_curve.iloc[0] == 1020.0


def test_strategy_runner_hooks():
    """Verify order and trade event callback hooks execution."""
    runner = StrategyRunner(initial_cash=1000.0)
    
    order_calls = []
    trade_calls = []
    
    runner.on_order_submitted.append(lambda o: order_calls.append(o))
    runner.on_trade_executed.append(lambda t: trade_calls.append(t))
    
    order = Order(symbol="AAPL", qty=1.0, side="buy", timestamp=datetime.now(UTC))
    runner.submit_order(order, current_price=10.0)
    
    assert len(order_calls) == 1
    assert len(trade_calls) == 1
    assert order_calls[0].symbol == "AAPL"
    assert trade_calls[0].price == 10.0
stream_result = None
