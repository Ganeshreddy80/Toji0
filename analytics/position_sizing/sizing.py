"""Position sizing models for calculating execution share and contract quantities."""

from __future__ import annotations


class PositionSizer:
    """Computes target transaction sizes and weights for active strategies."""

    @staticmethod
    def kelly_sizing(win_rate: float, win_loss_ratio: float, leverage_fraction: float = 1.0) -> float:
        """Calculate Kelly-based allocation sizing fraction.
        
        Sizing = Leverage_Fraction * (Win_Rate - (1 - Win_Rate) / Win_Loss_Ratio)
        """
        if win_loss_ratio <= 0.0:
            return 0.0
        raw_kelly = win_rate - (1.0 - win_rate) / win_loss_ratio
        kelly = max(0.0, raw_kelly)
        return float(kelly * leverage_fraction)

    @staticmethod
    def volatility_adjusted_sizing(
        total_equity: float,
        target_risk_pct: float,
        asset_volatility: float,  # annualized standard deviation fraction (e.g. 0.3 for 30%)
        price: float,
    ) -> float:
        """Size position such that volatility matches target portfolio risk.
        
        Formula: Qty = (Equity * Target_Risk_Pct) / (Asset_Volatility * Price)
        """
        if asset_volatility <= 0.0 or price <= 0.0:
            return 0.0
        cash_risk = total_equity * target_risk_pct
        vol_dollar = price * asset_volatility
        return float(cash_risk / vol_dollar)

    @staticmethod
    def equal_risk_sizing(
        total_equity: float,
        target_risk_pct: float,
        stop_loss_distance: float,  # Stop loss distance in absolute price
    ) -> float:
        """Size position such that hitting the stop loss loses a fixed fraction of total equity.
        
        Formula: Qty = (Equity * Target_Risk_Pct) / Stop_Loss_Distance
        """
        if stop_loss_distance <= 0.0:
            return 0.0
        cash_risk = total_equity * target_risk_pct
        return float(cash_risk / stop_loss_distance)

    @staticmethod
    def fixed_fractional_sizing(
        total_equity: float,
        fraction: float,
        price: float,
    ) -> float:
        """Size position based on a static fixed cash allocation fraction.
        
        Formula: Qty = (Equity * Fraction) / Price
        """
        if price <= 0.0:
            return 0.0
        return float((total_equity * fraction) / price)
