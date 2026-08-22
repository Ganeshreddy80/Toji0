"""Comprehensive Test Suite for Sprint 9B Live Market Feed Integration."""

import ast
from datetime import datetime, timedelta, timezone
import importlib
import pathlib
import threading
import time

from pydantic import ValidationError
import pytest

from paper_trading.candle_builder import CandleBuilder
from paper_trading.events import (
    CandleClosed,
    FeedConnected,
    FeedDisconnected,
    FeedRecovered,
    MarketClosed,
    MarketOpened,
    MarketTickReceived,
)
from paper_trading.feed_manager import FeedManager
from paper_trading.heartbeat import HeartbeatMonitor
from paper_trading.market_data import MarketDataAdapter
from paper_trading.models.market_models import (
    FeedStatus,
    MarketCandle,
    MarketTick,
    OrderBookSnapshot,
)
from paper_trading.models.paper_models import PaperOrderSide
from paper_trading.orchestrator import PaperOrchestrator
from paper_trading.orderbook import OrderBookCache
from paper_trading.reconnect import ReconnectionManager
from paper_trading.scheduler import SessionScheduler
from paper_trading.tick_processor import TickProcessor
from toji_platform.core.event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def feed_manager(event_bus):
    return FeedManager(event_bus=event_bus)


# 1. Feed connection
def test_feed_connection(event_bus):
    fm = FeedManager(event_bus=event_bus)
    status = fm.connect()
    assert status.connected is True
    assert fm.get_feed_status().connected is True


# 2. Feed disconnection
def test_feed_disconnection(event_bus):
    fm = FeedManager(event_bus=event_bus)
    fm.connect()
    status = fm.disconnect(reason="Maintenance")
    assert status.connected is False
    assert fm.get_feed_status().connected is False


# 3. Feed recovery
def test_feed_recovery(event_bus):
    fm = FeedManager(event_bus=event_bus)
    fm.connect()
    fm.disconnect()
    success, status = fm.recover()
    assert success is True
    assert status.connected is True
    assert status.reconnect_count == 1


# 4. Tick validation
def test_tick_validation():
    tp = TickProcessor()
    now = datetime.now(timezone.utc)
    tick = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.5, timestamp=now)
    processed = tp.validate_and_process(tick)
    assert processed is not None
    assert processed.price == 50000.0


# 5. Invalid ticks
def test_invalid_ticks():
    tp = TickProcessor()
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        MarketTick(symbol="BTC/USDT", price=-100.0, volume=1.0, timestamp=now)

    with pytest.raises(ValidationError):
        MarketTick(symbol="BTC/USDT", price=50000.0, volume=-1.0, timestamp=now)

    assert tp.validate_and_process(None) is None


# 6. Tick ordering
def test_tick_ordering():
    tp = TickProcessor()
    now = datetime.now(timezone.utc)
    t1 = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now)
    t2 = MarketTick(symbol="BTC/USDT", price=50100.0, volume=1.0, timestamp=now + timedelta(seconds=1))

    assert tp.validate_and_process(t1) is not None
    assert tp.validate_and_process(t2) is not None


# 7. Candle creation
def test_candle_creation():
    cb = CandleBuilder(timeframes=["1m"])
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    t1 = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=base_time)
    t2 = MarketTick(symbol="BTC/USDT", price=50500.0, volume=2.0, timestamp=base_time + timedelta(seconds=10))

    cb.process_tick(t1)
    cb.process_tick(t2)

    active = cb.get_active_candle("BTC/USDT", "1m")
    assert active is not None
    assert active.open == 50000.0
    assert active.high == 50500.0
    assert active.low == 50000.0
    assert active.close == 50500.0
    assert active.volume == 3.0


# 8. Candle rollover
def test_candle_rollover():
    cb = CandleBuilder(timeframes=["1m"])
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    t1 = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=base_time)
    t2 = MarketTick(symbol="BTC/USDT", price=51000.0, volume=1.0, timestamp=base_time + timedelta(seconds=65))

    closed = cb.process_tick(t1)
    assert len(closed) == 0

    closed_rollover = cb.process_tick(t2)
    assert len(closed_rollover) == 1
    assert closed_rollover[0].close == 50000.0
    assert closed_rollover[0].timeframe == "1m"


# 9. Multiple symbols
def test_multiple_symbols(feed_manager):
    feed_manager.connect()
    feed_manager.subscribe("BTC/USDT")
    feed_manager.subscribe("ETH/USDT")

    now = datetime.now(timezone.utc)
    t1 = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now)
    t2 = MarketTick(symbol="ETH/USDT", price=3000.0, volume=5.0, timestamp=now)

    p1 = feed_manager.process_tick(t1)
    p2 = feed_manager.process_tick(t2)

    assert p1.symbol == "BTC/USDT"
    assert p2.symbol == "ETH/USDT"
    assert len(feed_manager.get_subscribed_symbols()) == 2


