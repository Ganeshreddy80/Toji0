"""PostgreSQL reporting repository.
"""

from __future__ import annotations

from typing import List, Optional

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import ReportModel
from research_platform.reporting.models import ReportCard


class PostgresReportRepository(BaseRepository):
    """PostgreSQL-backed Reporting repository implementation."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, ReportModel)

    def save_report(self, report: ReportCard) -> None:
        model = self.get(report.report_id)
        if model:
            updates = {
                "title": report.title,
                "content": report.content,
                "format_type": report.format_type,
                "created_at": report.created_at
            }
            self.update(report.report_id, updates)
        else:
            new_model = ReportModel(
                report_id=report.report_id,
                title=report.title,
                content=report.content,
                format_type=report.format_type,
                created_at=report.created_at
            )
            self.create(new_model)

    def get_report(self, report_id: str) -> Optional[ReportCard]:
        model = self.get(report_id)
        if model:
            return ReportCard(
                report_id=model.report_id,
                title=model.title,
                content=model.content,
                format_type=model.format_type,
                created_at=model.created_at
            )
        return None
