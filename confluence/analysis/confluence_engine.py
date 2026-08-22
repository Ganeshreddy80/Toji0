"""Confluence Engine implementation coordinating positive and conflict scoring."""

from __future__ import annotations

from typing import Any

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from price_action.core.models import PatternState
from confluence.core.enums import SetupGrade
from confluence.core.interfaces import IConfluenceEngine
from confluence.core.models import (
    ConfluenceScore,
    SupportingFactor,
    ConflictingFactor,
)
from confluence.analysis.trend_score import evaluate_trend
from confluence.analysis.structure_score import evaluate_structure
from confluence.analysis.liquidity_score import evaluate_liquidity
from confluence.analysis.zone_score import evaluate_zones
from confluence.analysis.volume_score import evaluate_volume
from confluence.analysis.regime_score import evaluate_regime
from confluence.analysis.session_score import evaluate_session
from confluence.analysis.mtf_score import evaluate_mtf
from confluence.analysis.correlation_score import evaluate_correlation
from confluence.analysis.pattern_score import evaluate_pattern
from confluence.analysis.quality_score import evaluate_quality
from confluence.analysis.conflict_engine import ConflictEngine
from confluence.analysis.grade_engine import GradeEngine
from confluence.analysis.opportunity_engine import OpportunityEngine
from confluence.analysis.risk_flag_engine import RiskFlagEngine
from confluence.analysis.explanation_engine import ExplanationEngine


