"""Trading Journal recording session lessons and observations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from research_platform.ai_intelligence.models import JournalEntry


class TradingJournal:
    """Maintains quantitative research diaries logs."""

    def create_journal_entry(
        self,
        trades_count: int,
        observations: str
    ) -> JournalEntry:
        """Construct JournalEntry snapshot."""
        return JournalEntry(
            entry_id=str(uuid.uuid4()),
            trades_reviewed_count=trades_count,
            observations=observations,
            timestamp=datetime.now(timezone.utc)
        )
