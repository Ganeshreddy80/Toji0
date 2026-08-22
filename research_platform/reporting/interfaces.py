"""Abstract contracts for Institutional Reporting.
"""

from __future__ import annotations

import abc
from typing import Optional
from research_platform.reporting.models import ReportCard


class IReportingRepository(abc.ABC):
    """Abstract contract for persisting reports."""

    @abc.abstractmethod
    def save_report(self, report: ReportCard) -> None:
        """Persist report card details."""

    @abc.abstractmethod
    def get_report(self, report_id: str) -> Optional[ReportCard]:
        """Retrieve report card details by ID."""
