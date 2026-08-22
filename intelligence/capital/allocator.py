"""Capital Allocator for portfolio suggestions and risk budgeting."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SizingSuggestion(BaseModel):
    """Represent suggested capital allocation parameters for a single asset."""

    symbol: str = Field(...)
    target_percentage: float = Field(..., ge=0.0, le=1.0, description="Suggested allocation % of portfolio")
    suggested_amount: float = Field(..., ge=0.0, description="Absolute cash allocation amount")
    kelly_fraction: float = Field(..., description="Unscaled Kelly fraction calculated")
    is_capped: bool = Field(default=False, description="True if allocation was capped by risk budget")
    reason: str = Field(...)

    model_config = {"frozen": True}


class CapitalAllocator:
    """Calculates suggested allocation sizing based on fractional Kelly Criterion and risk limits."""

    def __init__(
        self,
        fractional_kelly: float = 0.25,  # Quarter Kelly standard
        max_portfolio_exposure: float = 0.80,  # 80% maximum total exposure
        default_payoff_ratio: float = 2.0,  # 2:1 Reward to Risk
    ) -> None:
        """Initialize the CapitalAllocator.

        Args:
            fractional_kelly: Fraction of Kelly criterion to use (e.g. 0.25 for quarter-Kelly).
            max_portfolio_exposure: Maximum combined portfolio allocation limit.
            default_payoff_ratio: Default reward-to-risk ratio if not specified.
        """
        self.fractional_kelly = fractional_kelly
        self.max_portfolio_exposure = max_portfolio_exposure
        self.default_payoff_ratio = default_payoff_ratio

    def calculate_kelly_fraction(self, win_rate: float, payoff_ratio: float) -> float:
        """Calculate the standard Kelly Criterion fraction.

        Formula: f = p - (1-p)/b
        where p is probability of win, b is payoff ratio (win_amount / loss_amount).
        """
        if payoff_ratio <= 0.0:
            return 0.0
        p = win_rate
        q = 1.0 - p
        f = p - (q / payoff_ratio)
        return max(0.0, f)

    def suggest_sizing(
        self,
        symbol: str,
        win_rate: float,
        payoff_ratio: float | None = None,
        confidence: float = 1.0,
        portfolio_value: float = 100000.0,
        risk_budget_pct: float = 0.05,  # 5% max risk budget per trade
    ) -> SizingSuggestion:
        """Suggest capital allocation for a single asset.

        Args:
            symbol: Ticker symbol.
            win_rate: Historical strategy win rate (0.0 to 1.0).
            payoff_ratio: Reward/risk ratio.
            confidence: Strategy/pulse confidence multiplier (0.0 to 1.0).
            portfolio_value: Current total portfolio value.
            risk_budget_pct: Maximum percentage allocation allowed for this asset.

        Returns:
            SizingSuggestion object.
        """
        b = payoff_ratio if payoff_ratio is not None else self.default_payoff_ratio
        f = self.calculate_kelly_fraction(win_rate, b)

        # Scale Kelly fraction
        scaled_f = f * self.fractional_kelly * confidence

        # Apply risk budget cap
        is_capped = False
        target_pct = scaled_f
        if target_pct > risk_budget_pct:
            target_pct = risk_budget_pct
            is_capped = True

        suggested_amount = target_pct * portfolio_value
        reason = (
            f"Sizing based on fractional Kelly ({scaled_f:.2%}) capped by risk budget ({risk_budget_pct:.2%})"
            if is_capped
            else f"Sizing based on fractional Kelly ({scaled_f:.2%})"
        )

        if target_pct <= 0.0:
            reason = "Negative or zero Kelly fraction (expected loss exceeds payoff)"

        return SizingSuggestion(
            symbol=symbol,
            target_percentage=target_pct,
            suggested_amount=suggested_amount,
            kelly_fraction=f,
            is_capped=is_capped,
            reason=reason,
        )

    def suggest_portfolio_allocations(
        self,
        opportunities: list[dict[str, Any]],
        portfolio_value: float,
        cash_available: float,
        correlations: dict[tuple[str, str], float] | None = None,
    ) -> list[SizingSuggestion]:
        """Suggest portfolio allocation sizes across multiple opportunities.

        Applies correlation penalties and clamps to available cash & max exposure limits.

        Args:
            opportunities: List of dicts, each with keys:
                           'symbol', 'win_rate', 'payoff_ratio', 'confidence', 'risk_budget_pct'.
            portfolio_value: Total value of the portfolio.
            cash_available: Total cash currency currently liquid.
            correlations: Optional dict of {(symbol_A, symbol_B): correlation_coefficient}.

        Returns:
            List of SizingSuggestion objects.
        """
        suggestions = []
        raw_pcts = {}

        # 1. Calculate raw suggested sizes
        for opp in opportunities:
            sym = opp["symbol"]
            win_rate = opp.get("win_rate", 0.5)
            payoff_ratio = opp.get("payoff_ratio", self.default_payoff_ratio)
            confidence = opp.get("confidence", 1.0)
            risk_budget_pct = opp.get("risk_budget_pct", 0.05)

            suggestion = self.suggest_sizing(
                symbol=sym,
                win_rate=win_rate,
                payoff_ratio=payoff_ratio,
                confidence=confidence,
                portfolio_value=portfolio_value,
                risk_budget_pct=risk_budget_pct,
            )
            raw_pcts[sym] = suggestion.target_percentage
            suggestions.append(suggestion)

        # 2. Apply Correlation Penalty
        # If asset A has high correlation to asset B, scale down their size to mitigate risk
        if correlations and len(suggestions) > 1:
            adjusted_pcts = {}
            for sym, pct in raw_pcts.items():
                avg_corr = 0.0
                corr_count = 0
                for other_sym in raw_pcts:
                    if sym == other_sym:
                        continue
                    # Check correlation dict key in either order
                    corr = correlations.get((sym, other_sym)) or correlations.get((other_sym, sym))
                    if corr is not None:
                        avg_corr += abs(corr)
                        corr_count += 1

                if corr_count > 0:
                    avg_corr = avg_corr / corr_count
                    # Penalty: if correlation is 1.0, scale down size by 50%.
                    penalty_factor = 1.0 - (0.5 * avg_corr)
                    adjusted_pcts[sym] = pct * penalty_factor
                else:
                    adjusted_pcts[sym] = pct
            raw_pcts = adjusted_pcts

        # 3. Constrain total allocations
        total_suggested_pct = sum(raw_pcts.values())
        max_pct = min(self.max_portfolio_exposure, cash_available / portfolio_value)

        # Scale down proportionally if total exceeds max permitted portfolio exposure or liquid cash
        scale_factor = 1.0
        if total_suggested_pct > max_pct and total_suggested_pct > 0.0:
            scale_factor = max_pct / total_suggested_pct

        final_suggestions = []
        for orig in suggestions:
            sym = orig.symbol
            pct = raw_pcts.get(sym, orig.target_percentage) * scale_factor
            amt = pct * portfolio_value
            reason = orig.reason
            if scale_factor < 1.0:
                reason += f" (scaled down by {scale_factor:.2f}x to satisfy portfolio limits)"

            final_suggestions.append(
                SizingSuggestion(
                    symbol=sym,
                    target_percentage=pct,
                    suggested_amount=amt,
                    kelly_fraction=orig.kelly_fraction,
                    is_capped=orig.is_capped or scale_factor < 1.0,
                    reason=reason,
                )
            )

        return final_suggestions
