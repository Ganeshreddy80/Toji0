"""Abstract contracts for the Execution Management System (EMS).
"""

from __future__ import annotations

import abc
from typing import Dict, List, Optional

from research_platform.execution_engine.models import (
    ExchangeBalance,
    ExchangePosition,
    ExecutionReport,
    ReconciliationLog
)
from research_platform.oms.models import Order, OrderRequest


class IExchangeAdapter(abc.ABC):
    """Abstract contract for connecting and executing on external exchanges."""

    @abc.abstractmethod
    def connect(self) -> bool:
        """Establish connections to exchange APIs."""

    @abc.abstractmethod
    def submit_order(self, request: OrderRequest) -> ExecutionReport:
        """Submit order to exchange."""

    @abc.abstractmethod
    def get_positions(self) -> List[ExchangePosition]:
        """Fetch active positions from exchange."""

    @abc.abstractmethod
    def get_balances(self) -> List[ExchangeBalance]:
        """Fetch balances from exchange."""


class IExecutionRepository(abc.ABC):
    """Abstract database repository contract for execution logs."""

    @abc.abstractmethod
    def save_report(self, report: ExecutionReport) -> None:
        """Persist an ExecutionReport."""

    @abc.abstractmethod
    def save_reconciliation(self, log: ReconciliationLog) -> None:
        """Persist a ReconciliationLog."""
