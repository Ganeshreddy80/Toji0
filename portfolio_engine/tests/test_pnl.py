import pytest
from portfolio_engine.core.enums import PositionSide
from portfolio_engine.analysis.pnl_calculator import PnlCalculator


def test_calculate_unrealized_pnl_long():
    # Long position
    # Quantity: 10, average entry: 100, current price: 110
    pnl = PnlCalculator.calculate_unrealized_pnl(
        PositionSide.LONG, quantity=10.0, average_entry=100.0, current_price=110.0
    )
    assert pnl == 100.0  # (110 - 100) * 10

    # Current price goes down: 90
    pnl_down = PnlCalculator.calculate_unrealized_pnl(
        PositionSide.LONG, quantity=10.0, average_entry=100.0, current_price=90.0
    )
    assert pnl_down == -100.0


def test_calculate_unrealized_pnl_short():
    # Short position
    # Quantity: 10, average entry: 100, current price: 90
    pnl = PnlCalculator.calculate_unrealized_pnl(
        PositionSide.SHORT, quantity=10.0, average_entry=100.0, current_price=90.0
    )
    assert pnl == 100.0  # (100 - 90) * 10

    # Current price goes up: 110
    pnl_up = PnlCalculator.calculate_unrealized_pnl(
        PositionSide.SHORT, quantity=10.0, average_entry=100.0, current_price=110.0
    )
    assert pnl_up == -100.0


def test_calculate_realized_pnl():
    # Long exit
    pnl_long = PnlCalculator.calculate_realized_pnl(
        PositionSide.LONG, average_entry=100.0, exit_price=110.0, quantity=5.0, fees=2.5
    )
    assert pnl_long == 47.5  # (110 - 100) * 5 - 2.5

    # Short exit
    pnl_short = PnlCalculator.calculate_realized_pnl(
        PositionSide.SHORT, average_entry=100.0, exit_price=90.0, quantity=5.0, fees=2.5
    )
    assert pnl_short == 47.5


def test_calculate_weighted_average_entry():
    avg = PnlCalculator.calculate_weighted_average_entry(
        current_qty=10.0, current_avg=100.0, fill_qty=5.0, fill_price=115.0
    )
    assert avg == 105.0  # (10*100 + 5*115) / 15
