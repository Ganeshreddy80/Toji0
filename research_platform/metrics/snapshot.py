"""R55 Platform Snapshot Builder — assembles PlatformSnapshot from live data."""

from __future__ import annotations

import time
import logging
from datetime import datetime, timezone

from research_platform.metrics.models import PlatformSnapshot
from research_platform.metrics.collectors import SystemMetricsCollector

logger = logging.getLogger(__name__)

_boot_time = time.time()


class SnapshotBuilder:
    """Aggregates live system and trading metrics into a PlatformSnapshot."""

    def __init__(self) -> None:
        self._sys = SystemMetricsCollector()

    def build(self) -> PlatformSnapshot:
        snap = PlatformSnapshot()

        # System
        try:
            snap.cpu_pct = self._sys.collect_cpu().value
            snap.memory_mb = self._sys.collect_memory().value
            snap.free_disk_gb = self._sys.collect_disk().value
            snap.active_threads = int(self._sys.collect_threads().value)
        except Exception as e:
            logger.debug("System metrics collection partial: %s", e)

        # Trading (graceful)
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            oms = ServiceRegistry().get_service("OMSOrchestrator")
            if oms:
                if hasattr(oms, "get_portfolio_value"):
                    snap.portfolio_value = float(oms.get_portfolio_value() or 0.0)
                if hasattr(oms, "get_daily_pnl"):
                    snap.daily_pnl = float(oms.get_daily_pnl() or 0.0)
                if hasattr(oms, "_open_orders"):
                    snap.open_orders = len(getattr(oms, "_open_orders", {}))
        except Exception:
            pass

        # Certification status
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            orch = ServiceRegistry().get_service("ValidationOrchestrator")
            if orch:
                cert = orch.get_latest_certification()
                if cert:
                    snap.certification_status = "CERTIFIED" if cert.certified else "FAILED"
        except Exception:
            pass

        snap.uptime_sec = time.time() - _boot_time
        return snap
