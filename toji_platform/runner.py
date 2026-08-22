"""TOJI Live Runner — production-style runtime entry point.

Boots the core 12-plugin kernel, initializes trade journal, event journal,
metrics service, and market data manager, and manages background plugin recovery.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.boot import boot_kernel
from toji_platform.kernel import TojiKernel
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from toji_platform.services.trade_journal import TradeJournal
from toji_platform.services.replay_journal import ReplayJournal
from toji_platform.services.metrics_service import MetricsService
from toji_platform.services.market_data_manager import MarketDataManager

logger = logging.getLogger("toji.runner")


class RecoveryManager:
    """Monitors plugin health status and attempts automated recovery for failed components."""

    def __init__(self, kernel: TojiKernel, check_interval_sec: float = 15.0, max_retries: int = 3) -> None:
        self._kernel = kernel
        self._interval = check_interval_sec
        self._max_retries = max_retries
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._retries: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="RecoveryManager"
        )
        self._thread.start()
        logger.info("Plugin Recovery Manager started ✓ (interval=%.1fs)", self._interval)

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        logger.info("Plugin Recovery Manager stopped ✓")

    def _monitor_loop(self) -> None:
        while self._running:
            if self._stop_event.wait(self._interval):
                break
            if not self._running:
                break
            try:
                self._check_and_recover()
            except Exception as e:
                logger.error("RecoveryManager: error checking/recovering components: %s", e)

    def _check_and_recover(self) -> None:
        health_status = self._kernel.health_check()
        for component_name, status in health_status.items():
            if status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED):
                # Try resolving if it is a plugin
                pm = self._kernel.plugin_manager
                plugin_id = PluginId(component_name)
                try:
                    plugin = pm.get(plugin_id)
                except Exception:
                    # Not a plugin or not found
                    continue

                if plugin.state == ModuleState.FAILED or status == HealthStatus.UNHEALTHY:
                    self._attempt_plugin_recovery(plugin_id, plugin)

    def _attempt_plugin_recovery(self, plugin_id: PluginId, plugin: Any) -> None:
        with self._lock:
            pid_str = str(plugin_id)
            retries = self._retries.get(pid_str, 0)
            if retries >= self._max_retries:
                logger.error(
                    "RecoveryManager: %s exceeded max retries (%d). Marking as permanently FAILED.",
                    pid_str, self._max_retries
                )
                return

            self._retries[pid_str] = retries + 1
            logger.warning(
                "RecoveryManager: Attempting recovery for plugin %s (Attempt %d/%d)...",
                pid_str, retries + 1, self._max_retries
            )

        try:
            # Shutdown and re-initialize plugin
            logger.info("RecoveryManager: Shutting down %s...", pid_str)
            plugin.shutdown()
            
            logger.info("RecoveryManager: Re-initializing %s...", pid_str)
            plugin.initialize()
            
            # Reset retry counter on success
            with self._lock:
                self._retries[pid_str] = 0
            logger.info("RecoveryManager: Plugin %s recovered successfully! ✓", pid_str)
        except Exception as e:
            logger.error("RecoveryManager: Failed to recover plugin %s: %s", pid_str, e)


class LiveRunner:
    """Continuous runtime entry point for Live Paper Trading."""

    def __init__(self, config_overrides: Optional[dict[str, Any]] = None) -> None:
        self._config_overrides = config_overrides or {}
        self._kernel: Optional[TojiKernel] = None
        self._recovery_mgr: Optional[RecoveryManager] = None
        self._trade_journal: Optional[TradeJournal] = None
        self._replay_journal: Optional[ReplayJournal] = None
        self._metrics_service: Optional[MetricsService] = None
        self._market_data_mgr: Optional[MarketDataManager] = None
        self._shutdown_event = threading.Event()

    def run(self, initial_symbols: List[str], duration_sec: Optional[float] = None) -> None:
        """Start the runtime, initialize services, block, and shut down gracefully."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self._setup_signals()

        async def _run_async() -> None:
            logger.info("Starting TOJI Live Paper Trading Platform...")

            # 1. Boot the core 12-plugin kernel
            self._kernel = boot_kernel(config_overrides=self._config_overrides)

            # 2. Instantiate and register Sprint 3 Services
            self._trade_journal = TradeJournal(
                event_bus=self._kernel.event_bus,
                flush_interval=5.0
            )
            self._replay_journal = ReplayJournal(
                event_bus=self._kernel.event_bus,
                flush_interval=5.0
            )
            self._metrics_service = MetricsService(
                collection_interval=5.0,
                container=self._kernel.container
            )
            self._market_data_mgr = MarketDataManager(
                event_bus=self._kernel.event_bus,
                market_gateway=self._kernel.plugin_manager.get(PluginId("market_gateway")),
                stale_threshold_sec=60.0
            )

            # 3. Register new services in the DI container
            container = self._kernel.container
            container.register(TradeJournal, instance=self._trade_journal)
            container.register(ReplayJournal, instance=self._replay_journal)
            container.register(MetricsService, instance=self._metrics_service)
            container.register(MarketDataManager, instance=self._market_data_mgr)
            container.register("trade_journal", instance=self._trade_journal)
            container.register("replay_journal", instance=self._replay_journal)
            container.register("metrics_service", instance=self._metrics_service)
            container.register("market_data_manager", instance=self._market_data_mgr)

            # 4. Wire new services into the kernel lifecycle manager
            lifecycle = self._kernel.lifecycle
            lifecycle.register(self._trade_journal)
            lifecycle.register(self._replay_journal)
            lifecycle.register(self._metrics_service)
            lifecycle.register(self._market_data_mgr)

            # 5. Start new services (kernel lifecycle manager only starts pre-registered ones)
            self._trade_journal.start()
            self._replay_journal.start()
            self._metrics_service.start()
            self._market_data_mgr.start()

            # 6. Start the Recovery Manager
            self._recovery_mgr = RecoveryManager(self._kernel)
            self._recovery_mgr.start()

            # 7. Subscribe to initial symbols
            for symbol in initial_symbols:
                self._market_data_mgr.subscribe(symbol, "ohlcv", "1m")
                self._market_data_mgr.subscribe(symbol, "trade")

            self._print_banner()

            # 8. Main blocking loop
            if duration_sec is not None:
                logger.info("Running for a limited duration of %.1fs...", duration_sec)
                start_wait = time.perf_counter()
                while not self._shutdown_event.is_set() and (time.perf_counter() - start_wait) < duration_sec:
                    await asyncio.sleep(0.1)
            else:
                while not self._shutdown_event.is_set():
                    await asyncio.sleep(1.0)

            # 9. Graceful shutdown sequence
            self.shutdown()

        loop.run_until_complete(_run_async())

    def shutdown(self) -> None:
        """Trigger a clean shutdown of all systems."""
        if self._shutdown_event.is_set():
            return
        self._shutdown_event.set()
        logger.info("Initiating graceful shutdown of TOJI Live Paper Trading Platform...")

        # Stop Recovery Manager first
        if self._recovery_mgr is not None:
            self._recovery_mgr.stop()

        # Stop new services
        if self._market_data_mgr is not None:
            self._market_data_mgr.stop()
        if self._metrics_service is not None:
            self._metrics_service.stop()
        if self._replay_journal is not None:
            self._replay_journal.stop()
        if self._trade_journal is not None:
            self._trade_journal.stop()

        # Shutdown the core kernel
        if self._kernel is not None:
            self._kernel.shutdown()

        logger.info("TOJI Live Paper Trading Platform shut down cleanly ✓")

    def _setup_signals(self) -> None:
        def _handle_signal(sig: int, frame: Any) -> None:
            logger.info("Signal %d received.", sig)
            self._shutdown_event.set()

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except ValueError as e:
            logger.warning("Could not set up signal handlers (probably not running in main thread): %s", e)

    def _print_banner(self) -> None:
        print("=" * 60)
        print("  TOJI LIVE RUNNER — Paper Trading Engine Running")
        print("=" * 60)
        print(f"  Mode    : live (paper)")
        print(f"  Uptime  : {datetime.now(timezone.utc).isoformat()}")
        print(f"  Uvicorn : http://127.0.0.1:{self._config_overrides.get('dashboard.port', 8000)}")
        print("  TOJI READY")
        print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="TOJI Live Runner")
    parser.add_argument("--mode", default="live", choices=["live", "boot"], help="Runner mode")
    parser.add_argument("--symbols", default="BTC/USDT,ETH/USDT", help="Comma-separated symbols to subscribe")
    parser.add_argument("--duration", type=float, help="Optional running duration in seconds")
    args = parser.parse_args()

    # Enable logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if args.mode == "boot":
        # Run regular boot sequence and exit
        boot_kernel()
        print("Regular boot successful ✓")
        sys.exit(0)

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    runner = LiveRunner()
    
    try:
        runner.run(initial_symbols=symbols, duration_sec=args.duration)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt caught by main. Shutting down...")
        runner.shutdown()


if __name__ == "__main__":
    main()
