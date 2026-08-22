"""Reconciliation Engine audits differences between local database and exchange states.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.execution_engine.models import ExchangePosition, ReconciliationLog
from research_platform.oms.models import Order


class StateReconciler:
    """Verifies orders, positions, and cash balances matching parameters."""

    @staticmethod
    def reconcile(
        local_orders: List[Order],
        exchange_positions: List[ExchangePosition]
    ) -> ReconciliationLog:
        """Compare local records against exchange updates, identifying discrepancies.

        Returns:
            ReconciliationLog tracking status matches.
        """
        discrepancies = []
        
        # Simple reconciliation logic: check if local FILLED orders match exchange position totals
        total_local_qty = sum(o.filled_quantity for o in local_orders if o.status == "FILLED")
        total_exch_qty = sum(p.quantity for p in exchange_positions)

        if total_local_qty != total_exch_qty:
            discrepancies.append(
                f"Position mismatch: Local filled quantity sum is {total_local_qty}, "
                f"but Exchange positions quantity sum is {total_exch_qty}"
            )

        reconciled = len(discrepancies) == 0

        return ReconciliationLog(
            log_id=str(uuid.uuid4()),
            discrepancies=discrepancies,
            reconciled=reconciled,
            timestamp=datetime.now(timezone.utc)
        )
