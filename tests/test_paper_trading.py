"""Comprehensive Test Suite for Sprint 9A Paper Trading Foundation."""

from datetime import datetime, timezone
import importlib
import threading
import time

from pydantic import ValidationError
import pytest

from paper_trading.broker import PaperBroker
from paper_trading.events import PaperOrderSubmitted, PaperTradeExecuted
from paper_trading.models.paper_models import (
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    PaperPosition,
    PaperSession,
    PaperSessionStatus,
    PaperTrade,
)
from paper_trading.orchestrator import PaperOrchestrator
from paper_trading.orders import PaperOrderEngine
from paper_trading.plugin import PaperTradingPlugin
from paper_trading.portfolio import PaperPortfolio
from paper_trading.repository import PaperRepository
from paper_trading.session import PaperSessionManager
from paper_trading.state import PaperState
from toji_platform.core.event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return PaperOrchestrator(event_bus=event_bus, initial_capital=100000.0)


# 1. Account creation
def test_account_creation():
    portfolio = PaperPortfolio(initial_capital=50000.0)
    account = portfolio.get_account_snapshot()
    assert account.starting_cash == 50000.0
    assert account.available_cash == 50000.0
    assert account.reserved_cash == 0.0
    assert account.equity == 50000.0
    assert account.realized_pnl == 0.0
    assert account.unrealized_pnl == 0.0


# 2. Cash updates
def test_cash_updates():
    portfolio = PaperPortfolio(initial_capital=100000.0)
    order = PaperOrder(
        symbol="BTC/USDT",
        side=PaperOrderSide.BUY,
        quantity=1.0,
        order_type=PaperOrderType.LIMIT,
        limit_price=40000.0,
    )
    assert portfolio.reserve_cash_for_order(order) is True
    snap = portfolio.get_account_snapshot()
    assert snap.available_cash == 60000.0
    assert snap.reserved_cash == 40000.0

    portfolio.release_reserved_cash(order)
    snap2 = portfolio.get_account_snapshot()
    assert snap2.available_cash == 100000.0
    assert snap2.reserved_cash == 0.0


# 3. Position updates
def test_position_updates():
    portfolio = PaperPortfolio(initial_capital=100000.0)
    pos = portfolio.update_market_price("BTC/USDT", 50000.0)
    assert pos is None  # No position open yet

    order = PaperOrder(symbol="BTC/USDT", side=PaperOrderSide.BUY, quantity=2.0)
    trade = PaperTrade(order_id=order.order_id, symbol="BTC/USDT", quantity=2.0, fill_price=50000.0)
    account, position = portfolio.apply_fill(order, trade)

    assert position.quantity == 2.0
    assert position.average_price == 50000.0

    updated_pos = portfolio.update_market_price("BTC/USDT", 55000.0)
    assert updated_pos.unrealized_pnl == 10000.0
    assert updated_pos.market_value == 110000.0


# 4. Buy orders
def test_buy_orders(orchestrator):
    order, trades = orchestrator.submit_order(
        symbol="BTC/USDT",
        side=PaperOrderSide.BUY,
        quantity=1.0,
        order_type=PaperOrderType.MARKET,
        current_market_price=50000.0,
    )
    assert order.status == PaperOrderStatus.FILLED
    assert len(trades) == 1
    assert trades[0].quantity == 1.0
    assert trades[0].fill_price == 50000.0


# 5. Sell orders
def test_sell_orders(orchestrator):
    # First BUY to open long position
    orchestrator.submit_order(
        symbol="BTC/USDT",
        side=PaperOrderSide.BUY,
        quantity=2.0,
        order_type=PaperOrderType.MARKET,
        current_market_price=50000.0,
    )
    # SELL to close half position at profit
    order_sell, trades_sell = orchestrator.submit_order(
        symbol="BTC/USDT",
        side=PaperOrderSide.SELL,
        quantity=1.0,
        order_type=PaperOrderType.MARKET,
        current_market_price=60000.0,
    )
    assert order_sell.status == PaperOrderStatus.FILLED
    pos = orchestrator.get_position("BTC/USDT")
    assert pos.quantity == 1.0
    assert orchestrator.get_account().realized_pnl > 0.0