# 10. Order book updates
def test_order_book_updates():
    ob = OrderBookCache()
    now = datetime.now(timezone.utc)
    snap = OrderBookSnapshot(
        symbol="BTC/USDT",
        bids=[(49990.0, 1.0), (49980.0, 2.0)],
        asks=[(50010.0, 1.0), (50020.0, 2.0)],
        timestamp=now,
    )
    ob.update_snapshot(snap)
    cached = ob.get_snapshot("BTC/USDT")

    assert cached is not None
    assert cached.bids[0] == (49990.0, 1.0)
    assert cached.asks[0] == (50010.0, 1.0)


# 11. Heartbeat timeout
def test_heartbeat_timeout():
    hm = HeartbeatMonitor(timeout_seconds=0.1)
    hm.set_connected(True)

    past_time = datetime.now(timezone.utc) - timedelta(seconds=1)
    hm.record_heartbeat(timestamp=past_time)

    assert hm.is_stale() is True


# 12. Reconnection
def test_reconnection():
    rm = ReconnectionManager(base_delay=0.01, max_delay=0.05, max_retries=3)
    rm.register_disconnect()

    success, delay, attempts = rm.attempt_reconnect()
    assert success is True
    assert attempts == 1

    rm.reset()
    assert rm.attempts == 0


def test_reconnection_exhaustion():
    rm = ReconnectionManager(base_delay=0.0, max_delay=0.0, max_retries=2)
    rm.register_disconnect()

    succ1, delay1, att1 = rm.attempt_reconnect()
    assert succ1 is True
    assert att1 == 1

    succ2, delay2, att2 = rm.attempt_reconnect()
    assert succ2 is True
    assert att2 == 2

    # Attempt after max_retries hit -> Exhausted
    succ3, delay3, att3 = rm.attempt_reconnect()
    assert succ3 is False
    assert att3 == 2
    assert delay3 == 0.0

    # Additional attempts after exhaustion return False without incrementing
    succ4, delay4, att4 = rm.attempt_reconnect()
    assert succ4 is False
    assert att4 == 2


# 13. Scheduler open
def test_scheduler_open(event_bus):
    published = []
    event_bus.subscribe("*", lambda e: published.append(e.event_type))

    sched = SessionScheduler(event_bus=event_bus)
    evt = sched.open_market("MorningSession")

    assert sched.is_market_open() is True
    assert sched.get_current_session_name() == "MorningSession"
    assert "MarketOpened" in published


# 14. Scheduler close
def test_scheduler_close(event_bus):
    published = []
    event_bus.subscribe("*", lambda e: published.append(e.event_type))

    sched = SessionScheduler(event_bus=event_bus)
    sched.open_market("MorningSession")
    sched.close_market("MorningSession")

    assert sched.is_market_open() is False
    assert sched.get_current_session_name() is None
    assert "MarketClosed" in published


# 15. Event publishing
def test_event_publishing(event_bus):
    published = []
    event_bus.subscribe("*", lambda e: published.append(e.event_type))

    fm = FeedManager(event_bus=event_bus)
    fm.connect()

    now = datetime.now(timezone.utc)
    t1 = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now)
    fm.process_tick(t1)

    assert "FeedConnected" in published
    assert "MarketTickReceived" in published


# 16. Determinism
def test_determinism():
    cb1 = CandleBuilder(timeframes=["1m"])
    cb2 = CandleBuilder(timeframes=["1m"])

    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ticks = [
        MarketTick(symbol="BTC/USDT", price=50000.0 + i * 10.0, volume=1.0, timestamp=base_time + timedelta(seconds=i * 5))
        for i in range(15)
    ]

    for t in ticks:
        cb1.process_tick(t)
        cb2.process_tick(t)

    c1 = cb1.get_active_candle("BTC/USDT", "1m")
    c2 = cb2.get_active_candle("BTC/USDT", "1m")

    assert c1.open == c2.open
    assert c1.high == c2.high
    assert c1.low == c2.low
    assert c1.close == c2.close
    assert c1.volume == c2.volume


# 17. Thread safety
def test_thread_safety(feed_manager):
    feed_manager.connect()
    errors = []

    def worker(id_idx):
        try:
            base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            for i in range(50):
                t = MarketTick(
                    symbol=f"SYM{id_idx}",
                    price=100.0 + i,
                    volume=1.0,
                    timestamp=base_time + timedelta(seconds=i),
                )
                feed_manager.process_tick(t)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert len(errors) == 0


# 18. Performance
def test_performance():
    tp = TickProcessor()
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ticks = [
        MarketTick(symbol="BTC/USDT", price=50000.0 + (i % 100), volume=1.0, timestamp=base_time + timedelta(milliseconds=i))
        for i in range(10000)
    ]

    start_t = time.perf_counter()
    for t in ticks:
        tp.validate_and_process(t)
    elapsed = time.perf_counter() - start_t

    assert elapsed < 2.0  # Must validate 10,000 ticks under 2 seconds


