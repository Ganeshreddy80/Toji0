"""Unit tests for Trade Ledger and Equity Engine (Sprint 7A)."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from backtesting_engine.core.enums import PositionSide, TradeStatus
from backtesting_engine.core.models import MarketBar, SimulatedFill
from backtesting_engine.equity.equity_engine import EquityEngine
from backtesting_engine.ledger.trade_ledger import TradeLedger


def test_trade_ledger_open_and_close_trade():
    ledger = TradeLedger()
    bar1 = MarketBar(symbol="SOL/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=100.0, high=105.0, low=98.0, close=102.0, volume=100.0)

    fill_buy = SimulatedFill(
        order_id="ord-001",
        symbol="SOL/USDT",
        side=PositionSide.LONG,
        fill_quantity=10.0,
        fill_price=100.0,
        fee=1.0,
        timestamp=bar1.timestamp,
    )

    open_trade = ledger.process_fill(fill_buy, bar1)
    assert open_trade.status == TradeStatus.OPEN
    assert open_trade.quantity == 10.0
    assert open_trade.entry_price == 100.0
    assert len(ledger.get_open_trades()) == 1

    bar2 = MarketBar(symbol="SOL/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc), open=102.0, high=115.0, low=101.0, close=110.0, volume=120.0)
    fill_sell = SimulatedFill(
        order_id="ord-002",
        symbol="SOL/USDT",
        side=PositionSide.SHORT,
        fill_quantity=10.0,
        fill_price=110.0,
        fee=1.1,
        timestamp=bar2.timestamp,
    )

    closed_trade = ledger.process_fill(fill_sell, bar2)
    assert closed_trade.status == TradeStatus.CLOSED
    assert closed_trade.realized_pnl == round((110.0 - 100.0) * 10.0 - (1.0 + 1.1), 4)  # 100.0 - 2.1 = 97.9
    assert len(ledger.get_open_trades()) == 0
    assert len(ledger.get_closed_trades()) == 1


def test_equity_engine_snapshots_and_returns():
    eq_engine = EquityEngine(initial_capital=100000.0)
    ledger = TradeLedger()

    bar1 = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), open=50000.0, high=51000.0, low=49500.0, close=51000.0, volume=10.0)
    fill1 = SimulatedFill(order_id="o1", symbol="BTC/USDT", side=PositionSide.LONG, fill_quantity=1.0, fill_price=50000.0, fee=10.0, timestamp=bar1.timestamp)
    ledger.process_fill(fill1, bar1)

    s1 = eq_engine.update(bar1, ledger)
    assert s1.balance == 100000.0
    assert s1.open_pnl == 1000.0  # (51000 - 50000) * 1
    assert s1.equity == 101000.0

    bar2 = MarketBar(symbol="BTC/USDT", timeframe="1h", timestamp=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc), open=51000.0, high=53000.0, low=50500.0, close=52000.0, volume=15.0)
    s2 = eq_engine.update(bar2, ledger)
    assert s2.equity == 102000.0

    returns = eq_engine.get_returns_series()
    curve = eq_engine.get_equity_curve()

    assert len(returns) == 1
    assert returns[0] == round((102000.0 - 101000.0) / 101000.0, 6)
    assert curve == [101000.0, 102000.0]
