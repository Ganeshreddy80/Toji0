"""Quantitative statistics calculators for portfolio and asset performance evaluation."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd


class StatsCalculator:
    """Institutional-grade statistics calculator for quantitative returns series."""

    @staticmethod
    def calculate_cagr(returns: pd.Series | np.ndarray, periods_per_year: int = 252) -> float:
        """Compute the Compound Annual Growth Rate (CAGR) of a return series."""
        n = len(returns)
        if n == 0:
            return 0.0
        
        # Convert to numpy for performance
        ret_arr = np.asarray(returns)
        cum_ret = np.prod(ret_arr + 1.0)
        
        if cum_ret <= 0.0:
            return -1.0  # Bankrupted or fully depleted
            
        years = n / periods_per_year
        if years == 0.0:
            return 0.0
        return float(cum_ret ** (1.0 / years) - 1.0)

    @staticmethod
    def sharpe_ratio(
        returns: pd.Series | np.ndarray,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> float:
        """Compute the annualized Sharpe Ratio.
        
        Formula: (Annualized Return - Risk Free Rate) / Annualized Volatility
        """
        ret_arr = np.asarray(returns)
        if len(ret_arr) < 2:
            return 0.0
            
        mean_ret = np.mean(ret_arr)
        std_ret = np.std(ret_arr, ddof=1)
        
        if std_ret == 0.0:
            return 0.0
            
        # Annualize
        ann_return = mean_ret * periods_per_year
        ann_vol = std_ret * math.sqrt(periods_per_year)
        
        return float((ann_return - risk_free_rate) / ann_vol)

    @staticmethod
    def sortino_ratio(
        returns: pd.Series | np.ndarray,
        risk_free_rate: float = 0.0,
        target_return: float = 0.0,
        periods_per_year: int = 252,
    ) -> float:
        """Compute the annualized Sortino Ratio.
        
        Formula: (Annualized Return - Risk Free Rate) / Annualized Downside Volatility
        """
        ret_arr = np.asarray(returns)
        if len(ret_arr) < 2:
            return 0.0
            
        mean_ret = np.mean(ret_arr)
        
        # Downside returns (only below target_return)
        excess = ret_arr - target_return
        downside_returns = excess[excess < 0.0]
        
        if len(downside_returns) == 0:
            return 0.0
            
        # Downside variance uses total periods N in denominator
        downside_var = np.sum(downside_returns ** 2) / len(ret_arr)
        downside_std = math.sqrt(downside_var)
        
        if downside_std == 0.0:
            return 0.0
            
        ann_return = mean_ret * periods_per_year
        ann_downside_vol = downside_std * math.sqrt(periods_per_year)
        
        return float((ann_return - risk_free_rate) / ann_downside_vol)

    @staticmethod
    def calmar_ratio(
        returns: pd.Series | np.ndarray,
        max_drawdown: float,
        periods_per_year: int = 252,
    ) -> float:
        """Compute the Calmar Ratio.
        
        Formula: Annualized Return (CAGR) / Max Drawdown
        """
        if max_drawdown == 0.0:
            return 0.0
        cagr = StatsCalculator.calculate_cagr(returns, periods_per_year)
        return float(cagr / abs(max_drawdown))

    @staticmethod
    def mar_ratio(
        returns: pd.Series | np.ndarray,
        max_drawdown: float,
        periods_per_year: int = 252,
    ) -> float:
        """Compute the MAR Ratio.
        
        Formula: Annualized Mean Return / Max Drawdown
        """
        if max_drawdown == 0.0:
            return 0.0
        ret_arr = np.asarray(returns)
        ann_return = np.mean(ret_arr) * periods_per_year
        return float(ann_return / abs(max_drawdown))

    @staticmethod
    def omega_ratio(returns: pd.Series | np.ndarray, threshold: float = 0.0) -> float:
        """Compute the Omega Ratio.
        
        Formula: Sum(max(r - threshold, 0)) / Sum(max(threshold - r, 0))
        """
        ret_arr = np.asarray(returns)
        if len(ret_arr) == 0:
            return 0.0
            
        excess = ret_arr - threshold
        gains = excess[excess > 0.0]
        losses = excess[excess < 0.0]
        
        sum_gains = np.sum(gains) if len(gains) > 0 else 0.0
        sum_losses = np.sum(np.abs(losses)) if len(losses) > 0 else 0.0
        
        if sum_losses == 0.0:
            return float("inf") if sum_gains > 0.0 else 0.0
            
        return float(sum_gains / sum_losses)

    @staticmethod
    def profit_factor(trades_pnl: pd.Series | np.ndarray) -> float:
        """Compute the Profit Factor.
        
        Formula: Sum(profits) / Sum(absolute losses)
        """
        pnl_arr = np.asarray(trades_pnl)
        if len(pnl_arr) == 0:
            return 0.0
            
        profits = pnl_arr[pnl_arr > 0.0]
        losses = pnl_arr[pnl_arr < 0.0]
        
        sum_profits = np.sum(profits) if len(profits) > 0 else 0.0
        sum_losses = np.sum(np.abs(losses)) if len(losses) > 0 else 0.0
        
        if sum_losses == 0.0:
            return float("inf") if sum_profits > 0.0 else 1.0
            
        return float(sum_profits / sum_losses)

    @staticmethod
    def expectancy(trades_pnl: pd.Series | np.ndarray) -> float:
        """Compute the Expectancy of a trade history.
        
        Formula: (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
        """
        pnl_arr = np.asarray(trades_pnl)
        n = len(pnl_arr)
        if n == 0:
            return 0.0
            
        wins = pnl_arr[pnl_arr > 0.0]
        losses = pnl_arr[pnl_arr < 0.0]
        
        win_rate = len(wins) / n
        loss_rate = len(losses) / n
        
        avg_win = np.mean(wins) if len(wins) > 0 else 0.0
        avg_loss = np.mean(np.abs(losses)) if len(losses) > 0 else 0.0
        
        return float((win_rate * avg_win) - (loss_rate * avg_loss))

    @staticmethod
    def recovery_factor(net_profit: float, max_drawdown: float) -> float:
        """Compute the Recovery Factor.
        
        Formula: Net Profit / Max Drawdown (expressed in absolute/percentage cash values)
        """
        if max_drawdown == 0.0:
            return 0.0
        return float(net_profit / abs(max_drawdown))

    @staticmethod
    def ulcer_index(returns: pd.Series | np.ndarray) -> float:
        """Compute the Ulcer Index of a returns series.
        
        Formula: sqrt(mean(drawdown_t^2))
        """
        ret_arr = np.asarray(returns)
        if len(ret_arr) == 0:
            return 0.0
            
        # Reconstruct cumulative equity curve
        cum_equity = np.cumprod(ret_arr + 1.0)
        # Add baseline 1.0 at start
        cum_equity = np.insert(cum_equity, 0, 1.0)
        
        # Calculate running maximums
        running_max = np.maximum.accumulate(cum_equity)
        
        # Drawdowns
        drawdowns = (cum_equity - running_max) / running_max
        
        # Ulcer index calculation
        squared_drawdowns = drawdowns ** 2
        mean_squared = np.mean(squared_drawdowns)
        return float(math.sqrt(mean_squared))

    @staticmethod
    def alpha_beta(
        returns: pd.Series | np.ndarray,
        benchmark_returns: pd.Series | np.ndarray,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> tuple[float, float]:
        """Compute Alpha and Beta against a benchmark.
        
        Formula: 
            Beta = Covariance(returns, benchmark) / Variance(benchmark)
            Alpha = Annualized Return - (Risk Free Rate + Beta * (Annualized Benchmark Return - Risk Free Rate))
        """
        ret_arr = np.asarray(returns)
        bench_arr = np.asarray(benchmark_returns)
        
        if len(ret_arr) < 2 or len(ret_arr) != len(bench_arr):
            return 0.0, 0.0
            
        cov_matrix = np.cov(ret_arr, bench_arr)
        cov = cov_matrix[0, 1]
        var_bench = cov_matrix[1, 1]
        
        if var_bench == 0.0:
            beta = 0.0
        else:
            beta = float(cov / var_bench)
            
        ann_ret = np.mean(ret_arr) * periods_per_year
        ann_bench_ret = np.mean(bench_arr) * periods_per_year
        
        alpha = float(ann_ret - (risk_free_rate + beta * (ann_bench_ret - risk_free_rate)))
        return alpha, beta

    @staticmethod
    def tracking_error(
        returns: pd.Series | np.ndarray,
        benchmark_returns: pd.Series | np.ndarray,
        periods_per_year: int = 252,
    ) -> float:
        """Compute the Tracking Error.
        
        Formula: Standard Deviation of Active Returns * sqrt(periods_per_year)
        """
        ret_arr = np.asarray(returns)
        bench_arr = np.asarray(benchmark_returns)
        
        if len(ret_arr) < 2 or len(ret_arr) != len(bench_arr):
            return 0.0
            
        active_returns = ret_arr - bench_arr
        active_std = np.std(active_returns, ddof=1)
        return float(active_std * math.sqrt(periods_per_year))

    @staticmethod
    def information_ratio(
        returns: pd.Series | np.ndarray,
        benchmark_returns: pd.Series | np.ndarray,
        periods_per_year: int = 252,
    ) -> float:
        """Compute the Information Ratio.
        
        Formula: (Annualized Return - Annualized Benchmark Return) / Tracking Error
        """
        ret_arr = np.asarray(returns)
        bench_arr = np.asarray(benchmark_returns)
        
        if len(ret_arr) < 2:
            return 0.0
            
        te = StatsCalculator.tracking_error(ret_arr, bench_arr, periods_per_year)
        if te == 0.0:
            return 0.0
            
        ann_ret = np.mean(ret_arr) * periods_per_year
        ann_bench_ret = np.mean(bench_arr) * periods_per_year
        
        return float((ann_ret - ann_bench_ret) / te)

    @staticmethod
    def correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate the Pearson correlation matrix of multiple returns series."""
        return returns_df.corr(method="pearson")

    @staticmethod
    def rolling_sharpe(
        returns: pd.Series,
        window: int,
        periods_per_year: int = 252,
        risk_free_rate: float = 0.0,
    ) -> pd.Series:
        """Calculate the rolling Sharpe Ratio over a specified window."""
        mean = returns.rolling(window).mean()
        std = returns.rolling(window).std(ddof=1)
        
        ann_mean = mean * periods_per_year
        ann_std = std * math.sqrt(periods_per_year)
        
        rolling_ratio = (ann_mean - risk_free_rate) / (ann_std + 1e-10)
        return rolling_ratio.fillna(0.0)

    @staticmethod
    def rolling_beta(
        returns: pd.Series,
        benchmark_returns: pd.Series,
        window: int,
    ) -> pd.Series:
        """Calculate the rolling Beta against a benchmark over a specified window."""
        cov = returns.rolling(window).cov(benchmark_returns)
        var = benchmark_returns.rolling(window).var()
        rolling_b = cov / (var + 1e-10)
        return rolling_b.fillna(0.0)
