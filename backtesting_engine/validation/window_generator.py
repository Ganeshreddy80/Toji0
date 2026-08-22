"""Chronological window generator for walk-forward validation (Sprint 8B)."""

from __future__ import annotations

import abc
from typing import List, Optional

from backtesting_engine.core.exceptions import WalkForwardValidationError
from backtesting_engine.core.models import MarketBar
from backtesting_engine.validation.models.validation import (
    ValidationMethod,
    ValidationWindow,
    WalkForwardConfig,
)


class IWindowGeneratorStrategy(abc.ABC):
    """Abstract interface for walk-forward window generation strategies (Open/Closed Principle)."""

    @abc.abstractmethod
    def generate_windows(
        self,
        bars: List[MarketBar],
        config: WalkForwardConfig,
    ) -> List[ValidationWindow]:
        """Generate chronological non-overlapping validation windows."""


class RollingWindowStrategy(IWindowGeneratorStrategy):
    """Rolling window generator: fixed train window, fixed test window, sliding step_size."""

    def generate_windows(
        self,
        bars: List[MarketBar],
        config: WalkForwardConfig,
    ) -> List[ValidationWindow]:
        windows: List[ValidationWindow] = []
        n_bars = len(bars)
        tr_win = config.training_window
        te_win = config.testing_window
        step = config.step_size

        cursor = 0
        fold = 1

        while cursor + tr_win + te_win <= n_bars:
            train_start_idx = cursor
            train_end_idx = cursor + tr_win - 1
            test_start_idx = cursor + tr_win
            test_end_idx = cursor + tr_win + te_win - 1

            windows.append(
                ValidationWindow(
                    fold_number=fold,
                    train_start=bars[train_start_idx].timestamp,
                    train_end=bars[train_end_idx].timestamp,
                    test_start=bars[test_start_idx].timestamp,
                    test_end=bars[test_end_idx].timestamp,
                    train_start_idx=train_start_idx,
                    train_end_idx=train_end_idx,
                    test_start_idx=test_start_idx,
                    test_end_idx=test_end_idx,
                )
            )

            cursor += step
            fold += 1

        return windows


class ExpandingWindowStrategy(IWindowGeneratorStrategy):
    """Expanding window generator: train window grows from start, test window slides."""

    def generate_windows(
        self,
        bars: List[MarketBar],
        config: WalkForwardConfig,
    ) -> List[ValidationWindow]:
        windows: List[ValidationWindow] = []
        n_bars = len(bars)
        tr_win = config.training_window
        te_win = config.testing_window
        step = config.step_size

        train_end_idx = tr_win - 1
        fold = 1

        while train_end_idx + 1 + te_win <= n_bars:
            train_start_idx = 0
            test_start_idx = train_end_idx + 1
            test_end_idx = test_start_idx + te_win - 1

            windows.append(
                ValidationWindow(
                    fold_number=fold,
                    train_start=bars[train_start_idx].timestamp,
                    train_end=bars[train_end_idx].timestamp,
                    test_start=bars[test_start_idx].timestamp,
                    test_end=bars[test_end_idx].timestamp,
                    train_start_idx=train_start_idx,
                    train_end_idx=train_end_idx,
                    test_start_idx=test_start_idx,
                    test_end_idx=test_end_idx,
                )
            )

            train_end_idx += step
            fold += 1

        return windows


class AnchoredWindowStrategy(ExpandingWindowStrategy):
    """Anchored window generator: training anchored at first bar, test window slides (alias of Expanding)."""


class WindowGenerator:
    """Authoritative window generator with input validation and strategy routing."""

    def __init__(
        self,
        rolling_strategy: Optional[IWindowGeneratorStrategy] = None,
        expanding_strategy: Optional[IWindowGeneratorStrategy] = None,
        anchored_strategy: Optional[IWindowGeneratorStrategy] = None,
    ) -> None:
        self._strategies = {
            ValidationMethod.ROLLING: rolling_strategy or RollingWindowStrategy(),
            ValidationMethod.EXPANDING: expanding_strategy or ExpandingWindowStrategy(),
            ValidationMethod.ANCHORED: anchored_strategy or AnchoredWindowStrategy(),
        }

    def generate_windows(
        self,
        bars: List[MarketBar],
        config: WalkForwardConfig,
    ) -> List[ValidationWindow]:
        """Validate dataset and parameters, then generate chronological validation windows."""
        if not config:
            raise WalkForwardValidationError("Invalid WalkForwardConfig provided.")

        if not bars:
            raise WalkForwardValidationError("Cannot generate windows for an empty dataset.")

        n_bars = len(bars)
        if n_bars < config.minimum_history:
            raise WalkForwardValidationError(
                f"Insufficient historical data ({n_bars} bars). Required minimum: {config.minimum_history}."
            )

        if config.training_window <= 0 or config.testing_window <= 0 or config.step_size <= 0:
            raise WalkForwardValidationError("Window sizes and step_size must be strictly positive integers.")

        if n_bars < config.training_window + config.testing_window:
            raise WalkForwardValidationError(
                f"Dataset length ({n_bars} bars) is smaller than training + testing window ({config.training_window + config.testing_window})."
            )

        # Chronological order verification
        for i in range(1, n_bars):
            if bars[i].timestamp < bars[i - 1].timestamp:
                raise WalkForwardValidationError(
                    f"Market bars are not strictly chronological at index {i}: {bars[i].timestamp} < {bars[i-1].timestamp}."
                )

        strategy = self._strategies.get(config.validation_method)
        if not strategy:
            raise WalkForwardValidationError(f"Unsupported validation method: {config.validation_method}")

        windows = strategy.generate_windows(bars, config)
        if not windows:
            raise WalkForwardValidationError(
                f"No valid folds could be generated with given window parameters for dataset length {n_bars}."
            )

        return windows
