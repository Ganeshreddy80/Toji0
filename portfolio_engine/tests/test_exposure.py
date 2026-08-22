import pytest
from datetime import datetime, timezone
from portfolio_engine.core.enums import PositionSide
from portfolio_engine.core.models import Position
from portfolio_engine.analysis.exposure import ExposureCalculator


def test_exposure_calculations():
    pos_long = Position(
        position_id="pos-1",
        symbol="BTCUSD",
        side=PositionSide.LONG,
        quantity=2.0,
        average_entry=50000.0,
        current_price=55000.0,
        market_value=110000.0,
        cost_basis=100000.0,
        exposure=110000.0,
        open_time=datetime.now(timezone.utc),
    )

    pos_short = Position(
        position_id="pos-2",
        symbol="ETHUSD",
        side=PositionSide.SHORT,
        quantity=10.0,
        average_entry=3000.0,
        current_price=2800.0,
        market_value=28000.0,
        cost_basis=30000.0,
        exposure=28000.0,
        open_time=datetime.now(timezone.utc),
    )

    gross, net = ExposureCalculator.calculate_exposures([pos_long, pos_short])
    assert gross == 138000.0  # 110000 + 28000
    assert net == 82000.0     # 110000 - 28000
