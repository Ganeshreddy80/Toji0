"""News Validator for the Risk Engine."""

from __future__ import annotations

from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskSeverity
from risk_engine.core.models import RiskFactor


class NewsValidator:
    """Framework-only news validator accepting injected news events to apply risk restrictions."""

    def validate(
        self, context: TradingContext, **kwargs: Any
    ) -> tuple[RiskFactor | None, float, str | None]:
        # 1. Resolve limits and current states from kwargs
        high_impact_news_active = bool(kwargs.get("high_impact_news_active", False))
        news_gap_minutes = int(kwargs.get("news_gap_minutes", -1))
        news_restriction_window_mins = int(kwargs.get("news_restriction_window_mins", 30))

        # 2. Evaluate news release period
        if high_impact_news_active:
            return (
                RiskFactor(
                    id="RE_NEWS_001",
                    name="Active High-Impact News Event",
                    severity=RiskSeverity.HIGH,
                    score=30.0,
                    description="A high-impact news event is currently active or releasing.",
                ),
                30.0,
                "Active high-impact news event release.",
            )

        # 3. Check proximity to upcoming/recent news event
        if 0 <= news_gap_minutes < news_restriction_window_mins:
            return (
                RiskFactor(
                    id="RE_NEWS_002",
                    name="News Restriction Window Active",
                    severity=RiskSeverity.HIGH,
                    score=25.0,
                    description=f"Current gap of {news_gap_minutes} minutes to high-impact "
                    f"news event is within the restriction window of {news_restriction_window_mins} minutes.",
                ),
                25.0,
                f"Proximity to high-impact news: {news_gap_minutes}m < {news_restriction_window_mins}m.",
            )

        return None, 0.0, None
