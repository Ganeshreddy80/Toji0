"""Position sizing models and schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any


@dataclass
class SizingConfig:
    """Config parameters for position sizing and capital allocation."""
    method: str = "fixed_risk"
    risk_percent: float = 0.01
    default_price: float = 50000.0
    max_portfolio_exposure_pct: float = 0.50
    max_symbol_exposure_pct: float = 0.20
    max_position_qty_cap: float = 1000.0
    target_volatility: float = 0.10
    # FP-3D: Maximum leverage scalar cap for the volatility sizing formula.
    # Consistent with VolatilityTargetingEngine (min(2.0, scale)) and PortfolioRebalancer.
    max_leverage: float = 2.0
    # FP-3D: Fallback annualized volatility when Feature Platform is unavailable or in warm-up.
    # 0.50 = 50% annualized — conservative estimate used as a risk-policy floor, not a measured value.
    # This replaces the previous 0.02 ("2% daily") fallback which was at a different scale.
    fallback_volatility: float = 0.50
    win_rate: float = 0.55
    payoff_ratio: float = 2.0
    kelly_leverage_frac: float = 0.5
    max_open_positions: int = 10
    fallback_balance: float = 100000.0



@dataclass
class SizingResult:
    """Result of a position sizing calculation."""
    symbol: str
    direction: str
    method: str
    raw_qty: float
    final_qty: float
    allocated_capital: float
    risk_amount: float
    price: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reasons: list[str] = field(default_factory=list)
