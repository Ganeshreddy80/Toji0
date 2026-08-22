"""Report Generator compiling daily and weekly operational summaries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.ai_intelligence.models import DailyReport, Insight, Warning


class ReportGenerator:
    """Compiles portfolio performance reports."""

    def compile_daily_report(
        self,
        summary: str,
        insights: List[Insight],
        warnings: List[Warning]
    ) -> DailyReport:
        """Construct DailyReport document."""
        return DailyReport(
            report_id=str(uuid.uuid4()),
            summary=summary,
            insights=insights,
            warnings=warnings,
            timestamp=datetime.now(timezone.utc)
        )
