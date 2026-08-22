"""Factor Model calculating portfolio exposure to style factors (Momentum, Value, Volatility).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict

from research_platform.portfolio_engine.interfaces import IFactorModel
from research_platform.portfolio_engine.models import FactorExposure, PortfolioWeights


class FactorModel(IFactorModel):
    """Calculates style factor loadings and residual risk exposure metrics."""

    def calculate_exposures(self, weights: PortfolioWeights, returns_df: pd.DataFrame) -> FactorExposure:
        """Compute portfolio exposure weights against size, momentum, value factors.

        Expected returns_df: columns are assets, index are dates.
        """
        symbols = list(weights.weights.keys())
        exposures = {}
        factor_loadings = {"market": 0.0, "momentum": 0.0, "volatility": 0.0}

        if returns_df.empty or len(returns_df) < 5:
            exposures = {sym: {"market": 1.0, "momentum": 0.0, "volatility": 0.0} for sym in symbols}
        else:
            # 1. Compute rolling stats for each symbol
            # Market proxy is equal-weighted returns index
            mkt_returns = returns_df.mean(axis=1)
            
            for sym in symbols:
                if sym not in returns_df.columns:
                    exposures[sym] = {"market": 1.0, "momentum": 0.0, "volatility": 0.0}
                    continue

                asset_ret = returns_df[sym]
                
                # Market Beta
                cov = np.cov(asset_ret, mkt_returns)
                beta = float(cov[0, 1] / (cov[1, 1] + 1e-10)) if cov.ndim == 2 else 1.0

                # Momentum (cumulative 5-day return)
                mom = float(asset_ret.tail(5).sum())

                # Volatility (annualized std)
                vol = float(asset_ret.std() * np.sqrt(252.0))

                exposures[sym] = {
                    "market": beta,
                    "momentum": mom,
                    "volatility": vol
                }

                # Scale by asset weights to get aggregate portfolio factor loading
                w_val = weights.weights.get(sym, 0.0)
                factor_loadings["market"] += beta * w_val
                factor_loadings["momentum"] += mom * w_val
                factor_loadings["volatility"] += vol * w_val

        return FactorExposure(
            exposures=exposures,
            factor_loadings=factor_loadings
        )
