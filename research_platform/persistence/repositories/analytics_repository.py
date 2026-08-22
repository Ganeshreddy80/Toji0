"""PostgreSQL portfolio analytics repository.
"""

from __future__ import annotations

import json
from typing import List, Optional

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import AnalyticsModel
from research_platform.portfolio_analytics.models import PortfolioSnapshot, PortfolioAnalyticsReport


class PostgresPortfolioAnalyticsRepository(BaseRepository):
    """PostgreSQL-backed Portfolio Analytics repository implementation."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, AnalyticsModel)
        self._snapshots: List[str] = []
        self._reports: List[str] = []
        self._latest: Optional[str] = None

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        self._snapshots.append(snapshot.model_dump_json())

    def list_snapshots(self) -> List[PortfolioSnapshot]:
        return [PortfolioSnapshot.model_validate_json(s) for s in self._snapshots]

    def save_report(self, report: PortfolioAnalyticsReport) -> None:
        serialized = report.model_dump_json()
        self._reports.append(serialized)
        self._latest = serialized

    def get_latest_report(self) -> Optional[PortfolioAnalyticsReport]:
        if self._latest:
            return PortfolioAnalyticsReport.model_validate_json(self._latest)
        return None
