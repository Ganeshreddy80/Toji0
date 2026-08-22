"""Comprehensive Test Suite for Sprint 9C Paper Trading Validation & Long-Running Stability."""

import ast
from datetime import datetime, timedelta, timezone
import pathlib
import threading
import time

from pydantic import ValidationError
import pytest

from paper_trading.candle_builder import CandleBuilder
from paper_trading.events import CandleClosed, FeedConnected, MarketTickReceived, PaperOrderFilled
from paper_trading.feed_manager import FeedManager
from paper_trading.heartbeat import HeartbeatMonitor
from paper_trading.market_data import MarketDataAdapter
from paper_trading.models.market_models import MarketTick
from paper_trading.models.paper_models import PaperOrderSide
from paper_trading.orchestrator import PaperOrchestrator
from paper_trading.reconnect import ReconnectionManager
from paper_trading.validation.endurance import EnduranceHarness
from paper_trading.validation.fault_injection import FaultInjector
from paper_trading.validation.latency_monitor import LatencyMonitor
from paper_trading.validation.memory_monitor import MemoryMonitor
from paper_trading.validation.metrics import MetricsCollector, OperationalMetrics
from paper_trading.validation.profiler import PerformanceProfiler
from paper_trading.validation.recovery_validator import RecoveryValidator
from paper_trading.validation.replay_validator import ReplayValidator
from paper_trading.validation.report import ReportGenerator, ValidationReport
from toji_platform.core.event_bus import InMemoryEventBus


# 1. Endurance startup
def test_endurance_startup():
    harness = EnduranceHarness(duration_config="1h")
    assert harness.is_running() is False
    harness.start()
    assert harness.is_running() is True
    harness.stop()


# 2. Endurance shutdown
def test_endurance_shutdown():
    harness = EnduranceHarness(duration_config="1h")
    harness.start()
    assert harness.is_running() is True
    harness.stop()
    assert harness.is_running() is False


# 3. Long-running simulation
def test_long_running_simulation():
    harness = EnduranceHarness(duration_config="1h")
    report = harness.run_simulation(tick_count=50)
    assert report is not None
    assert report.passed is True
    assert report.metrics.processed_ticks_count > 0


# 4. Memory growth
def test_memory_growth():
    mm = MemoryMonitor()
    mm.start()
    for _ in range(5):
        mm.record_sample()
    growth = mm.get_allocation_growth_mb()
    assert growth >= 0.0
    mm.stop()


# 5. Memory leak detection
def test_memory_leak_detection():
    mm = MemoryMonitor()
    mm.start()
    mm._samples = [
        (datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc), 10.0),
        (datetime(2026, 1, 1, 12, 0, 10, tzinfo=timezone.utc), 50.0),
    ]
    is_leak, rate = mm.check_memory_leak(growth_rate_threshold_mb_per_sec=1.0)
    assert is_leak is True
    assert rate == 4.0
    mm.stop()


# 6. Latency statistics
def test_latency_statistics():
    lm = LatencyMonitor()
    for val in [10.0, 20.0, 30.0, 40.0, 50.0]:
        lm.record_processing_latency(val)

    stats = lm.get_summary_stats("processing")
    assert stats["count"] == 5.0
    assert stats["average"] == 30.0
    assert stats["maximum"] == 50.0


# 7. p95 calculation
def test_p95_calculation():
    lm = LatencyMonitor()
    vals = [float(i) for i in range(1, 101)]
    for v in vals:
        lm.record_processing_latency(v)

    stats = lm.get_summary_stats("processing")
    assert stats["p95"] >= 94.0


# 8. p99 calculation
def test_p99_calculation():
    lm = LatencyMonitor()
    vals = [float(i) for i in range(1, 101)]
    for v in vals:
        lm.record_processing_latency(v)

    stats = lm.get_summary_stats("processing")
    assert stats["p99"] >= 98.0


# 9. Recovery timing
def test_recovery_timing():
    rv = RecoveryValidator()
    fm = FeedManager()
    is_valid, elapsed = rv.test_single_recovery(fm)
    assert is_valid is True
    assert elapsed >= 0.0


