"""Market Structure Engine for identifying Higher Highs, Higher Lows, etc."""

from __future__ import annotations

import logging

from market_intelligence.core.enums import SwingType
from market_intelligence.core.events import StructureUpdated
from market_intelligence.core.models import StructurePoint, SwingPoint
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class MarketStructureEngine:
    """Classifies confirmed swing points into HH, HL, LH, LL."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        # Mapping: (symbol, timeframe) -> list of StructurePoint
        self._history: dict[tuple[str, str], list[StructurePoint]] = {}

    def get_structure_history(
        self, symbol: str, timeframe: str
    ) -> list[StructurePoint]:
        """Retrieve structure points history."""
        return self._history.get((symbol, timeframe), [])

    def process_swing(self, swing: SwingPoint) -> StructurePoint:
        """Classify a new confirmed swing point and append to history."""
        symbol = swing.symbol
        timeframe = swing.timeframe
        key = (symbol, timeframe)

        if key not in self._history:
            self._history[key] = []

        history = self._history[key]

        # Find previous swing of the same type
        prev_swing: SwingPoint | None = None
        for item in reversed(history):
            if item.swing_point.point_type == swing.point_type:
                prev_swing = item.swing_point
                break

        classification = ""
        if swing.point_type == SwingType.HIGH:
            if prev_swing is not None:
                if swing.price > prev_swing.price:
                    classification = "HH"
                else:
                    classification = "LH"
            else:
                classification = "HH"
        else:  # LOW
            if prev_swing is not None:
                if swing.price > prev_swing.price:
                    classification = "HL"
                else:
                    classification = "LL"
            else:
                classification = "LL"

        struct_point = StructurePoint(
            swing_point=swing, classification=classification
        )
        history.append(struct_point)

        self._publish_structure_event(struct_point, prev_swing)
        return struct_point

    def _publish_structure_event(
        self, struct_point: StructurePoint, prev_swing: SwingPoint | None
    ) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": struct_point.swing_point.symbol,
            "timeframe": struct_point.swing_point.timeframe,
            "swing_point": struct_point.swing_point.model_dump(),
            "classification": struct_point.classification,
            "previous_price": prev_swing.price if prev_swing else None,
        }

        event = StructureUpdated(
            source="market_intelligence.structure_engine", payload=payload
        )
        self._event_bus.publish(event)
