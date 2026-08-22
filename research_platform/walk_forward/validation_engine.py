"""Validation engine updating optimization window performance scores.
"""

from __future__ import annotations

from research_platform.walk_forward.interfaces import IValidationEngine
from research_platform.walk_forward.models import ValidationWindow


class ValidationEngine(IValidationEngine):
    """Binds train/test scores to windows."""

    def validate_window(self, window: ValidationWindow, in_sample_sharpe: float, out_of_sample_sharpe: float) -> ValidationWindow:
        return window.model_copy(update={
            "in_sample_sharpe": in_sample_sharpe,
            "out_of_sample_sharpe": out_of_sample_sharpe
        })