# 6. Market orders
def test_market_orders(orchestrator):
    order, trades = orchestrator.submit_order(
        symbol="ETH/USDT",
        side=PaperOrderSide.BUY,
        quantity=10.0,
        order_type=PaperOrderType.MARKET,
        current_market_price=3000.0,
    )
    assert order.status == PaperOrderStatus.FILLED
    assert order.filled_quantity == 10.0


# 7. Limit orders
def test_limit_orders(orchestrator):
    # Submit BUY limit below market
    order, trades = orchestrator.submit_order(
        symbol="BTC/USDT",
        side=PaperOrderSide.BUY,
        quantity=1.0,
        order_type=PaperOrderType.LIMIT,
        limit_price=45000.0,
        current_market_price=50000.0,
    )
    assert order.status == PaperOrderStatus.PENDING
    assert len(trades) == 0

    # Trigger fill via market tick
    fills = orchestrator.on_market_price_tick("BTC/USDT", 44000.0)
    assert len(fills) == 1
    filled_order, trade = fills[0]
    assert filled_order.status == PaperOrderStatus.FILLED
    assert trade.fill_price == 44000.0


# 8. Stop orders
def test_stop_orders(orchestrator):
    order, trades = orchestrator.submit_order(
        symbol="BTC/USDT",
        side=PaperOrderSide.BUY,
        quantity=1.0,
        order_type=PaperOrderType.STOP,
        stop_price=55000.0,
        current_market_price=50000.0,
    )
    assert order.status == PaperOrderStatus.PENDING

    # Market rises above stop price -> triggers fill
    fills = orchestrator.on_market_price_tick("BTC/USDT", 56000.0)
    assert len(fills) == 1
    assert fills[0][0].status == PaperOrderStatus.FILLED


# 9. Partial fills
def test_partial_fills():
    engine = PaperOrderEngine()
    order = engine.create_order("BTC/USDT", PaperOrderSide.BUY, 2.0, PaperOrderType.LIMIT, limit_price=50000.0)
    updated = engine.update_order_status(order.order_id, PaperOrderStatus.PARTIALLY_FILLED, filled_qty=1.0, avg_fill_price=50000.0)
    assert updated.status == PaperOrderStatus.PARTIALLY_FILLED
    assert updated.filled_quantity == 1.0


# 10. Full fills
def test_full_fills(orchestrator):
    order, trades = orchestrator.submit_order(
        symbol="BTC/USDT",
        side=PaperOrderSide.BUY,
        quantity=1.0,
        current_market_price=50000.0,
    )
    assert order.status == PaperOrderStatus.FILLED
    assert order.filled_quantity == 1.0


# 11. Cancelled orders
def test_cancelled_orders(orchestrator):
    order, _ = orchestrator.submit_order(
        symbol="BTC/USDT",
        side=PaperOrderSide.BUY,
        quantity=1.0,
        order_type=PaperOrderType.LIMIT,
        limit_price=40000.0,
        current_market_price=50000.0,
    )
    cancelled = orchestrator.cancel_order(order.order_id)
    assert cancelled.status == PaperOrderStatus.CANCELLED
    assert orchestrator.get_account().reserved_cash == 0.0


# 12. Rejected orders
def test_rejected_orders(orchestrator):
    # Attempt order exceeding available cash
    order, _ = orchestrator.submit_order(
        symbol="BTC/USDT",
        side=PaperOrderSide.BUY,
        quantity=10.0,
        order_type=PaperOrderType.LIMIT,
        limit_price=50000.0,  # Required cash 500,000 > 100,000 available
        current_market_price=60000.0,
    )
    assert order.status == PaperOrderStatus.REJECTED


