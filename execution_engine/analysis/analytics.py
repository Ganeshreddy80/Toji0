import threading
from typing import Dict, List, Any
from execution_engine.core.models import ExecutionMetrics, Order
from execution_engine.core.enums import OrderState


class ExecutionAnalyticsCalculator:
    """Calculates rolling and aggregated execution performance metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics_list: List[ExecutionMetrics] = []
        self._orders_list: List[Order] = []
        self._peak_queue_size = 0
        self._current_queue_depth = 0

    def record_metrics(self, metric: ExecutionMetrics) -> None:
        """Add execution metrics snapshot for rolling average updates."""
        with self._lock:
            self._metrics_list.append(metric)

    def record_order(self, order: Order) -> None:
        """Add finished order for state success updates."""
        with self._lock:
            self._orders_list.append(order)

    def update_queue_stats(self, size: int) -> None:
        """Update active queue depth and tracks peak historical sizes."""
        with self._lock:
            self._current_queue_depth = size
            if size > self._peak_queue_size:
                self._peak_queue_size = size

    def get_summary(self) -> Dict[str, Any]:
        """Compile and summarize rolling analytics averages."""
        with self._lock:
            total_orders = len(self._orders_list)
            if total_orders == 0:
                return {
                    "success_rate": 1.0,
                    "fill_rate": 0.0,
                    "partial_fill_rate": 0.0,
                    "average_slippage": 0.0,
                    "average_commission": 0.0,
                    "average_latency_ms": 0.0,
                    "retry_rate": 0.0,
                    "orders_per_second": 0.0,
                    "queue_depth": self._current_queue_depth,
                    "peak_queue_size": self._peak_queue_size,
                }

            filled_count = sum(1 for o in self._orders_list if o.state == OrderState.FILLED)
            partial_count = sum(1 for o in self._orders_list if o.state == OrderState.PARTIALLY_FILLED)
            failed_count = sum(1 for o in self._orders_list if o.state in (OrderState.REJECTED, OrderState.EXPIRED))

            success_rate = (total_orders - failed_count) / total_orders
            fill_rate = filled_count / total_orders
            partial_fill_rate = partial_count / total_orders

            avg_slippage = sum(m.slippage for m in self._metrics_list) / max(1, len(self._metrics_list))
            avg_commission = sum(m.commission for m in self._metrics_list) / max(1, len(self._metrics_list))
            avg_latency = sum(m.broker_latency_ms for m in self._metrics_list) / max(1, len(self._metrics_list))

            total_retries = sum(m.retry_count for m in self._metrics_list)
            retry_rate = total_retries / total_orders

            ops = 0.0
            if len(self._orders_list) > 1:
                times = [o.created_at for o in self._orders_list]
                duration = (max(times) - min(times)).total_seconds()
                if duration > 0:
                    ops = total_orders / duration

            return {
                "success_rate": success_rate,
                "fill_rate": fill_rate,
                "partial_fill_rate": partial_fill_rate,
                "average_slippage": avg_slippage,
                "average_commission": avg_commission,
                "average_latency_ms": avg_latency,
                "retry_rate": retry_rate,
                "orders_per_second": ops,
                "queue_depth": self._current_queue_depth,
                "peak_queue_size": self._peak_queue_size,
            }
