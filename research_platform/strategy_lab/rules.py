"""Declarative rule evaluation engine for entries and exits.
"""

from __future__ import annotations

import pandas as pd
from typing import Any, Dict, List


class RuleEvaluator:
    """Evaluates entry triggers and exit conditions over market DataFrames."""

    @staticmethod
    def evaluate_entry(condition_type: str, params: Dict[str, Any], df: pd.DataFrame) -> pd.Series:
        """Evaluate a single entry rule and return a boolean Series of signals.

        Supported types:
            - SignalThreshold: evaluates signal column > threshold.
            - Crossover: fast crosses slow.
            - Momentum: signal changes direction.
        """
        if df.empty:
            return pd.Series(dtype=bool)

        if condition_type == "SignalThreshold":
            col = params.get("column", "close")
            threshold = params.get("threshold", 0.0)
            operator = params.get("operator", ">")
            
            if col not in df.columns:
                return pd.Series(False, index=df.index)

            if operator == ">":
                return df[col] > threshold
            elif operator == "<":
                return df[col] < threshold
            else:
                return df[col] == threshold

        elif condition_type == "Crossover":
            fast_col = params.get("fast_column")
            slow_col = params.get("slow_column")
            
            if fast_col not in df.columns or slow_col not in df.columns:
                return pd.Series(False, index=df.index)

            # crossover means: fast_t > slow_t and fast_{t-1} <= slow_{t-1}
            fast = df[fast_col]
            slow = df[slow_col]
            return (fast > slow) & (fast.shift(1) <= slow.shift(1))

        # Default fallback
        return pd.Series(False, index=df.index)

    @staticmethod
    def evaluate_exit(
        condition_type: str,
        params: Dict[str, Any],
        df: pd.DataFrame,
        entry_price: float,
        current_idx: int
    ) -> bool:
        """Evaluate a single exit rule at a specific row index.

        Supported types:
            - StopLoss: price falls below threshold percentage or fixed amount.
            - ProfitTarget: price rises above target percentage.
            - Fixed: fixed hold periods.
        """
        if df.empty or current_idx >= len(df):
            return False

        current_price = float(df["close"].iloc[current_idx])

        if condition_type == "StopLoss":
            pct = params.get("stop_pct", 0.02)
            stop_price = entry_price * (1.0 - pct)
            return current_price <= stop_price

        elif condition_type == "ProfitTarget":
            pct = params.get("target_pct", 0.05)
            target_price = entry_price * (1.0 + pct)
            return current_price >= target_price

        elif condition_type == "Fixed":
            hold_bars = params.get("hold_bars", 5)
            # Find entry row index to calculate elapsed periods
            entry_idx = params.get("entry_index", 0)
            return (current_idx - entry_idx) >= hold_bars

        return False

    @classmethod
    def evaluate_logical(cls, operator: str, rules_signals: List[pd.Series]) -> pd.Series:
        """Combine boolean Series using logical operators AND, OR, or NOT."""
        if not rules_signals:
            return pd.Series(dtype=bool)

        result = rules_signals[0]
        for signal in rules_signals[1:]:
            if operator == "AND":
                result = result & signal
            elif operator == "OR":
                result = result | signal

        if operator == "NOT":
            result = ~result

        return result
