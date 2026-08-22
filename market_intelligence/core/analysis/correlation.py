"""Correlation Engine for calculating rolling Pearson and Spearman asset correlations."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any

from market_intelligence.core.events import CorrelationUpdated
from market_intelligence.core.models import CorrelationAnalysis
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class CorrelationEngine:
    """Calculates Pearson and Spearman correlation between multiple symbols over rolling windows."""

    def __init__(self, event_bus: IEventBus | None = None, window: int = 50) -> None:
        self._event_bus = event_bus
        self._window = window
        # Mapping: (symbol, timeframe) -> list of (timestamp, close)
        self._price_history: dict[tuple[str, str], list[tuple[datetime, float]]] = {}
        # Mapping: (symbol, timeframe) -> Pydantic CorrelationAnalysis model
        self._pydantic_correlations: dict[tuple[str, str], CorrelationAnalysis] = {}

    def get_pydantic_correlation(self, symbol: str, timeframe: str) -> CorrelationAnalysis | None:
        """Get the current Pydantic CorrelationAnalysis model."""
        return self._pydantic_correlations.get((symbol, timeframe))

    def process_correlation(self, symbol: str, timeframe: str, candle: Any) -> dict[str, float]:
        """Update price history, calculate correlations with other assets, and publish updates."""
        key = (symbol, timeframe)
        if key not in self._price_history:
            self._price_history[key] = []

        history = self._price_history[key]
        history.append((candle.timestamp, candle.close))
        if len(history) > 500:
            history.pop(0)

        correlations: dict[str, float] = {}

        # Calculate correlation with other assets present in the history on the same timeframe
        for other_key, other_history in self._price_history.items():
            other_symbol, other_tf = other_key
            if other_tf != timeframe or other_symbol == symbol:
                continue

            # Align series by timestamp
            d2 = {ts: val for ts, val in other_history}
            X = []
            Y = []
            # Gather matching timestamps starting from latest
            for ts, val in reversed(history):
                if len(X) >= self._window:
                    break
                if ts in d2:
                    X.append(val)
                    Y.append(d2[ts])

            # We need at least 10 data points for a meaningful correlation
            if len(X) < 10:
                correlations[f"{other_symbol}_pearson"] = 0.0
                correlations[f"{other_symbol}_spearman"] = 0.0
                continue

            # Restore chronological order
            X.reverse()
            Y.reverse()

            # Calculate Pearson
            pearson = self._calc_pearson(X, Y)
            correlations[f"{other_symbol}_pearson"] = pearson

            # Calculate Spearman
            spearman = self._calc_spearman(X, Y)
            correlations[f"{other_symbol}_spearman"] = spearman

        # Calculate a clean Pydantic dict and matrix
        pydantic_corrs: dict[str, float] = {}
        for k_pears, val in correlations.items():
            if k_pears.endswith("_pearson"):
                base_sym = k_pears.replace("_pearson", "")
                pydantic_corrs[base_sym] = val

        # Simple baseline self-correlation
        pydantic_corrs[symbol] = 1.0

        # Construct correlation matrix
        matrix: dict[str, dict[str, float]] = {symbol: pydantic_corrs.copy()}
        for k_pears, val in correlations.items():
            if k_pears.endswith("_pearson"):
                other_sym = k_pears.replace("_pearson", "")
                matrix[other_sym] = {other_sym: 1.0, symbol: val}

        analysis = CorrelationAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            correlations=pydantic_corrs,
            matrix=matrix,
            timestamp=candle.timestamp
        )
        self._pydantic_correlations[key] = analysis

        # Publish event if any correlations were updated
        if correlations:
            self._publish_event(symbol, timeframe, correlations, candle.timestamp)

        return correlations

    def _calc_pearson(self, X: list[float], Y: list[float]) -> float:
        n = len(X)
        mean_x = sum(X) / n
        mean_y = sum(Y) / n

        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(X, Y))
        den_x = sum((x - mean_x) ** 2 for x in X)
        den_y = sum((y - mean_y) ** 2 for y in Y)

        if den_x <= 0.0 or den_y <= 0.0:
            return 0.0

        return num / math.sqrt(den_x * den_y)

    def _calc_spearman(self, X: list[float], Y: list[float]) -> float:
        ranks_x = self._rank_data(X)
        ranks_y = self._rank_data(Y)
        return self._calc_pearson(ranks_x, ranks_y)

    def _rank_data(self, data: list[float]) -> list[float]:
        n = len(data)
        paired = [(val, idx) for idx, val in enumerate(data)]
        sorted_paired = sorted(paired, key=lambda x: x[0])

        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n and sorted_paired[j][0] == sorted_paired[i][0]:
                j += 1
            # Average rank for ties
            avg_rank = (i + j - 1) / 2.0 + 1.0
            for k in range(i, j):
                idx = sorted_paired[k][1]
                ranks[idx] = avg_rank
            i = j
        return ranks

    def _publish_event(self, symbol: str, timeframe: str, correlations: dict[str, float], timestamp: Any) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "correlations": correlations,
            "timestamp": timestamp.isoformat(),
        }
        event = CorrelationUpdated(
            source="market_intelligence.correlation_engine",
            payload=payload,
        )
        self._event_bus.publish(event)
