"""Covariance Engine estimating rolling, EWMA, and shrunk covariance matrices.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import List

from research_platform.portfolio_engine.interfaces import ICovarianceEngine
from research_platform.portfolio_engine.models import CovarianceMatrix


class CovarianceEngine(ICovarianceEngine):
    """Computes return covariances and correlation matrices using various statistical models."""

    def __init__(self, method: str = "rolling", decay: float = 0.94) -> None:
        self.method = method
        self.decay = decay

    def calculate_covariance(self, returns_df: pd.DataFrame) -> CovarianceMatrix:
        """Estimate return covariances across returns matrix DataFrame."""
        symbols = list(returns_df.columns)
        
        if returns_df.empty or len(returns_df) < 2:
            # Fallback identity matrix
            size = len(symbols)
            cov_mat = np.eye(size) * 0.0001
        elif self.method == "ewma":
            cov_mat = self._ewma_covariance(returns_df, self.decay)
        elif self.method == "shrinkage":
            cov_mat = self._shrinkage_covariance(returns_df)
        else:
            # Standard rolling sample covariance
            cov_mat = returns_df.cov().to_numpy()

        # Convert back to clean matrix representation list-of-lists
        matrix_list = cov_mat.tolist()

        return CovarianceMatrix(
            matrix=matrix_list,
            symbols=symbols,
            timestamp=datetime.now(timezone.utc)
        )

    def _ewma_covariance(self, df: pd.DataFrame, decay: float) -> np.ndarray:
        """Calculate exponentially weighted moving average covariance matrix."""
        returns = df.to_numpy()
        n, m = returns.shape
        cov = np.zeros((m, m))
        
        # Exponential weights
        weights = (1.0 - decay) * (decay ** np.arange(n - 1, -1, -1))
        weights /= np.sum(weights)  # normalize

        mean = np.average(returns, axis=0, weights=weights)
        for i in range(n):
            diff = (returns[i] - mean).reshape(-1, 1)
            cov += weights[i] * np.dot(diff, diff.T)
            
        return cov

    def _shrinkage_covariance(self, df: pd.DataFrame, shrinkage_coef: float = 0.2) -> np.ndarray:
        """Ledoit-Wolf style constant correlation shrinkage estimator.

        Shrinks sample covariance matrix toward constant correlation target.
        """
        sample_cov = df.cov().to_numpy()
        m = sample_cov.shape[0]
        
        # Target matrix (constant correlation)
        variances = np.diag(sample_cov)
        std_devs = np.sqrt(variances)
        
        corr_matrix = df.corr().to_numpy()
        # Find average correlation
        avg_corr = (np.sum(corr_matrix) - m) / (m * m - m) if m > 1 else 0.0
        
        target_corr = np.eye(m) + avg_corr * (np.ones((m, m)) - np.eye(m))
        target_cov = np.diag(std_devs) @ target_corr @ np.diag(std_devs)

        # Shrunk matrix
        shrunk_cov = (1.0 - shrinkage_coef) * sample_cov + shrinkage_coef * target_cov
        return shrunk_cov
