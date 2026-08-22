"""Confluence scoring engine integrating technical structures and indicators."""

from __future__ import annotations

import logging
from typing import Any, List

from research_platform.confluence.models import ConfluenceResult

logger = logging.getLogger(__name__)


class ConfluenceScoringEngine:
    """Combines indicators, structure breaks, order blocks, and multi-timeframe bias."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def calculate_confluence(self, symbol: str, current_price: float) -> ConfluenceResult:
        # Resolve dependencies
        pa_orch = self.container.resolve("PriceActionOrchestrator")
        td_engine = self.container.resolve("TopDownAnalysisEngine")

        # Gather inputs
        td_analysis = td_engine.analyze_symbol(symbol)
        swings = pa_orch.get_swings(symbol)
        structure_changes = pa_orch.get_structure_changes(symbol)
        blocks = pa_orch.get_blocks(symbol)
        gaps = pa_orch.get_gaps(symbol)
        vwap = pa_orch.get_vwap(symbol)
        atr = pa_orch.get_atr(symbol)

        score = 50.0
        explanations = []
        aligned_factors = 0

        # 1. Multi Timeframe Bias contribution
        if td_analysis.final_bias == "BULLISH":
            score += 20.0
            aligned_factors += 1
            explanations.append("Multi-timeframe trend alignment is Bullish (+20)")
        elif td_analysis.final_bias == "BEARISH":
            score -= 20.0
            aligned_factors += 1
            explanations.append("Multi-timeframe trend alignment is Bearish (-20)")

        # 2. Market Structure Break (BOS / CHOCH) contribution
        if structure_changes:
            last_change = structure_changes[-1]
            if last_change.direction == "BULLISH":
                score += 15.0
                aligned_factors += 1
                explanations.append(f"Recent Bullish {last_change.change_type} detected (+15)")
            else:
                score -= 15.0
                aligned_factors += 1
                explanations.append(f"Recent Bearish {last_change.change_type} detected (-15)")

        # 3. Price vs VWAP location
        if current_price > vwap:
            score += 10.0
            aligned_factors += 1
            explanations.append("Price is trading above daily VWAP (+10)")
        else:
            score -= 10.0
            aligned_factors += 1
            explanations.append("Price is trading below daily VWAP (-10)")

        # 4. Order Blocks (OB) alignment
        active_ob = [b for b in blocks if not b.mitigated]
        if active_ob:
            last_ob = active_ob[-1]
            if last_ob.direction == "BULLISH" and current_price >= last_ob.low:
                score += 10.0
                aligned_factors += 1
                explanations.append("Price is holding within a Bullish Order Block zone (+10)")
            elif last_ob.direction == "BEARISH" and current_price <= last_ob.high:
                score -= 10.0
                aligned_factors += 1
                explanations.append("Price is capped within a Bearish Order Block zone (-10)")

        # 5. Fair Value Gaps (FVG) proximity
        active_gaps = [g for g in gaps if not g.filled]
        if active_gaps:
            score += 5.0
            aligned_factors += 1
            explanations.append("Active Fair Value Gaps remain unfilled (+5)")

        # Limit score bounds
        score = max(0.0, min(100.0, score))

        # Determine direction
        if score > 55.0:
            direction = "BULLISH"
        elif score < 45.0:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        # Determine confidence
        if aligned_factors >= 4:
            confidence = "HIGH"
        elif aligned_factors >= 2:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        # Determine strength
        strength = "STRONG" if (score > 70.0 or score < 30.0) else "WEAK"

        return ConfluenceResult(
            symbol=symbol,
            score=score,
            confidence=confidence,
            strength=strength,
            direction=direction,
            explanations=explanations
        )