class ConfluenceEngine(IConfluenceEngine):
    """Authoritative engine to calculate confluence score and assign setup grades."""

    def __init__(
        self,
        conflict_engine: ConflictEngine | None = None,
        grade_engine: GradeEngine | None = None,
        opportunity_engine: OpportunityEngine | None = None,
        risk_flag_engine: RiskFlagEngine | None = None,
        explanation_engine: ExplanationEngine | None = None,
        container: Any | None = None,
    ) -> None:
        self._conflict_engine = conflict_engine or ConflictEngine()
        self._grade_engine = grade_engine or GradeEngine()
        self._opportunity_engine = opportunity_engine or OpportunityEngine()
        self._risk_flag_engine = risk_flag_engine or RiskFlagEngine()
        self._explanation_engine = explanation_engine or ExplanationEngine()
        self._container = container

        # Define weights
        self._weights = {
            "trend": 0.15,
            "structure": 0.15,
            "liquidity": 0.15,
            "zone": 0.10,
            "volume": 0.10,
            "regime": 0.05,
            "session": 0.05,
            "mtf": 0.10,
            "correlation": 0.05,
            "pattern": 0.10,
            "quality": 0.06,
        }

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
    ) -> ConfluenceScore:
        """Calculate overall confluence score from market and pattern states."""
        # Determine setup direction based on active or candidate pattern direction
        direction = None
        if pattern_state:
            if pattern_state.active_patterns:
                direction = pattern_state.active_patterns[0].direction
            elif pattern_state.candidate_patterns:
                direction = pattern_state.candidate_patterns[0].direction

        # Run all positive scorers
        trend_score, trend_sup, trend_conf = evaluate_trend(market_state, direction)
        struct_score, struct_sup, struct_conf = evaluate_structure(market_state, direction)
        liq_score, liq_sup, liq_conf = evaluate_liquidity(market_state, direction)
        zone_score, zone_sup, zone_conf = evaluate_zones(market_state, direction)
        vol_score, vol_sup, vol_conf = evaluate_volume(market_state, direction)
        regime_score, regime_sup, regime_conf = evaluate_regime(market_state, direction)
        session_score, session_sup, session_conf = evaluate_session(market_state, direction)
        mtf_score, mtf_sup, mtf_conf = evaluate_mtf(market_state, direction)
        corr_score, corr_sup, corr_conf = evaluate_correlation(market_state, direction)
        pat_score, pat_sup, pat_conf = evaluate_pattern(market_state, pattern_state, direction)
        qual_score, qual_sup, qual_conf = evaluate_quality(market_state, pattern_state, direction)

        # Aggregate supporting and conflicting factors
        supporting_factors = []
        supporting_factors.extend(trend_sup)
        supporting_factors.extend(struct_sup)
        supporting_factors.extend(liq_sup)
        supporting_factors.extend(zone_sup)
        supporting_factors.extend(vol_sup)
        supporting_factors.extend(regime_sup)
        supporting_factors.extend(session_sup)
        supporting_factors.extend(mtf_sup)
        supporting_factors.extend(corr_sup)
        supporting_factors.extend(pat_sup)
        supporting_factors.extend(qual_sup)

        conflicting_factors = []
        conflicting_factors.extend(trend_conf)
        conflicting_factors.extend(struct_conf)
        conflicting_factors.extend(liq_conf)
        conflicting_factors.extend(zone_conf)
        conflicting_factors.extend(vol_conf)
        conflicting_factors.extend(regime_conf)
        conflicting_factors.extend(session_conf)
        conflicting_factors.extend(mtf_conf)
        conflicting_factors.extend(corr_conf)
        conflicting_factors.extend(pat_conf)
        conflicting_factors.extend(qual_conf)

        # Calculate positive weighted sum
        weighted_sum = (
            trend_score * self._weights["trend"]
            + struct_score * self._weights["structure"]
            + liq_score * self._weights["liquidity"]
            + zone_score * self._weights["zone"]
            + vol_score * self._weights["volume"]
            + regime_score * self._weights["regime"]
            + session_score * self._weights["session"]
            + mtf_score * self._weights["mtf"]
            + corr_score * self._weights["correlation"]
            + pat_score * self._weights["pattern"]
            + qual_score * self._weights["quality"]
        )

        base_score = weighted_sum / 1.06

        # Calculate conflict penalty
        conflict_penalty = self._conflict_engine.calculate_penalty(conflicting_factors)

        # Final score
        overall_score = max(0.0, min(100.0, base_score - conflict_penalty))

        # Build intermediate score for risk flag and opportunity evaluation
        intermediate_score = ConfluenceScore(
            overall_score=round(overall_score, 2),
            setup_grade=SetupGrade.NO_TRADE,  # placeholder
            trend_score=round(trend_score, 2),
            structure_score=round(struct_score, 2),
            liquidity_score=round(liq_score, 2),
            zone_score=round(zone_score, 2),
            volume_score=round(vol_score, 2),
            regime_score=round(regime_score, 2),
            session_score=round(session_score, 2),
            mtf_score=round(mtf_score, 2),
            correlation_score=round(corr_score, 2),
            pattern_score=round(pat_score, 2),
            quality_score=round(qual_score, 2),
            conflict_penalty=round(conflict_penalty, 2),
            supporting_factors=supporting_factors,
            conflicting_factors=conflicting_factors,
        )

        # Sprint 6: Risk Flags → Grade → Opportunity → Explanation
        risk_flags = self._risk_flag_engine.evaluate(market_state, intermediate_score)
        grade = self._grade_engine.assign_grade(overall_score, risk_flags)
        opportunity = self._opportunity_engine.evaluate(market_state, intermediate_score)
        explanation = self._explanation_engine.explain(
            intermediate_score, opportunity, risk_flags, grade
        )

        return ConfluenceScore(
            overall_score=round(overall_score, 2),
            setup_grade=grade,
            trend_score=round(trend_score, 2),
            structure_score=round(struct_score, 2),
            liquidity_score=round(liq_score, 2),
            zone_score=round(zone_score, 2),
            volume_score=round(vol_score, 2),
            regime_score=round(regime_score, 2),
            session_score=round(session_score, 2),
            mtf_score=round(mtf_score, 2),
            correlation_score=round(corr_score, 2),
            pattern_score=round(pat_score, 2),
            quality_score=round(qual_score, 2),
            conflict_penalty=round(conflict_penalty, 2),
            supporting_factors=supporting_factors,
            conflicting_factors=conflicting_factors,
            opportunity=opportunity,
            risk_flags=risk_flags,
            explanation=explanation,
        )
