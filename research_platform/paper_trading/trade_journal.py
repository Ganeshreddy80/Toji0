"""Trade journal logging qualitative rationale entries.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from research_platform.paper_trading.models import TradeJournalEntry

logger = logging.getLogger(__name__)


class TradeJournal:
    """Logs post-trade retrospective rationale parameters."""

    def log_trade(
        self,
        symbol: str,
        quantity: float,
        price: float,
        side: str,
        rationale: str,
        realized_pnl: float = 0.0
    ) -> TradeJournalEntry:
        entry = TradeJournalEntry(
            entry_id=f"jrnl-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc),
            symbol=symbol,
            quantity=quantity,
            price=price,
            side=side,
            realized_pnl=realized_pnl,
            rationale=rationale
        )
        logger.info("Trade Journal logged entry '%s' for %s: %s", entry.entry_id, symbol, rationale)
        return entry
