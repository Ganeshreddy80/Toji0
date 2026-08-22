"""Master background runtime execution engine.
"""

from __future__ import annotations

import time
import logging
import threading
import uuid
from typing import Dict, Any, List

from research_platform.runtime.interfaces import IRuntimeEngine, IRuntimeLoop
from research_platform.runtime.models import RuntimeStatus, LoopMetrics
from research_platform.runtime.heartbeat import HeartbeatMonitor
from research_platform.runtime.repository import RuntimeRepository
from research_platform.runtime.events import (
    RuntimeStarted,
    RuntimePaused,
    RuntimeResumed,
    RuntimeStopped,
    HeartbeatLogged,
    SubsystemFailed,
    SubsystemRecovered
)

logger = logging.getLogger(__name__)


class RuntimeEngine(IRuntimeEngine):
    """Executes the master trading loops continuously on a background thread."""

    def __init__(self, container: Any, interval_sec: float = 1.0) -> None:
        self.container = container
        self.interval_sec = interval_sec
        self.status = RuntimeStatus.STOPPED
        
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        
        self.repository = RuntimeRepository()
        self.heartbeat_monitor = HeartbeatMonitor()
        
        # Instantiate execution loops
        from research_platform.runtime.market_loop import MarketLoop
        from research_platform.runtime.strategy_loop import StrategyLoop
        from research_platform.runtime.risk_loop import RiskLoop
        from research_platform.runtime.portfolio_loop import PortfolioLoop
        from research_platform.runtime.execution_loop import ExecutionLoop
        from research_platform.runtime.analytics_loop import AnalyticsLoop
        from research_platform.runtime.monitoring_loop import MonitoringLoop
        from research_platform.runtime.persistence_loop import PersistenceLoop
        from research_platform.runtime.scheduler_loop import SchedulerLoop
        from research_platform.runtime.recovery_loop import RecoveryLoop

        self.loops: Dict[str, IRuntimeLoop] = {
            "MarketLoop": MarketLoop(container),
            "StrategyLoop": StrategyLoop(container),
            "RiskLoop": RiskLoop(container),
            "PortfolioLoop": PortfolioLoop(container),
            "ExecutionLoop": ExecutionLoop(container),
            "AnalyticsLoop": AnalyticsLoop(container),
            "MonitoringLoop": MonitoringLoop(container),
            "PersistenceLoop": PersistenceLoop(container),
            "SchedulerLoop": SchedulerLoop(container),
            "RecoveryLoop": RecoveryLoop(container)
        }

        # Track execution stats
        self.metrics = LoopMetrics()
        self.run_count = 0

    def start(self) -> None:
        with self._lock:
            if self.status != RuntimeStatus.STOPPED:
                logger.warning("RuntimeEngine is already active or booting.")
                return

            logger.info("Starting Continuous Runtime Engine thread...")
            self.status = RuntimeStatus.RUNNING
            self._stop_event.clear()
            self._pause_event.clear()
            
            # Publish start event
            self._publish_event(RuntimeStarted(event_id=str(uuid.uuid4())))

            self._thread = threading.Thread(target=self._run_loop, name="TOJI_Master_Loop", daemon=True)
            self._thread.start()

    def pause(self) -> None:
        with self._lock:
            if self.status != RuntimeStatus.RUNNING:
                logger.warning("Cannot pause: Runtime is not running.")
                return
            logger.info("Pausing Continuous Runtime Engine loop...")
            self.status = RuntimeStatus.PAUSED
            self._pause_event.set()
            
            self._publish_event(RuntimePaused(event_id=str(uuid.uuid4())))

    def resume(self) -> None:
        with self._lock:
            if self.status != RuntimeStatus.PAUSED:
                logger.warning("Cannot resume: Runtime is not paused.")
                return
            logger.info("Resuming Continuous Runtime Engine loop...")
            self.status = RuntimeStatus.RUNNING
            self._pause_event.clear()
            
            self._publish_event(RuntimeResumed(event_id=str(uuid.uuid4())))

    def stop(self) -> None:
        with self._lock:
            if self.status == RuntimeStatus.STOPPED:
                return
            logger.info("Stopping Continuous Runtime Engine thread...")
            self.status = RuntimeStatus.STOPPED
            self._stop_event.set()
            self._pause_event.clear()

        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
            
        self._publish_event(RuntimeStopped(event_id=str(uuid.uuid4())))

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": self.status.value,
                "run_count": self.run_count,
                "metrics": self.metrics.model_dump()
            }

    def _publish_event(self, event: Any) -> None:
        try:
            eb = self.container.resolve("IEventBus")
            if eb:
                eb.publish(event.__class__.__name__, event.model_dump())
                self.metrics.event_count += 1
        except Exception:
            pass

    def _run_loop(self) -> None:
        context: Dict[str, Any] = {}
        
        while not self._stop_event.is_set():
            # Check pause state
            if self._pause_event.is_set():
                time.sleep(0.1)
                continue

            loop_start_time = time.perf_counter()
            self.run_count += 1
            
            loop_states = {}
            
            # Execute sequential loops (1 to 16)
            for name, loop in self.loops.items():
                if self._stop_event.is_set():
                    break
                    
                sub_start = time.perf_counter()
                try:
                    loop.execute(context)
                    self.metrics.execution_times_ms[name] = (time.perf_counter() - sub_start) * 1000.0
                    loop_states[name] = "HEALTHY"
                except Exception as ex:
                    # Increment metrics recovery counter and handle
                    self.metrics.recovery_count += 1
                    loop_states[name] = "FAILED"
                    self._publish_event(SubsystemFailed(event_id=str(uuid.uuid4()), subsystem_name=name, error_message=str(ex)))
                    
                    # Call recovery hook
                    recovered = False
                    try:
                        recovered = loop.recover(ex)
                    except Exception as recovery_err:
                        logger.error("Error running loop recovery handler for %s: %s", name, recovery_err)

                    if recovered:
                        loop_states[name] = "RECOVERED"
                        self._publish_event(SubsystemRecovered(event_id=str(uuid.uuid4()), subsystem_name=name, retry_count=1))
                    else:
                        logger.error("Subsystem %s failed to recover: %s", name, ex)

            # Compute latency
            loop_elapsed = (time.perf_counter() - loop_start_time) * 1000.0
            self.metrics.loop_latency_ms = loop_elapsed
            self.repository.save_metric("loop_latency_ms", loop_elapsed)
            
            # Analyze CPU/Memory telemetry (17. Heartbeat)
            telemetry = self.heartbeat_monitor.get_telemetry()
            self.metrics.cpu_time_ms = telemetry.get("cpu_pct", 0.0)
            self.metrics.memory_mb = telemetry.get("memory_mb", 0.0)
            
            self.repository.save_metric("cpu_time_ms", telemetry.get("cpu_pct", 0.0))
            self.repository.save_metric("memory_mb", telemetry.get("memory_mb", 0.0))
            self.repository.save_metric("event_count", self.metrics.event_count)
            self.repository.save_metric("recovery_count", self.metrics.recovery_count)
            
            # Trigger heartbeat
            self.repository.save_heartbeat(self.status.value, {
                "loop_latency_ms": loop_elapsed,
                "cpu_pct": telemetry.get("cpu_pct", 0.0),
                "memory_mb": telemetry.get("memory_mb", 0.0),
                "loop_states": loop_states
            })
            
            self._publish_event(HeartbeatLogged(
                event_id=str(uuid.uuid4()),
                loop_latency_ms=loop_elapsed,
                cpu_time_ms=telemetry.get("cpu_pct", 0.0),
                memory_mb=telemetry.get("memory_mb", 0.0),
                event_count=self.metrics.event_count,
                recovery_count=self.metrics.recovery_count,
                loop_states=loop_states
            ))
            
            # sleep for configurable interval
            if self._stop_event.wait(max(0.001, self.interval_sec)):
                break
