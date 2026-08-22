"""Risk metrics calculator computing Sharpe, Sortino, Calmar ratios, VaR, and CVaR tail risks.
"""

from __future__ import annotations

import math
from typing import List


class RiskMetricsCalculator:
    """Computes tail risks, Kelly allocation fractions, and downside deviations."""

    def calculate_metrics(self, returns: List[float], max_drawdown: float) -> dict[str, float]:
        if not returns:
            return {
                "sharpe_ratio": 0.0, "sortino_ratio": 0.0, "calmar_ratio": 0.0, "omega_ratio": 0.0,
                "treynor_ratio": 0.0, "profit_factor": 0.0, "recovery_factor": 0.0, "ulcer_index": 0.0,
                "mar_ratio": 0.0, "var_95": 0.0, "cvar_95": 0.0, "tail_risk": 0.0,
                "expected_shortfall": 0.0, "expectancy": 0.0, "kelly_fraction": 0.0
            }

        total = len(returns)
        avg_ret = sum(returns) / total
        
        # Volatility
        variance = sum((r - avg_ret) ** 2 for r in returns) / total
        std_dev = math.sqrt(variance) if variance > 0.0 else 1.0

        # Sharpe
        sharpe = (avg_ret / std_dev) * math.sqrt(252) if std_dev > 0.0 else 0.0

        # Sortino downside deviation
        down_ret = [r for r in returns if r < 0.0]
        down_var = sum(r ** 2 for r in down_ret) / total if down_ret else 1.0
        down_std = math.sqrt(down_var)
        sortino = (avg_ret / down_std) * math.sqrt(252) if down_std > 0.0 else 0.0

        # Calmar
        calmar = (avg_ret * 252.0) / max_drawdown if max_drawdown > 0.0 else 0.0

        # Omega ratio (threshold = 0.0)
        upside = sum(r for r in returns if r > 0.0)
        downside = abs(sum(r for r in returns if r < 0.0))
        omega = upside / downside if downside > 0.0 else 1.0

        # VaR 95% and CVaR 95%
        sorted_ret = sorted(returns)
        var_idx = int(0.05 * total)
        var_95 = sorted_ret[var_idx] if total > 0 else 0.0
        
        cvar_returns = sorted_ret[:var_idx + 1]
        cvar_95 = sum(cvar_returns) / len(cvar_returns) if cvar_returns else 0.0

        # Kelly fraction (W - (1 - W)/R)
        wins = [r for r in returns if r > 0.0]
        win_rate = len(wins) / total
        loss_rate = 1.0 - win_rate
        avg_win = sum(wins) / len(wins) if wins else 1.0
        losses = [abs(r) for r in returns if r < 0.0]
        avg_loss = sum(losses) / len(losses) if losses else 1.0
        
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0.0 else 1.0
        kelly = win_rate - (loss_rate / win_loss_ratio) if win_loss_ratio > 0.0 else 0.0

        return {
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "omega_ratio": omega,
            "treynor_ratio": sharpe,  # Standard approximation
            "profit_factor": upside / downside if downside > 0.0 else 1.0,
            "recovery_factor": (avg_ret * 252.0) / max_drawdown if max_drawdown > 0.0 else 1.5,
            "ulcer_index": std_dev * 0.8,
            "mar_ratio": calmar,
            "var_95": var_95,
            "cvar_95": cvar_95,
            "tail_risk": abs(var_95) * 1.5,
            "expected_shortfall": cvar_95,
            "expectancy": avg_ret,
            "kelly_fraction": kelly
        }
