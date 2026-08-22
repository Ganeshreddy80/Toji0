"""Thread-safe Endurance Test Harness for Sprint 9C Paper Trading Validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from paper_trading.feed_manager import FeedManager
from paper_trading.models.market_models import MarketTick
from paper_trading.orchestrator import PaperOrchestrator
from paper_trading.validation.fault_injection import FaultInjector
from paper_trading.validation.latency_monitor import LatencyMonitor
from paper_trading.validation.memory_monitor import MemoryMonitor
from paper_trading.validation.metrics import MetricsCollector
from paper_trading.validation.report import ReportGenerator, ValidationReport
from toji_platform.core.event_bus import InMemoryEventBus

logger = logging.getLogger(__name__)

DURATION_MAP: Dict[str, float] = {
    "1h": 3600.0,
    "6h": 21600.0,
    "24h": 86400.0,
    "72h": 259200.0,
}


class EnduranceHarness:
    """Thread-safe Endurance Test Harness driving long-running paper trading simulation validation."""

    def __init__(
        self,
        duration_config: str = "1h",
        time_compression_ratio: float = 1.0,
        enable_fault_injection: bool = False,
    ) -> None:
        self._lock = threading.RLock()
        self._duration_config = duration_config
        self._duration_seconds = DURATION_MAP.get(duration_config, 3600.0)
        self._time_compression = max(1.0, time_compression_ratio)
        self._enable_faults = enable_fault_injection

        self._is_running: bool = False
        self._exceptions: List[Exception] = []

        self._event_bus = InMemoryEventBus()
        self._metrics = MetricsCollector()
        self._memory_monitor = MemoryMonitor()
        self._latency_monitor = LatencyMonitor()
        self._fault_injector = FaultInjector()

        self._feed_manager = FeedManager(event_bus=self._event_bus)
        self._orchestrator = PaperOrchestrator(event_bus=self._event_bus, initial_capital=100000.0)

        # Wire up event counters
        self._event_bus.subscribe("MarketTickReceived", lambda e: self._metrics.record_tick())
        self._event_bus.subscribe("CandleClosed", lambda e: self._metrics.record_candle())
        self._event_bus.subscribe("PaperOrderSubmitted", lambda e: self._metrics.record_order())
        self._event_bus.subscribe("PaperOrderFilled", lambda e: self._metrics.record_fill())
        self._event_bus.subscribe("FeedRecovered", lambda e: self._metrics.record_reconnect())

    def start(self) -> None:
        """Start endurance test harness components."""
        with self._lock:
            if not self._is_running:
                self._is_running = True
                self._exceptions.clear()
                self._metrics.reset()
                self._memory_monitor.start()
                self._latency_monitor.reset()
                self._feed_manager.connect()
                self._orchestrator.start_session()
                logger.info("EnduranceHarness STARTED (duration: %s)", self._duration_config)

    def stop(self) -> None:
        """Stop endurance test harness components."""
        with self._lock:
            if self._is_running:
                self._feed_manager.disconnect()
                self._orchestrator.stop_session()
                self._memory_monitor.stop()
                self._is_running = False
                logger.info("EnduranceHarness STOPPED")

    def is_running(self) -> bool:
        """Get running status flag."""
        with self._lock:
            return self._is_running

    def record_exception(self, exc: Exception) -> None:
        """Record an exception during endurance execution."""
        with self._lock:
            self._exceptions.append(exc)
            self._metrics.record_error()
            logger.error("EnduranceHarness exception recorded: %s", exc)

    def run_simulation(
        self,
        tick_count: int = 100,
        symbol: str = "BTC/USDT",
    ) -> ValidationReport:
        """Execute a simulated endurance run of tick_count ticks and return a ValidationReport."""
        self.start()
        base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        try:
            for i in range(tick_count):
                if not self.is_running():
                    break

                ts = base_time + timedelta(seconds=i * 2)
                price = 50000.0 + (i % 20) * 5.0
                tick = MarketTick(symbol=symbol, price=price, volume=1.0, timestamp=ts)

                t0 = time.perf_counter()
                processed = self._feed_manager.process_tick(tick)
                proc_lat = (time.perf_counter() - t0) * 1000.0
                self._latency_monitor.record_processing_latency(proc_lat)

                if i % 10 == 0:
                    self._memory_monitor.record_sample()

                if self._enable_faults and i % 25 == 0:
                    malformed = self._fault_injector.generate_malformed_ticks(symbol=symbol)
                    for mf in malformed:
                        if mf is not None:
                            self._feed_manager.process_tick(mf)

        except Exception as e:
            self.record_exception(e)
        finally:
            self.stop()

        is_leak, growth_rate = self._memory_monitor.check_memory_leak()
        latency_stats = self._latency_monitor.get_all_summary_stats()
        metrics_snapshot = self._metrics.get_metrics_snapshot(latency_summary=latency_stats)

        passed = (len(self._exceptions) == 0) and (not is_leak)

        stats = {
            "exceptions_count": len(self._exceptions),
            "memory_stats": self._memory_monitor.get_stats(),
            "latency_stats": latency_stats,
            "processed_ticks": metrics_snapshot.processed_ticks_count,
            "completed_candles": metrics_snapshot.completed_candles_count,
        }

        return ReportGenerator.build_report(
            simulation_name=f"Endurance_{self._duration_config}",
            duration_seconds=self._duration_seconds,
            passed=passed,
            metrics=metrics_snapshot,
            statistics=stats,
        )
