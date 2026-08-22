"""Indicator library containing details of simple technical indicators.
"""

from __future__ import annotations

from typing import Dict, List
from research_platform.research_lab.models import Indicator


class IndicatorLibrary:
    """Aggregates indicators parameters setups."""

    def __init__(self) -> None:
        self._indicators: Dict[str, Indicator] = {
            "sma": Indicator(indicator_id="sma", name="Simple Moving Average", params={"period": 20}),
            "rsi": Indicator(indicator_id="rsi", name="Relative Strength Index", params={"period": 14})
        }

    def get_indicator(self, indicator_id: str) -> Optional[Indicator]:
        return self._indicators.get(indicator_id)

    def list_indicators(self) -> List[Indicator]:
        return list(self._indicators.values())
from typing import Optional