# 13. Session lifecycle
def test_session_lifecycle(event_bus):
    sm = PaperSessionManager(event_bus=event_bus)
    acc = PaperAccount(starting_cash=100000.0, available_cash=100000.0, buying_power=100000.0, equity=100000.0)

    session = sm.start_session(acc)
    assert session.status == PaperSessionStatus.RUNNING

    stopped = sm.stop_session()
    assert stopped.status == PaperSessionStatus.STOPPED


# 14. Event publishing
def test_event_publishing(event_bus):
    published = []
    event_bus.subscribe("*", lambda e: published.append(e.event_type))

    orchestrator = PaperOrchestrator(event_bus=event_bus)
    orchestrator.start_session()
    orchestrator.submit_order("BTC/USDT", PaperOrderSide.BUY, 1.0, current_market_price=50000.0)

    assert "PaperSessionStarted" in published
    assert "PaperOrderSubmitted" in published
    assert "PaperTradeExecuted" in published
    assert "PaperOrderFilled" in published
    assert "PaperAccountUpdated" in published


# 15. Repository persistence
def test_repository_persistence():
    repo = PaperRepository()
    acc = PaperAccount(starting_cash=100000.0, available_cash=100000.0, buying_power=100000.0, equity=100000.0)
    repo.save_account(acc)
    assert repo.load_account().starting_cash == 100000.0

    pos = PaperPosition(symbol="BTC/USDT", quantity=1.0, average_price=50000.0, market_price=50000.0, market_value=50000.0)
    repo.save_position(pos)
    assert repo.load_position("BTC/USDT").quantity == 1.0


# 16. Thread safety
def test_thread_safety(orchestrator):
    errors = []

    def worker():
        try:
            for _ in range(50):
                orchestrator.submit_order(
                    symbol="BTC/USDT",
                    side=PaperOrderSide.BUY,
                    quantity=0.01,
                    current_market_price=50000.0,
                )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(orchestrator.list_orders()) == 250


# 17. Determinism
def test_determinism():
    orch1 = PaperOrchestrator(initial_capital=100000.0)
    orch2 = PaperOrchestrator(initial_capital=100000.0)

    o1, t1 = orch1.submit_order("BTC/USDT", PaperOrderSide.BUY, 1.0, current_market_price=50000.0, order_id="ord-fixed-1")
    o2, t2 = orch2.submit_order("BTC/USDT", PaperOrderSide.BUY, 1.0, current_market_price=50000.0, order_id="ord-fixed-2")

    assert orch1.get_account().equity == orch2.get_account().equity
    assert t1[0].fill_price == t2[0].fill_price


# 18. Duplicate order protection
def test_duplicate_order_protection(orchestrator):
    o1, _ = orchestrator.submit_order("BTC/USDT", PaperOrderSide.BUY, 1.0, current_market_price=50000.0, order_id="dup-1")
    assert o1.order_id == "dup-1"

    with pytest.raises(ValueError, match="Duplicate order protection"):
        orchestrator.submit_order("BTC/USDT", PaperOrderSide.BUY, 1.0, current_market_price=50000.0, order_id="dup-1")


# 19. Invalid orders
def test_invalid_orders(orchestrator):
    with pytest.raises(ValueError):
        orchestrator.submit_order("BTC/USDT", PaperOrderSide.BUY, -1.0)

    with pytest.raises(ValueError):
        orchestrator.submit_order("BTC/USDT", PaperOrderSide.BUY, 1.0, PaperOrderType.LIMIT, limit_price=0.0)


# 20. Large order volume benchmark (10,000+ orders)
def test_large_order_volume():
    repo = PaperRepository(max_cache_size=1000)
    start_time = time.perf_counter()

    for i in range(10000):
        o = PaperOrder(symbol="BTC/USDT", side=PaperOrderSide.BUY, quantity=1.0, status=PaperOrderStatus.FILLED)
        repo.save_order(o)

    elapsed = time.perf_counter() - start_time
    assert elapsed < 5.0  # Must process 10,000 orders cleanly under 5 seconds
    assert len(repo.list_orders()) == 1000  # Bounded cache capped at 1000


