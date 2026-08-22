"""Portfolio analytics report repository with PostgreSQL delegation and memory fallbacks.
"""

from __future__ import annotations

import threading
from typing import List, Optional
from research_platform.portfolio_analytics.interfaces import IPortfolioAnalyticsRepository
from research_platform.portfolio_analytics.models import (
    PortfolioSnapshot,
    PortfolioAnalyticsReport,
)
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.analytics_repository import PostgresPortfolioAnalyticsRepository


class PortfolioAnalyticsRepository(IPortfolioAnalyticsRepository):
    """Memory-backed repository with PostgreSQL delegation capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshots: List[PortfolioSnapshot] = []
        self._reports: List[PortfolioAnalyticsReport] = []
        self._latest_report: Optional[PortfolioAnalyticsReport] = None

    def _get_pg_repo(self) -> Optional[PostgresPortfolioAnalyticsRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresPortfolioAnalyticsRepository(session_manager)
        return None

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_snapshot(snapshot)
            
        with self._lock:
            self._snapshots.append(snapshot)

    def list_snapshots(self) -> List[PortfolioSnapshot]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.list_snapshots()
            
        with self._lock:
            return list(self._snapshots)

    def save_report(self, report: PortfolioAnalyticsReport) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_report(report)
            
        with self._lock:
            self._reports.append(report)
            self._latest_report = report

    def get_latest_report(self) -> Optional[PortfolioAnalyticsReport]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_latest_report()
            
        with self._lock:
            return self._latest_report
