"""R55 Metrics Collectors — gather system and trading metrics."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from research_platform.metrics.models import MetricPoint, MetricType, MetricUnit, PlatformSnapshot

logger = logging.getLogger(__name__)


class SystemMetricsCollector:
    """Collects CPU, memory, disk, and thread counts."""

    def collect_cpu(self) -> MetricPoint:
        try:
            import psutil
            val = psutil.cpu_percent(interval=0.05)
        except ImportError:
            val = 0.0
        return MetricPoint(name="system.cpu_pct", value=val,
                           metric_type=MetricType.GAUGE, unit=MetricUnit.PERCENT)

    def collect_memory(self) -> MetricPoint:
        try:
            import psutil
            val = psutil.Process().memory_info().rss / (1024 * 1024)
        except ImportError:
            val = 0.0
        return MetricPoint(name="system.memory_mb", value=val,
                           metric_type=MetricType.GAUGE, unit=MetricUnit.MEGABYTES)

    def collect_disk(self) -> MetricPoint:
        import shutil
        total, used, free = shutil.disk_usage(".")
        return MetricPoint(name="system.free_disk_gb", value=free / (1024 ** 3),
                           metric_type=MetricType.GAUGE, unit=MetricUnit.MEGABYTES)

    def collect_threads(self) -> MetricPoint:
        import threading
        return MetricPoint(name="system.active_threads", value=threading.active_count(),
                           metric_type=MetricType.GAUGE, unit=MetricUnit.COUNT)


class TradingMetricsCollector:
    """Collects OMS, portfolio, and strategy metrics."""

    def collect_portfolio_value(self) -> Optional[MetricPoint]:
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            oms = ServiceRegistry().get_service("OMSOrchestrator")
            if oms and hasattr(oms, "get_portfolio_value"):
                val = oms.get_portfolio_value()
                return MetricPoint(name="trading.portfolio_value", value=val,
                                   metric_type=MetricType.GAUGE, unit=MetricUnit.DOLLARS)
        except Exception:
            pass
        return None

    def collect_daily_pnl(self) -> Optional[MetricPoint]:
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            oms = ServiceRegistry().get_service("OMSOrchestrator")
            if oms and hasattr(oms, "get_daily_pnl"):
                val = oms.get_daily_pnl()
                return MetricPoint(name="trading.daily_pnl", value=val,
                                   metric_type=MetricType.GAUGE, unit=MetricUnit.DOLLARS)
        except Exception:
            pass
        return None

    def collect_open_orders(self) -> MetricPoint:
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            oms = ServiceRegistry().get_service("OMSOrchestrator")
            if oms and hasattr(oms, "_open_orders"):
                val = len(getattr(oms, "_open_orders", {}))
                return MetricPoint(name="trading.open_orders", value=float(val),
                                   metric_type=MetricType.GAUGE, unit=MetricUnit.COUNT)
        except Exception:
            pass
        return MetricPoint(name="trading.open_orders", value=0.0,
                           metric_type=MetricType.GAUGE, unit=MetricUnit.COUNT)
