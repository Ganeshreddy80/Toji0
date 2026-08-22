"""Strategy Eligibility Evaluator based on market regime and health metrics."""

from __future__ import annotations

from pydantic import BaseModel, Field
from intelligence.models import MarketPulse


class StrategyEligibilityConstraints(BaseModel):
    """Configuration constraints for strategy execution eligibility."""

    strategy_id: str = Field(..., description="Unique strategy ID")
    target_regimes: list[str] = Field(
        ..., description="Regime phases where strategy is valid (e.g. ['Markup', 'Expansion'])"
    )
    min_market_health: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum market pulse overall score")
    max_market_risk: float = Field(default=1.0, ge=0.0, le=1.0, description="Maximum market pulse risk level")
    max_volatility: float = Field(default=float("inf"), description="Maximum volatility allowance")

    model_config = {"frozen": True}


class StrategyEligibilityEvaluator:
    """Evaluates whether strategies conform to the current market regime and pulse conditions."""

    def evaluate(
        self,
        constraints: StrategyEligibilityConstraints,
        pulse: MarketPulse,
        current_regime: str,
    ) -> tuple[bool, str]:
        """Determine if the strategy is eligible under the given market pulse and regime.

        Args:
            constraints: StrategyEligibilityConstraints.
            pulse: The latest MarketPulse object.
            current_regime: Current detected regime phase.

        Returns:
            Tuple of (is_eligible, reason_description).
        """
        # 1. Regime Phase Check
        # Normalize comparison to case-insensitive or exact
        normalized_regime = current_regime.strip().lower()
        normalized_targets = [r.strip().lower() for r in constraints.target_regimes]

        if normalized_regime not in normalized_targets:
            return (
                False,
                f"Regime mismatch: Current regime '{current_regime}' is not in strategy targets {constraints.target_regimes}",
            )

        # 2. Market Health check
        if pulse.overall_score < constraints.min_market_health:
            return (
                False,
                f"Low market health: Overall score {pulse.overall_score:.2f} is below minimum requirement {constraints.min_market_health:.2f}",
            )

        # 3. Market Risk check
        if pulse.risk > constraints.max_market_risk:
            return (
                False,
                f"High market risk: Risk level {pulse.risk:.2f} exceeds maximum allowance {constraints.max_market_risk:.2f}",
            )

        # 4. Volatility check
        if pulse.volatility > constraints.max_volatility:
            return (
                False,
                f"High volatility: Volatility {pulse.volatility:.4f} exceeds maximum allowance {constraints.max_volatility:.4f}",
            )

        return True, "Eligible"
