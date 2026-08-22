"""Drift Detection (Population Stability Index - PSI, KL Divergence, Jensen-Shannon Divergence).
"""

from __future__ import annotations

import math
import numpy as np
from typing import Tuple

from research_platform.validation_core.models import DriftValidationResult


class DriftDetector:
    """Audits distribution drift and concept drift in quantitative features."""

    @staticmethod
    def calculate_kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
        """Calculate Kullback-Leibler Divergence."""
        # Add epsilon to prevent log(0) or division by zero
        eps = 1e-10
        p = p + eps
        q = q + eps
        # Normalize
        p /= np.sum(p)
        q /= np.sum(q)
        return float(np.sum(p * np.log(p / q)))

    @classmethod
    def calculate_js_divergence(cls, p: np.ndarray, q: np.ndarray) -> float:
        """Calculate Jensen-Shannon Divergence (square root is JSD distance)."""
        eps = 1e-10
        p = (p + eps) / (np.sum(p) + eps)
        q = (q + eps) / (np.sum(q) + eps)
        
        m = 0.5 * (p + q)
        kl_pm = cls.calculate_kl_divergence(p, m)
        kl_qm = cls.calculate_kl_divergence(q, m)
        return float(0.5 * kl_pm + 0.5 * kl_qm)

    @classmethod
    def calculate_psi(cls, baseline: np.ndarray, target: np.ndarray, bins: int = 10) -> float:
        """Calculate Population Stability Index (PSI)."""
        # Determine bin edges from baseline
        if len(baseline) == 0 or len(target) == 0:
            return 0.0

        percentiles = np.linspace(0, 100, bins + 1)
        bin_edges = np.percentile(baseline, percentiles)
        
        # Avoid duplicate bin edges
        bin_edges = np.unique(bin_edges)
        if len(bin_edges) < 2:
            return 0.0

        # Calculate counts
        base_counts, _ = np.histogram(baseline, bins=bin_edges)
        target_counts, _ = np.histogram(target, bins=bin_edges)

        # Normalize to get percentages
        eps = 1e-4
        base_pcts = (base_counts + eps) / (len(baseline) + eps)
        target_pcts = (target_counts + eps) / (len(target) + eps)

        # PSI = sum( (actual - expected) * ln(actual / expected) )
        psi = np.sum((target_pcts - base_pcts) * np.log(target_pcts / base_pcts))
        return float(psi)

    @classmethod
    def detect_drift(
        cls,
        feature_name: str,
        baseline_values: np.ndarray,
        target_values: np.ndarray
    ) -> DriftValidationResult:
        """Evaluate distribution drift metrics."""
        psi = cls.calculate_psi(baseline_values, target_values)
        
        # Calculate histograms for KL/JS
        min_val = min(np.min(baseline_values), np.min(target_values))
        max_val = max(np.max(baseline_values), np.max(target_values))
        
        edges = np.linspace(min_val, max_val, 11)
        base_hist, _ = np.histogram(baseline_values, bins=edges)
        target_hist, _ = np.histogram(target_values, bins=edges)

        kl = cls.calculate_kl_divergence(base_hist, target_hist)
        js = cls.calculate_js_divergence(base_hist, target_hist)

        # Categorize severity
        # Standard PSI rules: PSI < 0.1 (none), 0.1 <= PSI < 0.25 (low), PSI >= 0.25 (high)
        if psi < 0.1:
            severity = "NONE"
        elif psi < 0.25:
            severity = "LOW"
        else:
            severity = "HIGH"

        return DriftValidationResult(
            feature_name=feature_name,
            psi=psi,
            kl_divergence=kl,
            js_divergence=js,
            severity=severity
        )
