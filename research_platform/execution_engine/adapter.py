"""Exchange Adapter Layer mocking connection and order submissions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.execution_engine.interfaces import IExchangeAdapter
from research_platform.execution_engine.models import (
    ExchangeBalance,
    ExchangePosition,
    ExecutionReport
)
from research_platform.oms.models import OrderRequest


class MockExchangeAdapter(IExchangeAdapter):
    """Mock adapter simulating Binance/Coinbase API endpoints."""

    def __init__(self, exchange_name: str) -> None:
        self.exchange_name = exchange_name
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def submit_order(self, request: OrderRequest) -> ExecutionReport:
        if not self._connected:
            raise ConnectionError(f"Adapter for {self.exchange_name} is disconnected.")

        # Simulate execution
        return ExecutionReport(
            report_id=str(uuid.uuid4()),
            order_id=request.order_id,
            symbol=request.symbol,
            status="FILLED",
            filled_quantity=request.quantity,
            avg_price=request.price if request.price > 0.0 else 50000.0,
            commission=1.0,
            timestamp=datetime.now(timezone.utc)
        )

    def get_positions(self) -> List[ExchangePosition]:
        return [
            ExchangePosition(
                symbol="BTC/USDT",
                quantity=1.5,
                entry_price=48000.0,
                current_price=50000.0,
                margin_requirement=24000.0
            )
        ]

    def get_balances(self) -> List[ExchangeBalance]:
        return [
            ExchangeBalance(
                asset="USDT",
                free=100000.0,
                locked=24000.0,
                total=124000.0
            )
        ]
