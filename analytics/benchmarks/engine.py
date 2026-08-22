"""Benchmarking engine for comparing strategy equity curves against standard baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd


class BenchmarkEngine:
    """Simulates benchmark performance curves and computes comparative stats."""

    @staticmethod
    def buy_and_hold(prices: pd.Series, initial_cash: float = 100000.0) -> pd.Series:
        """Generate the equity curve of a Buy & Hold strategy.
        
        Buy at the first price, hold until the end.
        """
        if prices.empty:
            return pd.Series(dtype=float)
        first_price = prices.iloc[0]
        if first_price == 0.0:
            first_price = 1e-10
        ratio = prices / first_price
        return initial_cash * ratio

    @staticmethod
    def equal_weight(prices_df: pd.DataFrame, initial_cash: float = 100000.0) -> pd.Series:
        """Generate the equity curve of an Equal Weight rebalanced portfolio across multiple assets."""
        if prices_df.empty:
            return pd.Series(dtype=float)
            
        returns = prices_df.pct_change().fillna(0.0)
        # Rebalanced daily: simple average return across columns
        avg_returns = returns.mean(axis=1)
        
        cum_ret = (avg_returns + 1.0).cumprod()
        return initial_cash * cum_ret

    @staticmethod
    def random_entry(
        prices: pd.Series,
        initial_cash: float = 100000.0,
        num_runs: int = 50,
        trade_prob: float = 0.05,
    ) -> pd.Series:
        """Generate the average equity curve of a random entry-exit execution strategy.
        
        Runs a simulation of random entries and exits multiple times, then returns the mean equity curve.
        """
        if prices.empty:
            return pd.Series(dtype=float)
            
        n = len(prices)
        returns = prices.pct_change().fillna(0.0).values
        all_runs = np.zeros((num_runs, n))
        
        for r in range(num_runs):
            position = 0  # 0: flat, 1: long, -1: short
            equity = initial_cash
            equity_path = [equity]
            
            for i in range(1, n):
                # Random entry decision
                if position == 0:
                    if np.random.rand() < trade_prob:
                        position = np.random.choice([1, -1])
                else:
                    # Random exit decision
                    if np.random.rand() < trade_prob:
                        position = 0
                        
                ret = returns[i]
                if position == 1:
                    equity *= (1.0 + ret)
                elif position == -1:
                    equity *= (1.0 - ret)
                    
                equity_path.append(equity)
                
            all_runs[r] = equity_path
            
        mean_path = np.mean(all_runs, axis=0)
        return pd.Series(mean_path, index=prices.index)

    @staticmethod
    def compare_performance(
        strategy_equity: pd.Series,
        benchmark_equity: pd.Series,
        periods_per_year: int = 252,
    ) -> dict[str, float]:
        """Compute relative comparative metrics between strategy and benchmark equity curves."""
        if strategy_equity.empty or benchmark_equity.empty:
            return {}
            
        strat_returns = strategy_equity.pct_change().dropna()
        bench_returns = benchmark_equity.pct_change().dropna()
        
        # Align index
        common_idx = strat_returns.index.intersection(bench_returns.index)
        strat_returns = strat_returns.loc[common_idx]
        bench_returns = bench_returns.loc[common_idx]
        
        if len(strat_returns) < 2:
            return {}
            
        strat_ann_ret = float(np.mean(strat_returns) * periods_per_year)
        bench_ann_ret = float(np.mean(bench_returns) * periods_per_year)
        
        # Active premium
        active_premium = strat_ann_ret - bench_ann_ret
        
        # Tracking Error (Standard deviation of active returns)
        active_returns = strat_returns - bench_returns
        tracking_error = float(np.std(active_returns, ddof=1) * np.sqrt(periods_per_year))
        
        # Information Ratio
        if tracking_error == 0.0:
            ir = 0.0
        else:
            ir = active_premium / tracking_error
            
        return {
            "strategy_return": strat_ann_ret,
            "benchmark_return": bench_ann_ret,
            "active_premium": active_premium,
            "tracking_error": tracking_error,
            "information_ratio": ir,
        }