# 10. Recovery correctness
def test_recovery_correctness():
    fm = FeedManager()
    fm.connect()
    fm.disconnect(reason="Test")
    success, status = fm.recover()
    assert success is True
    assert status.connected is True
    assert status.reconnect_count == 1


# 11. Disconnect handling
def test_disconnect_handling():
    fm = FeedManager()
    fm.connect()
    status = fm.disconnect(reason="Manual Disconnect")
    assert status.connected is False
    assert fm.get_feed_status().connected is False


# 12. Reconnect handling
def test_reconnect_handling():
    rm = ReconnectionManager(base_delay=0.0, max_delay=0.0, max_retries=3)
    rm.register_disconnect()
    success, delay, attempts = rm.attempt_reconnect()
    assert success is True
    assert attempts == 1


# 13. Replay determinism
def test_replay_determinism():
    rv = ReplayValidator()
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ticks = [
        MarketTick(symbol="BTC/USDT", price=50000.0 + i, volume=1.0, timestamp=base_time + timedelta(seconds=i * 5))
        for i in range(20)
    ]
    res = rv.validate_full_replay(ticks)
    assert res["overall_deterministic"] is True


# 14. Fault injection
def test_fault_injection():
    fi = FaultInjector(seed=123)
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    valid_ticks = [
        MarketTick(symbol="BTC/USDT", price=50000.0 + i, volume=1.0, timestamp=base_time + timedelta(seconds=i))
        for i in range(10)
    ]
    faulty_stream = fi.inject_faults_into_stream(valid_ticks, fault_ratio=0.5)
    assert len(faulty_stream) > len(valid_ticks)


# 15. Duplicate ticks
def test_duplicate_ticks():
    fi = FaultInjector()
    now = datetime.now(timezone.utc)
    t1 = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now)
    dup = fi.generate_duplicate_tick(t1)
    assert dup.price == t1.price
    assert dup.timestamp == t1.timestamp


# 16. Malformed ticks
def test_malformed_ticks():
    fi = FaultInjector()
    malformed = fi.generate_malformed_ticks(symbol="BTC/USDT")
    assert len(malformed) > 0


# 17. Out-of-order ticks
def test_out_of_order_ticks():
    fi = FaultInjector()
    now = datetime.now(timezone.utc)
    old_tick = fi.generate_out_of_order_tick("BTC/USDT", now, seconds_back=30.0)
    assert old_tick.timestamp < now


# 18. Missing heartbeat
def test_missing_heartbeat():
    hm = HeartbeatMonitor(timeout_seconds=0.1)
    hm.set_connected(True)
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    hm.record_heartbeat(timestamp=past)
    assert hm.is_stale() is True


# 19. Metrics collection
def test_metrics_collection():
    mc = MetricsCollector()
    mc.record_tick()
    mc.record_candle()
    mc.record_order()
    mc.record_fill()
    mc.record_reconnect()
    mc.record_error()

    snap = mc.get_metrics_snapshot()
    assert snap.processed_ticks_count == 1
    assert snap.completed_candles_count == 1
    assert snap.submitted_orders_count == 1
    assert snap.executed_fills_count == 1
    assert snap.reconnect_count == 1
    assert snap.error_count == 1


# 20. Report generation
def test_report_generation():
    report = ReportGenerator.build_report(
        simulation_name="TestSim",
        duration_seconds=3600.0,
        passed=True,
    )
    assert report.simulation_name == "TestSim"
    assert report.passed is True
    json_str = ReportGenerator.export_report_json(report)
    assert "TestSim" in json_str


# 21. Immutable reports
def test_immutable_reports():
    report = ReportGenerator.build_report(
        simulation_name="TestSim",
        duration_seconds=3600.0,
        passed=True,
    )
    with pytest.raises((ValidationError, TypeError)):
        report.passed = False


# 22. Thread safety
def test_thread_safety():
    lm = LatencyMonitor()
    mc = MetricsCollector()
    errors = []

    def worker(id_idx):
        try:
            for i in range(50):
                lm.record_processing_latency(float(i))
                mc.record_tick()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert len(errors) == 0
    assert mc.get_metrics_snapshot().processed_ticks_count == 250


