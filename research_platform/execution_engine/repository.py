"""Database repository saving execution status reports and reconciliation audits.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.execution_engine.interfaces import IExecutionRepository
from research_platform.execution_engine.models import ExecutionReport, ReconciliationLog


class ExecutionRepository(IExecutionRepository):
    """Memory database repository for execution reports."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reports: Dict[str, ExecutionReport] = {}
        self._reconciliations: Dict[str, ReconciliationLog] = {}

    def save_report(self, report: ExecutionReport) -> None:
        with self._lock:
            self._reports[report.report_id] = report

    def get_report(self, report_id: str) -> Optional[ExecutionReport]:
        with self._lock:
            return self._reports.get(report_id)

    def list_reports(self) -> List[ExecutionReport]:
        with self._lock:
            return list(self._reports.values())

    def save_reconciliation(self, log: ReconciliationLog) -> None:
        with self._lock:
            self._reconciliations[log.log_id] = log

    def get_reconciliation(self, log_id: str) -> Optional[ReconciliationLog]:
        with self._lock:
            return self._reconciliations.get(log_id)

    def list_reconciliations(self) -> List[ReconciliationLog]:
        with self._lock:
            return list(self._reconciliations.values())
