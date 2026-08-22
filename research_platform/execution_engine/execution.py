"""Execution tracker converting order requests into status fill reports.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from research_platform.execution_engine.models import ExecutionReport
from research_platform.oms.models import OrderRequest


class ExecutionTracker:
    """Processes fills notifications and maps updates to execution reports."""

    @staticmethod
    def create_filled_report(request: OrderRequest, fill_price: float) -> ExecutionReport:
        """Construct a complete FILLED status ExecutionReport."""
        return ExecutionReport(
            report_id=str(uuid.uuid4()),
            order_id=request.order_id,
            symbol=request.symbol,
            status="FILLED",
            filled_quantity=request.quantity,
            avg_price=fill_price,
            commission=1.0,
            timestamp=datetime.now(timezone.utc)
        )