# 23. Performance & Throughput target benchmark
def test_performance():
    prof = PerformanceProfiler()
    fm = FeedManager()
    fm.connect()
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ticks = [
        MarketTick(symbol="BTC/USDT", price=50000.0 + (i % 20), volume=1.0, timestamp=base_time + timedelta(milliseconds=i))
        for i in range(10000)
    ]

    start_t = time.perf_counter()
    for t in ticks:
        fm.process_tick(t)
    elapsed = time.perf_counter() - start_t

    throughput = prof.calculate_throughput(len(ticks), elapsed)
    assert elapsed < 5.0  # Must process 10,000 ticks cleanly under 5 seconds
    assert throughput > 1000.0  # High throughput verified


# 24. Stress testing
def test_stress_testing():
    fm = FeedManager()
    fm.connect()
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    for i in range(2000):
        t = MarketTick(symbol="BTC/USDT", price=50000.0 + (i % 10), volume=1.0, timestamp=base_time + timedelta(milliseconds=i))
        fm.process_tick(t)

    status = fm.get_feed_status()
    assert status.connected is True


# 25. Regression
def test_regression():
    orch = PaperOrchestrator(initial_capital=100000.0)
    session = orch.start_session()
    assert session.status.value == "RUNNING"
    orch.stop_session()
    assert orch.get_session().status.value == "STOPPED"


# 26. Sprint 9A compatibility
def test_sprint9a_compatibility():
    orch = PaperOrchestrator(initial_capital=100000.0)
    orch.start_session()
    order, trades = orch.submit_order(
        symbol="BTC/USDT",
        side=PaperOrderSide.BUY,
        quantity=1.0,
        current_market_price=50000.0,
    )
    assert order.status.value == "FILLED"
    assert len(trades) == 1


# 27. Sprint 9B compatibility
def test_sprint9b_compatibility():
    fm = FeedManager()
    fm.connect()
    fm.subscribe("BTC/USDT")
    now = datetime.now(timezone.utc)
    tick = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now)
    processed = fm.process_tick(tick)
    assert processed is not None
    assert "BTC/USDT" in fm.get_subscribed_symbols()


# 28. Bounded memory
def test_bounded_memory():
    cb = CandleBuilder(timeframes=["1m"], max_completed_candles=5)
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    for i in range(20):
        t = MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=base_time + timedelta(seconds=i * 65))
        cb.process_tick(t)

    completed = cb.get_completed_candles("BTC/USDT", "1m")
    assert len(completed) == 5  # Strictly capped at max_completed_candles


# 29. Error counting
def test_error_counting():
    mc = MetricsCollector()
    mc.record_error()
    mc.record_error()
    assert mc.get_metrics_snapshot().error_count == 2


# 30. Uptime tracking
def test_uptime_tracking():
    mc = MetricsCollector()
    time.sleep(0.01)
    uptime = mc.get_uptime_seconds()
    assert uptime > 0.0


# 31. Event consistency
def test_event_consistency():
    bus = InMemoryEventBus()
    events = []
    bus.subscribe("MarketTickReceived", lambda e: events.append(e.event_type))

    fm = FeedManager(event_bus=bus)
    fm.connect()
    now = datetime.now(timezone.utc)
    fm.process_tick(MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=now))
    assert len(events) == 1


# 32. Fill consistency
def test_fill_consistency():
    rv = ReplayValidator()
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ticks = [MarketTick(symbol="BTC/USDT", price=50000.0, volume=1.0, timestamp=base_time)]
    orders = [{"side": PaperOrderSide.BUY, "quantity": 1.0, "trigger_price": 50000.0}]
    assert rv.verify_fill_replay(ticks, orders) is True


# 33. Candle consistency
def test_candle_consistency():
    rv = ReplayValidator()
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ticks = [
        MarketTick(symbol="BTC/USDT", price=50000.0 + i, volume=1.0, timestamp=base_time + timedelta(seconds=i * 10))
        for i in range(10)
    ]
    assert rv.verify_candle_replay(ticks) is True


# 34. Recovery after repeated failures
def test_recovery_after_repeated_failures():
    rv = RecoveryValidator()
    res = rv.test_repeated_failures(failure_count=3)
    assert res["successful_recoveries"] == 3.0
    assert res["state_clean"] == 1.0


# 35. Architecture boundaries
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
