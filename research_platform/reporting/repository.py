"""Reporting repository with PostgreSQL delegation and memory fallbacks.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional
from research_platform.reporting.interfaces import IReportingRepository
from research_platform.reporting.models import ReportCard
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.report_repository import PostgresReportRepository


class ReportingRepository(IReportingRepository):
    """Memory-backed repository with PostgreSQL delegation capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reports: Dict[str, ReportCard] = {}

    def _get_pg_repo(self) -> Optional[PostgresReportRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresReportRepository(session_manager)
        return None

    def save_report(self, report: ReportCard) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_report(report)
            
        with self._lock:
            self._reports[report.report_id] = report

    def get_report(self, report_id: str) -> Optional[ReportCard]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_report(report_id)
            
        with self._lock:
            return self._reports.get(report_id)
