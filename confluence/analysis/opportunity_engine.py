"""Opportunity Engine for evaluating trade opportunity quality."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from confluence.core.models import ConfluenceScore, OpportunityScore


class OpportunityEngine:
    """Evaluates the quality and viability of a trading opportunity.

    Combines three dimensions:
        1. Setup Quality (40%): derived from confluence score and supporting factor count
        2. Execution Quality (30%): derived from liquidity, volume, and spread conditions
        3. Expected Risk/Reward (30%): derived from zone proximity and trend strength
    """

    def evaluate(
        self,
        market_state: MarketState,
        confluence_score: ConfluenceScore,
    ) -> OpportunityScore:
        """Calculate opportunity metrics from market conditions and confluence scoring."""
        setup_quality = self._calc_setup_quality(confluence_score)
        execution_quality = self._calc_execution_quality(market_state, confluence_score)
        expected_rr = self._calc_expected_rr(market_state, confluence_score)

        # Combined opportunity score
        opportunity = (
            setup_quality * 0.4
            + execution_quality * 0.3
            + min(expected_rr * 20.0, 100.0) * 0.3  # Normalize R:R to 0-100 scale
        )
        opportunity = round(max(0.0, min(100.0, opportunity)), 2)

        return OpportunityScore(
            setup_quality=round(setup_quality, 2),
            execution_quality=round(execution_quality, 2),
            expected_rr=round(expected_rr, 2),
            opportunity_score=opportunity,
        )

    def _calc_setup_quality(self, score: ConfluenceScore) -> float:
        """Setup quality from overall score and supporting factor count."""
        base = score.overall_score
        factor_bonus = min(len(score.supporting_factors) * 2.0, 10.0)
        factor_penalty = min(len(score.conflicting_factors) * 3.0, 15.0)
        return max(0.0, min(100.0, base + factor_bonus - factor_penalty))

    def _calc_execution_quality(
        self,
        market_state: MarketState,
        score: ConfluenceScore,
    ) -> float:
        """Execution quality from liquidity and volume conditions."""
        liq = score.liquidity_score
        vol = score.volume_score

        # Boost from MIL liquidity analysis if available
        spread_penalty = 0.0
        if market_state.liquidity_analysis is not None:
            spread = market_state.liquidity_analysis.bid_ask_spread
            if spread > 0.5:
                spread_penalty = min(spread * 10.0, 20.0)

        base = (liq * 0.6 + vol * 0.4)
        return max(0.0, min(100.0, base - spread_penalty))

    def _calc_expected_rr(
        self,
        market_state: MarketState,
        score: ConfluenceScore,
    ) -> float:
        """Expected risk/reward from zone proximity and trend strength."""
        # Base R:R from trend strength
        trend_contribution = 1.0
        if market_state.trend is not None:
            strength = market_state.trend.strength
            trend_contribution = 1.0 + (strength * 2.0)  # 1.0 to 3.0

        # Zone bonus: more zones = tighter R:R targets available
        zone_bonus = min(len(market_state.zones) * 0.2, 1.0)

        # Structure bonus from confluence score quality
        quality_bonus = score.quality_score / 100.0 * 0.5

        return max(0.5, trend_contribution + zone_bonus + quality_bonus)
