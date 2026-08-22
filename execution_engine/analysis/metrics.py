from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from execution_engine.core.models import ExecutionMetrics, Order, OrderFill


class ExecutionMetricsCalculator:
    """Calculates operational latency and transaction execution metrics."""

    @staticmethod
    def compute_metrics(
        execution_id: str,
        correlation_id: str,
        start_time: datetime,
        end_time: datetime,
        queue_wait_ms: float,
        validation_time_ms: float,
        network_latency_ms: float,
        broker_latency_ms: float,
        orders: List[Order],
        fills: List[OrderFill],
        retry_count: int,
    ) -> ExecutionMetrics:
        """Saturate an ExecutionMetrics model with performance details."""
        total_duration = (end_time - start_time).total_seconds() * 1000.0
        
        # Calculate total slippage
        # Slippage = Actual Avg Fill Price - Expected Price (limit/stop/reference price)
        total_slippage = 0.0
        for order in orders:
            expected_price = order.price or order.stop_price or 1.0
            avg_price = order.average_fill_price or expected_price
            
            # Absolute difference in percentage
            slippage_val = abs(avg_price - expected_price) / expected_price
            total_slippage += slippage_val

        avg_slippage = total_slippage / len(orders) if orders else 0.0

        # Calculate total commissions
        total_commission = sum(fill.commission for fill in fills)

        return ExecutionMetrics(
            execution_id=execution_id,
            correlation_id=correlation_id,
            queue_time_ms=queue_wait_ms,
            validation_time_ms=validation_time_ms,
            network_latency_ms=network_latency_ms,
            broker_latency_ms=broker_latency_ms,
            fill_latency_ms=total_duration - (queue_wait_ms + validation_time_ms + broker_latency_ms),
            execution_duration_ms=total_duration,
            slippage=avg_slippage,
            commission=total_commission,
            funding=0.0,  # Accumulates during leverage periods (defaults to 0 for Sprint 1)
            retry_count=retry_count,
            timestamp=datetime.now(timezone.utc),
        )
