"""Top-Down Analysis Engine resolving biases across multiple timeframes."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from research_platform.multi_timeframe.models import TimeframeBias, TopDownAnalysis

logger = logging.getLogger(__name__)


class TopDownAnalysisEngine:
    """Combines HTF, MTF, and LTF biases to confirm institutional order flow direction."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def analyze_symbol(self, symbol: str) -> TopDownAnalysis:
        # Resolve PriceActionOrchestrator
        pa_orch = self.container.resolve("PriceActionOrchestrator")
        
        # In a real environment, we'd query multiple timeframes of data.
        # Since we aggregate ticks into a single stream, we mock/simulate the top-down alignment
        # by checking the current trend and swings from the PriceActionOrchestrator.
        changes = pa_orch.get_structure_changes(symbol)
        
        # Calculate base bias from recent structure changes
        if changes:
            last_change = changes[-1]
            primary_direction = last_change.direction
            strength = 0.85
        else:
            primary_direction = "NEUTRAL"
            strength = 0.5

        # HTF Bias: Higher Timeframe (e.g., Daily trend)
        htf = TimeframeBias(
            timeframe="1d",
            bias=primary_direction,
            strength=strength
        )

        # MTF Bias: Medium Timeframe (e.g., 1h / 15m trend)
        mtf = TimeframeBias(
            timeframe="15m",
            bias=primary_direction,
            strength=strength
        )

        # LTF Bias: Lower Timeframe (e.g., 1m trend / confirmation)
        ltf = TimeframeBias(
            timeframe="1m",
            bias=primary_direction,
            strength=strength
        )

        aligned = (htf.bias == mtf.bias == ltf.bias) and htf.bias != "NEUTRAL"

        return TopDownAnalysis(
            symbol=symbol,
            htf_bias=htf,
            mtf_bias=mtf,
            ltf_bias=ltf,
            aligned=aligned,
            final_bias=htf.bias if aligned else "NEUTRAL"
        )
