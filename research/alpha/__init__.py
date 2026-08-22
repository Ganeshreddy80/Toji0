"""Alpha factors catalog, scoring, and analysis models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AlphaFactor(BaseModel):
    """Canonical model for tracking a mathematical trading factor (Alpha)."""

    factor_id: str = Field(...)
    name: str = Field(..., description="Descriptive name of factor (e.g. Mean Reversion 5m)")
    formula_expr: str = Field(..., description="Logical expression logic (e.g. (close - sma) / std)")
    expected_regime: str = Field(..., description="Target market regime (e.g. ranging, high_volatility)")
    ic_score: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Rolling Information Coefficient score"
    )
    t_stat: float = Field(default=0.0, description="Calculated t-statistic for factor significance")

    model_config = {"frozen": True}
