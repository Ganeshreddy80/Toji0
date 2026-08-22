"""Monte Carlo equity path simulator engine (Sprint 8C)."""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from backtesting_engine.core.models import BacktestResult
from backtesting_engine.monte_carlo.bootstrap import (
    BlockBootstrap,
    IBootstrapStrategy,
    ReturnBootstrap,
    TradeBootstrap,
)
from backtesting_engine.monte_carlo.models.monte_carlo import (
    BootstrapMethod,
    MonteCarloConfig,
    SimulationResult,
)

logger = logging.getLogger(__name__)


class MonteCarloSimulator:
    """Generates N independent simulated equity paths from BacktestResult."""

    def __init__(
        self,
        config: Optional[MonteCarloConfig] = None,
        bootstrap_strategy: Optional[IBootstrapStrategy] = None,
    ) -> None:
        self.config = config or MonteCarloConfig()
        self.bootstrap_strategy = bootstrap_strategy

    @staticmethod
    def _select_bootstrap_strategy(config: MonteCarloConfig) -> IBootstrapStrategy:
        """Select bootstrap strategy based on configuration."""
        if config.bootstrap_method == BootstrapMethod.TRADE:
            return TradeBootstrap(preserve_trade_order=config.preserve_trade_order)
        elif config.bootstrap_method == BootstrapMethod.RETURN:
            return ReturnBootstrap()
        elif config.bootstrap_method == BootstrapMethod.BLOCK:
            return BlockBootstrap(block_size=config.block_size)
        else:
            raise ValueError(f"Unsupported bootstrap method: {config.bootstrap_method}")

    def simulate(
        self,
        result: BacktestResult,
        config_override: Optional[MonteCarloConfig] = None,
    ) -> List[SimulationResult]:
        """Execute Monte Carlo simulation across N iterations.

        Args:
            result: Completed BacktestResult object.
            config_override: Optional config override for run.

        Returns:
            List of SimulationResult objects for each path.
        """
        cfg = config_override or self.config
        # Always resolve strategy from cfg if override provided or not pre-supplied
        strategy = (
            self._select_bootstrap_strategy(cfg)
            if config_override or not self.bootstrap_strategy
            else self.bootstrap_strategy
        )

        initial_capital = result.config.initial_capital if result.config else 100000.0
        if initial_capital <= 0.0:
            initial_capital = 100000.0

        # Determinism flag handling
        if cfg.deterministic:
            seed = cfg.random_seed if cfg.random_seed is not None else 42
            rng = np.random.default_rng(seed)
        else:
            rng = np.random.default_rng(cfg.random_seed)

        # Extract data series depending on strategy
        data = self._extract_data(result, cfg.bootstrap_method, initial_capital)

        num_paths = cfg.iterations
        if num_paths <= 0:
            raise ValueError(f"iterations must be > 0, got {num_paths}")

        # Handle empty data case
        if len(data) == 0:
            return self._build_empty_results(num_paths, initial_capital)

        # Resample returns matrix (num_paths, path_length)
        resampled_returns = strategy.resample(
            data=data,
            num_paths=num_paths,
            path_length=len(data),
            rng=rng,
        )

        # Compute equity paths matrix: (num_paths, path_length + 1)
        equity_paths = self._compute_equity_paths(resampled_returns, initial_capital)

        # Calculate annualization factor for CAGR
        years = self._calculate_years(result)

        # Vectorized metrics computation
        simulations = self._vectorized_metrics(
            equity_paths=equity_paths,
            resampled_returns=resampled_returns,
            initial_capital=initial_capital,
            years=years,
            ruin_threshold_pct=cfg.ruin_threshold_pct,
        )

        return simulations

    def _extract_data(
        self,
        result: BacktestResult,
        method: BootstrapMethod,
        initial_capital: float,
    ) -> np.ndarray:
        """Extract resamplable series from BacktestResult."""
        if method == BootstrapMethod.TRADE:
            if result.trades:
                trade_returns = []
                for t in result.trades:
                    pnl = t.realized_pnl
                    pos_val = t.entry_price * t.quantity if (t.entry_price > 0 and t.quantity > 0) else initial_capital
                    ret = pnl / pos_val if pos_val > 0 else 0.0
                    trade_returns.append(ret)
                return np.array(trade_returns, dtype=np.float64)
            # Fallback to returns_series if no trades exist
            if result.returns_series:
                return np.array(result.returns_series, dtype=np.float64)
            return np.array([], dtype=np.float64)

        # RETURN or BLOCK method
        if result.returns_series and len(result.returns_series) > 0:
            return np.array(result.returns_series, dtype=np.float64)

        if result.equity_curve and len(result.equity_curve) > 1:
            eq = np.array(result.equity_curve, dtype=np.float64)
            prev = eq[:-1]
            curr = eq[1:]
            ret = np.where(prev > 0, (curr - prev) / prev, 0.0)
            return ret

        if result.equity_snapshots and len(result.equity_snapshots) > 1:
            eq = np.array([s.equity for s in result.equity_snapshots], dtype=np.float64)
            prev = eq[:-1]
            curr = eq[1:]
            ret = np.where(prev > 0, (curr - prev) / prev, 0.0)
            return ret

        return np.array([], dtype=np.float64)

    def _compute_equity_paths(
        self,
        resampled_returns: np.ndarray,
        initial_capital: float,
    ) -> np.ndarray:
        """Compute compounding equity paths matrix of shape (num_paths, T + 1)."""
        num_paths, T = resampled_returns.shape
        clipped_returns = np.maximum(resampled_returns, -0.999999)
        compounded = np.cumprod(1.0 + clipped_returns, axis=1)

        equity_paths = np.empty((num_paths, T + 1), dtype=np.float64)
        equity_paths[:, 0] = initial_capital
        equity_paths[:, 1:] = initial_capital * compounded

        equity_paths = np.maximum(equity_paths, 0.0)
        return equity_paths

    def _calculate_years(self, result: BacktestResult) -> float:
        """Calculate total duration of backtest in years for CAGR calculation."""
        if result.config and result.config.start_date and result.config.end_date:
            duration_days = (result.config.end_date - result.config.start_date).total_seconds() / 86400.0
            if duration_days > 0:
                return duration_days / 365.25
        return 1.0

    def _vectorized_metrics(
        self,
        equity_paths: np.ndarray,
        resampled_returns: np.ndarray,
        initial_capital: float,
        years: float,
        ruin_threshold_pct: float,
    ) -> List[SimulationResult]:
        """Compute SimulationResult objects across all paths using vectorized operations."""
        num_paths, path_len_plus_1 = equity_paths.shape

        ending_equity = equity_paths[:, -1]
        total_returns = (ending_equity - initial_capital) / initial_capital

        peaks = np.maximum.accumulate(equity_paths, axis=1)
        peaks = np.maximum(peaks, 1e-12)
        drawdowns = (peaks - equity_paths) / peaks
        max_drawdowns = np.max(drawdowns, axis=1)

        if years > 0:
            cagr = np.where(
                ending_equity > 0,
                (ending_equity / initial_capital) ** (1.0 / years) - 1.0,
                -1.0,
            )
        else:
            cagr = total_returns

        mean_ret = np.mean(resampled_returns, axis=1)
        std_ret = np.std(resampled_returns, axis=1, ddof=1)
        sharpe = np.where(std_ret > 1e-12, (mean_ret / std_ret) * np.sqrt(252), 0.0)

        ruin = (max_drawdowns >= ruin_threshold_pct) | (ending_equity <= 0.0)

        results = []
        for i in range(num_paths):
            results.append(
                SimulationResult(
                    iteration=i,
                    ending_equity=float(ending_equity[i]),
                    max_drawdown=float(max_drawdowns[i]),
                    total_return=float(total_returns[i]),
                    cagr=float(cagr[i]),
                    sharpe=float(sharpe[i]),
                    ruin=bool(ruin[i]),
                )
            )
        return results

    def _build_empty_results(
        self,
        num_paths: int,
        initial_capital: float,
    ) -> List[SimulationResult]:
        """Return static results when backtest dataset is empty."""
        return [
            SimulationResult(
                iteration=i,
                ending_equity=initial_capital,
                max_drawdown=0.0,
                total_return=0.0,
                cagr=0.0,
                sharpe=0.0,
                ruin=False,
            )
            for i in range(num_paths)
        ]