# 21. Portfolio valuation
def test_portfolio_valuation():
    portfolio = PaperPortfolio(initial_capital=100000.0)
    order = PaperOrder(symbol="BTC/USDT", side=PaperOrderSide.BUY, quantity=1.0)
    trade = PaperTrade(order_id=order.order_id, symbol="BTC/USDT", quantity=1.0, fill_price=50000.0)
    portfolio.apply_fill(order, trade)

    portfolio.update_market_price("BTC/USDT", 60000.0)
    snap = portfolio.get_account_snapshot()
    assert snap.equity == 110000.0


# 22. Equity updates
def test_equity_updates(orchestrator):
    orchestrator.submit_order("BTC/USDT", PaperOrderSide.BUY, 1.0, current_market_price=50000.0)
    orchestrator.on_market_price_tick("BTC/USDT", 55000.0)
    # BUY fill cost: 50,000 + 50 commission = 50,050. Cash = 49,950. Position value = 55,000. Equity = 104,950.
    assert orchestrator.get_account().equity == 104950.0


# 23. Realized PnL
def test_realized_pnl(orchestrator):
    orchestrator.submit_order("BTC/USDT", PaperOrderSide.BUY, 1.0, current_market_price=50000.0)
    orchestrator.submit_order("BTC/USDT", PaperOrderSide.SELL, 1.0, current_market_price=55000.0)
    assert orchestrator.get_account().realized_pnl > 0.0


# 24. Unrealized PnL
def test_unrealized_pnl(orchestrator):
    orchestrator.submit_order("BTC/USDT", PaperOrderSide.BUY, 1.0, current_market_price=50000.0)
    orchestrator.on_market_price_tick("BTC/USDT", 48000.0)
    assert orchestrator.get_account().unrealized_pnl == -2000.0


# 25. Buying power
def test_buying_power(orchestrator):
    snap = orchestrator.get_account()
    assert snap.buying_power == 100000.0


# 26. Atomic persistence
def test_atomic_persistence():
    repo = PaperRepository()
    acc = PaperAccount(starting_cash=100000.0, available_cash=100000.0, buying_power=100000.0, equity=100000.0)
    repo.save_account(acc)
    assert repo.load_account() == acc


# 27. Bounded cache
def test_bounded_cache():
    repo = PaperRepository(max_cache_size=5)
    for i in range(10):
        repo.save_order(PaperOrder(symbol="BTC/USDT", side=PaperOrderSide.BUY, quantity=1.0))
    assert len(repo.list_orders()) == 5


# 28. Regression
def test_regression(orchestrator):
    session = orchestrator.start_session()
    assert session.status == PaperSessionStatus.RUNNING
    orchestrator.stop_session()
    assert orchestrator.get_session().status == PaperSessionStatus.STOPPED


# 29. Architecture boundaries
def test_architecture_boundaries():
    plugin_module = importlib.import_module("paper_trading.plugin")
    forbidden = ["mission_control", "self_learning", "aws", "live_broker", "monte_carlo"]
    for attr in dir(plugin_module):
        obj = getattr(plugin_module, attr)
        mod_name = getattr(obj, "__module__", "")
        for f in forbidden:
            assert f not in mod_name


# 30. Immutable models
def test_immutable_models():
    acc = PaperAccount(starting_cash=100000.0, available_cash=100000.0, buying_power=100000.0, equity=100000.0)
    with pytest.raises((ValidationError, TypeError)):
        acc.available_cash = 50000.0

    pos = PaperPosition(symbol="BTC/USDT", quantity=1.0, average_price=50000.0, market_price=50000.0, market_value=50000.0)
    with pytest.raises((ValidationError, TypeError)):
        pos.quantity = 2.0
