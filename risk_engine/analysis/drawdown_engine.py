"""Drawdown Engine for tracking portfolio equity drawdown and triggering alerts/halts."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from risk_engine.core.models import DrawdownRisk

logger = logging.getLogger(__name__)


class DrawdownEngine:
    """Manages rolling drawdown calculations and triggers risk stops/halts."""

    def __init__(self) -> None:
        pass

    def calculate_drawdown(
        self,
        current_equity: float,
        peak_equity: float,
        net_profit: float,
        historical_equities: list[float] | None = None,
        warning_threshold: float = 0.05,
        halt_threshold: float = 0.10,
        historical_timestamps: list[datetime] | None = None,
        **kwargs: Any,
    ) -> tuple[DrawdownRisk, str, bool]:
        """
        Calculate rolling drawdown metrics.
        Returns:
            - DrawdownRisk model instance
            - Alert level ("HEALTHY", "WARNING", "HALT")
            - Halt trigger flag (True if halt threshold breached)
        """
        if current_equity <= 0:
            return DrawdownRisk(
                rolling_drawdown=0.0,
                max_drawdown=0.0,
                peak_equity=0.0,
                time_under_water=0.0,
                recovery_factor=0.0,
            ), "HEALTHY", False

        new_peak = max(peak_equity, current_equity)
        rolling_dd = (new_peak - current_equity) / new_peak if new_peak > 0 else 0.0

        # Calculate max drawdown from history if available, else use current rolling drawdown
        max_dd = rolling_dd
        if historical_equities and len(historical_equities) > 0:
            hist_peak = new_peak
            for eq in historical_equities:
                hist_peak = max(hist_peak, eq)
                dd = (hist_peak - eq) / hist_peak if hist_peak > 0 else 0.0
                max_dd = max(max_dd, dd)

        max_dd = max(max_dd, rolling_dd)

        # Time under water (calculated from historical timestamps if available, else 0.0)
        time_under_water = 0.0
        if rolling_dd > 0 and historical_timestamps:
            if len(historical_timestamps) >= 2 and isinstance(historical_timestamps[0], datetime) and isinstance(historical_timestamps[-1], datetime):
                time_under_water = max(0.0, (historical_timestamps[-1] - historical_timestamps[0]).total_seconds())

        recovery_factor = max(0.0, net_profit / max_dd) if max_dd > 0 else 0.0

        # Trigger logic
        alert_level = "HEALTHY"
        halt_trigger = False

        if rolling_dd >= halt_threshold:
            alert_level = "HALT"
            halt_trigger = True
            logger.error("DrawdownEngine: Drawdown HALT triggered! Current DD: %.2f%% >= %.2f%%", rolling_dd * 100, halt_threshold * 100)
        elif rolling_dd >= warning_threshold:
            alert_level = "WARNING"
            logger.warning("DrawdownEngine: Drawdown WARNING active! Current DD: %.2f%% >= %.2f%%", rolling_dd * 100, warning_threshold * 100)

        model = DrawdownRisk(
            rolling_drawdown=round(rolling_dd, 4),
            max_drawdown=round(max_dd, 4),
            peak_equity=round(new_peak, 2),
            time_under_water=time_under_water,
            recovery_factor=round(recovery_factor, 2),
        )

        return model, alert_level, halt_trigger
