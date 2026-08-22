"""Reports generator service for compiling quantitative performance summaries."""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from analytics.statistics.calculator import StatsCalculator
from analytics.risk_metrics.calculator import RiskMetricsCalculator
from analytics.portfolio.attribution import PerformanceAttributor


class ReportGenerator:
    """Compiles statistics, backtest data, and portfolio attributions into reports."""

    @staticmethod
    def generate_analytics_report(
        returns: pd.Series | np.ndarray,
        periods_per_year: int = 252,
        risk_free_rate: float = 0.0,
    ) -> dict[str, Any]:
        """Aggregate returns statistical distribution metrics into an Analytics Report."""
        ret_arr = np.asarray(returns)
        if len(ret_arr) == 0:
            return {"status": "No data"}
            
        cagr = StatsCalculator.calculate_cagr(ret_arr, periods_per_year)
        sharpe = StatsCalculator.sharpe_ratio(ret_arr, risk_free_rate, periods_per_year)
        sortino = StatsCalculator.sortino_ratio(ret_arr, risk_free_rate, target_return=0.0, periods_per_year=periods_per_year)
        omega = StatsCalculator.omega_ratio(ret_arr, threshold=0.0)
        ulcer = StatsCalculator.ulcer_index(ret_arr)
        
        return {
            "report_type": "Analytics Report",
            "metrics": {
                "cagr": cagr,
                "sharpe_ratio": sharpe,
                "sortino_ratio": sortino,
                "omega_ratio": omega,
                "ulcer_index": ulcer,
                "mean_return": float(np.mean(ret_arr)),
                "volatility": float(np.std(ret_arr, ddof=1)),
                "total_observations": len(ret_arr),
            }
        }

    @staticmethod
    def generate_backtest_report(
        runner_instance: Any,  # StrategyRunner
    ) -> dict[str, Any]:
        """Aggregate ledger trades and equity curves into a Backtest Report."""
        ledger = runner_instance.ledger
        eq_curve = runner_instance.get_equity_curve()
        returns = runner_instance.get_returns()
        
        total_trades = len(ledger)
        total_commission = sum(t.commission for t in ledger)
        total_slippage = sum(t.slippage for t in ledger)
        
        final_equity = eq_curve.iloc[-1] if not eq_curve.empty else runner_instance.initial_cash
        net_profit = final_equity - runner_instance.initial_cash
        
        max_dd = RiskMetricsCalculator.maximum_drawdown(eq_curve.values) if not eq_curve.empty else 0.0
        
        # Win rate & profit factor calculation
        pnls = np.array([t.realized_pnl for t in ledger])
        wins = pnls[pnls > 0.0]
        losses = pnls[pnls < 0.0]
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
        profit_factor = StatsCalculator.profit_factor(pnls)
        expectancy = StatsCalculator.expectancy(pnls)
        
        return {
            "report_type": "Backtest Report",
            "summary": {
                "initial_cash": runner_instance.initial_cash,
                "final_equity": final_equity,
                "net_profit": net_profit,
                "max_drawdown": max_dd,
                "total_trades": total_trades,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "expectancy": expectancy,
                "total_commission_paid": total_commission,
                "total_slippage_incurred": total_slippage,
            },
            "has_warnings": (final_equity <= 0.0)
        }

    @staticmethod
    def generate_risk_report(
        returns: pd.Series | np.ndarray,
        equity_curve: pd.Series | np.ndarray,
        positions_value: dict[str, float],
        total_equity: float,
        confidence_level: float = 0.95,
    ) -> dict[str, Any]:
        """Aggregate tail-risk thresholds and exposure into a Risk Report."""
        ret_arr = np.asarray(returns)
        eq_arr = np.asarray(equity_curve)
        
        var_hist = RiskMetricsCalculator.value_at_risk(ret_arr, confidence_level, method="historical")
        var_param = RiskMetricsCalculator.value_at_risk(ret_arr, confidence_level, method="parametric")
        cvar = RiskMetricsCalculator.conditional_value_at_risk(ret_arr, confidence_level)
        max_dd = RiskMetricsCalculator.maximum_drawdown(eq_arr)
        
        net_exp, gross_exp = RiskMetricsCalculator.portfolio_exposure(positions_value, total_equity)
        
        return {
            "report_type": "Risk Report",
            "risk_metrics": {
                "var_historical": var_hist,
                "var_parametric": var_param,
                "cvar": cvar,
                "max_drawdown": max_dd,
                "net_exposure": net_exp,
                "gross_exposure": gross_exp,
            }
        }

    @staticmethod
    def generate_portfolio_report(
        weights: dict[str, float],
        returns_df: pd.DataFrame,
    ) -> dict[str, Any]:
        """Aggregate correlations and risk contributions into a Portfolio Report."""
        risk_contrib = PerformanceAttributor.calculate_risk_contribution(weights, returns_df)
        div_ratio = PerformanceAttributor.diversification_ratio(weights, returns_df)
        corr_mat = returns_df.corr().to_dict()
        
        return {
            "report_type": "Portfolio Report",
            "allocation_weights": weights,
            "diversification_ratio": div_ratio,
            "risk_attribution": risk_contrib,
            "correlation_matrix": corr_mat,
        }

    @staticmethod
    def generate_optimization_report(
        sweeps_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Aggregate parameters sweep comparisons into an Optimization Report."""
        if not sweeps_results:
            return {"report_type": "Optimization Report", "sweeps_count": 0, "best_trial": {}}
            
        best = sweeps_results[0]
        return {
            "report_type": "Optimization Report",
            "sweeps_count": len(sweeps_results),
            "best_trial": best,
            "worst_trial": sweeps_results[-1],
        }
