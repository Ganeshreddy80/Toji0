"""Weekend Validator for the Risk Engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from trading_context.core.models import TradingContext
from risk_engine.core.enums import RiskSeverity
from risk_engine.core.models import RiskFactor


class WeekendValidator:
    """Blocks weekend trading where markets are closed or liquidity is extremely thin."""

    def validate(
        self, context: TradingContext, **kwargs: Any
    ) -> tuple[RiskFactor | None, float, str | None]:
        # 1. Resolve configurations from kwargs
        weekend_block_active = bool(kwargs.get("weekend_block_active", True))
        weekend_start_hour = int(kwargs.get("weekend_start_hour", 17))  # Friday 17:00 UTC
        weekend_end_hour = int(kwargs.get("weekend_end_hour", 18))      # Sunday 18:00 UTC

        if not weekend_block_active:
            return None, 0.0, None

        # 2. Extract timestamp to check
        dt = context.generated_at or datetime.now(timezone.utc)
        # Ensure timezone-aware comparison by converting to UTC
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)

        weekday = dt.weekday()  # Monday=0, ..., Friday=4, Saturday=5, Sunday=6
        hour = dt.hour

        is_weekend = False

        if weekday == 4:  # Friday
            if hour >= weekend_start_hour:
                is_weekend = True
        elif weekday == 5:  # Saturday
            is_weekend = True
        elif weekday == 6:  # Sunday
            if hour < weekend_end_hour:
                is_weekend = True

        # 3. Return violation if weekend
        if is_weekend:
            return (
                RiskFactor(
                    id="RE_WEND_001",
                    name="Weekend Trading Prohibited",
                    severity=RiskSeverity.CRITICAL,
                    score=100.0,
                    description=f"Trading proposal timestamp {dt.isoformat()} falls "
                    f"during the weekend restriction window.",
                ),
                100.0,
                f"Weekend trading block is active: day={weekday}, hour={hour}.",
            )

        return None, 0.0, None
