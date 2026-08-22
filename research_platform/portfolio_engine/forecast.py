"""Forecast Engine predicting future asset returns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Dict

from research_platform.portfolio_engine.interfaces import IForecastEngine
from research_platform.portfolio_engine.models import ForecastResult


class ForecastEngine(IForecastEngine):
    """Generates returns forecasts using Historical Mean, Momentum, or EWMA averages."""

    def __init__(self, method: str = "mean", window: int = 60, decay: float = 0.94) -> None:
        self.method = method
        self.window = window
        self.decay = decay

    def forecast_returns(self, price_df: pd.DataFrame) -> ForecastResult:
        """Estimate future expected returns from price history DataFrame.

        Expected DataFrame columns: datetime index, columns represent asset prices.
        """
        # Compute daily percentage returns
        returns_df = price_df.pct_change().dropna()
        symbols = list(price_df.columns)
        forecasts = {}

        if returns_df.empty:
            forecasts = {sym: 0.0 for sym in symbols}
        elif self.method == "momentum":
            # Total return over window
            for sym in symbols:
                hist_window = price_df[sym].tail(self.window)
                if len(hist_window) > 1:
                    total_ret = (hist_window.iloc[-1] / hist_window.iloc[0]) - 1.0
                    forecasts[sym] = float(total_ret / self.window)
                else:
                    forecasts[sym] = 0.0
        elif self.method == "ewma":
            # Exponentially weighted returns mean
            for sym in symbols:
                ewma_series = returns_df[sym].ewm(alpha=1.0 - self.decay).mean()
                forecasts[sym] = float(ewma_series.iloc[-1])
        else:
            # Historical Mean
            for sym in symbols:
                forecasts[sym] = float(returns_df[sym].mean())

        return ForecastResult(
            forecasts=forecasts,
            forecast_type=self.method.upper(),
            timestamp=datetime.now(timezone.utc)
        )