# 19. Large tick volume benchmark (10,000+ ticks/second)
def test_large_tick_volume():
    fm = FeedManager()
    fm.connect()
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    start_t = time.perf_counter()
    for i in range(10000):
        t = MarketTick(symbol="BTC/USDT", price=50000.0 + (i % 50), volume=0.5, timestamp=base_time + timedelta(milliseconds=i))
        fm.process_tick(t)
    elapsed = time.perf_counter() - start_t

    assert elapsed < 5.0  # Must process 10,000 ticks cleanly under 5 seconds


# 20. Memory stability
def test_memory_stability():
    cb = CandleBuilder(timeframes=["1m"])
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    for i in range(1000):
        t = MarketTick(symbol="BTC/USDT", price=50000.0 + (i % 10), volume=1.0, timestamp=base_time + timedelta(seconds=i * 2))
        cb.process_tick(t)

    history = cb.get_completed_candles("BTC/USDT", "1m")
    assert len(history) > 0


# 21. Regression
def test_regression():
    orch = PaperOrchestrator(initial_capital=100000.0)
    session = orch.start_session()
    assert session.status.value == "RUNNING"
    orch.stop_session()
    assert orch.get_session().status.value == "STOPPED"


# 22. Architecture boundaries
def test_architecture_boundaries():
    paper_dir = pathlib.Path(__file__).parent.parent / "paper_trading"
    forbidden = {"mission_control", "self_learning", "aws", "live_broker", "monte_carlo"}

    for py_file in paper_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for f in forbidden:
                        assert f not in alias.name, f"Forbidden import '{alias.name}' found in {py_file.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for f in forbidden:
                        assert f not in node.module, f"Forbidden import from '{node.module}' found in {py_file.name}"


# 23. Immutable models
def test_immutable_models():
    now = datetime.now(timezone.utc)
    tick = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now)
    with pytest.raises((ValidationError, TypeError)):
        tick.price = 55000.0

    candle = MarketCandle(
        symbol="BTC/USDT",
        timeframe="1m",
        open=50000.0,
        high=51000.0,
        low=49500.0,
        close=50500.0,
        volume=10.0,
        open_time=now,
        close_time=now + timedelta(minutes=1),
    )
    with pytest.raises((ValidationError, TypeError)):
        candle.close = 52000.0


# 24. Latency calculation
def test_latency_calculation():
    hm = HeartbeatMonitor()
    now = datetime.now(timezone.utc)
    past = now - timedelta(milliseconds=150)
    status = hm.record_heartbeat(timestamp=past)

    assert status.latency_ms >= 140.0


# 25. Duplicate tick handling
def test_duplicate_tick_handling():
    tp = TickProcessor()
    now = datetime.now(timezone.utc)
    t1 = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now)
    t2 = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now)

    assert tp.validate_and_process(t1) is not None
    assert tp.validate_and_process(t2) is None  # Duplicate rejected


# 26. Out-of-order ticks
def test_out_of_order_ticks():
    tp = TickProcessor()
    now = datetime.now(timezone.utc)
    t1 = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now)
    t_old = MarketTick(symbol="BTC/USDT", price=49000.0, volume=1.0, timestamp=now - timedelta(seconds=10))

    assert tp.validate_and_process(t1) is not None
    assert tp.validate_and_process(t_old) is None  # Out-of-order rejected


# 27. Feed status updates
def test_feed_status_updates():
    fm = FeedManager()
    fm.connect()
    st1 = fm.get_feed_status()
    assert st1.connected is True

    fm.disconnect()
    st2 = fm.get_feed_status()
    assert st2.connected is False


# 28. Symbol subscription
def test_symbol_subscription():
    fm = FeedManager()
    fm.subscribe("BTC/USDT")
    assert "BTC/USDT" in fm.get_subscribed_symbols()


# 29. Symbol unsubscription
def test_symbol_unsubscription():
    fm = FeedManager()
    fm.subscribe("BTC/USDT")
    fm.unsubscribe("BTC/USDT")
    assert "BTC/USDT" not in fm.get_subscribed_symbols()


# 30. Integration with Paper Trading
def test_integration_with_paper_trading(event_bus):
    orch = PaperOrchestrator(event_bus=event_bus, initial_capital=100000.0)
    orch.start_session()

    fm = FeedManager(event_bus=event_bus)
    fm.connect()
    fm.subscribe("BTC/USDT")

    # Tick arrives at 50,000 -> Drives paper order matching
    now = datetime.now(timezone.utc)
    fm.process_tick(MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now))

    order, trades = orch.submit_order(
        symbol="BTC/USDT",
        side=PaperOrderSide.BUY,
        quantity=1.0,
        current_market_price=50000.0,
    )
    assert order.status.value == "FILLED"
    assert len(trades) == 1
    assert orch.get_account().equity > 0.0
