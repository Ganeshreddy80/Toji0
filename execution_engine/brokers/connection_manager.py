from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from toji_platform.core.types import HealthStatus
from execution_engine.brokers.broker_interface import IBrokerAdapter

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages adapter connection lifecycles, monitoring heartbeats and auto-reconnecting on disconnects."""

    def __init__(self, adapter: IBrokerAdapter, heartbeat_interval_sec: int = 30, reconnect_interval_sec: int = 5) -> None:
        self._adapter = adapter
        self._heartbeat_interval = heartbeat_interval_sec
        self._reconnect_interval = reconnect_interval_sec
        
        self._lock = threading.Lock()
        self._connectivity = "DISCONNECTED"  # CONNECTED, DISCONNECTED, RECONNECTING
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def connectivity(self) -> str:
        """Get the current connectivity status string."""
        with self._lock:
            return self._connectivity

    def start(self) -> None:
        """Start the connection monitoring thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            
        self._connectivity = "RECONNECTING"
        self._monitor_thread = threading.Thread(target=self._monitor_loop, name="broker-connection-monitor", daemon=True)
        self._monitor_thread.start()
        logger.info("ConnectionManager: Monitoring thread started.")

    def stop(self) -> None:
        """Stop the connection monitoring thread cleanly."""
        with self._lock:
            self._running = False
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None
        self._adapter.disconnect()
        self._connectivity = "DISCONNECTED"
        logger.info("ConnectionManager: Monitoring thread stopped.")

    def _monitor_loop(self) -> None:
        """Background loop executing connection checks and heartbeats."""
        while True:
            with self._lock:
                if not self._running:
                    break

            try:
                # 1. Attempt connection if marked disconnected/reconnecting
                if self._connectivity in ("DISCONNECTED", "RECONNECTING"):
                    logger.debug("ConnectionManager: Attempting connection to broker...")
                    self._adapter.connect()
                    with self._lock:
                        self._connectivity = "CONNECTED"
                    logger.info("ConnectionManager: Successfully connected to broker.")

                # 2. Perform heartbeat check
                ping_ok = self._adapter.ping()
                if not ping_ok or self._adapter.health() == HealthStatus.UNHEALTHY:
                    logger.warning("ConnectionManager: Heartbeat check failed or adapter unhealthy.")
                    with self._lock:
                        self._connectivity = "RECONNECTING"
                    self._adapter.disconnect()
                else:
                    with self._lock:
                        self._connectivity = "CONNECTED"
                    
            except Exception as e:
                logger.error("ConnectionManager: Error during monitor loop: %s", e)
                with self._lock:
                    self._connectivity = "RECONNECTING"
                try:
                    self._adapter.disconnect()
                except Exception:
                    pass

            # Sleep depending on state
            sleep_time = self._heartbeat_interval if self._connectivity == "CONNECTED" else self._reconnect_interval
            if self._stop_event.wait(sleep_time):
                break
