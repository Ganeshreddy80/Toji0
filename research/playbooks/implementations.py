"""Concrete quant research playbooks implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from research.playbooks.interfaces import IPlaybook

if TYPE_CHECKING:
    from research.experiments.manager import ExperimentManager
    from research.experiments.models import ResearchExperiment


class BasePlaybook(IPlaybook):
    """Utility base class for playbooks, providing generic execution logging."""

    def execute(
        self,
        manager: ExperimentManager,
        dataset_ref: str,
        asset_universe: list[str],
        custom_inputs: dict[str, Any] | None = None,
    ) -> ResearchExperiment:
        # Register the experiment with the manager
        tags = [self.name.lower().replace(" ", "_"), "playbook_derived"]
        return manager.create_experiment(
            name=f"{self.name} Run",
            description=f"Generated research experiment using {self.name} template.",
            dataset_ref=dataset_ref,
            asset_universe=asset_universe,
            tags=tags,
            feature_refs=self.required_features,
            market_regime=custom_inputs.get("market_regime") if custom_inputs else None,
        )


class MomentumResearchPlaybook(BasePlaybook):
    """Workflow template for researching momentum factors and trend-following strategies."""

    @property
    def name(self) -> str:
        return "Momentum Research"

    @property
    def description(self) -> str:
        return "Analyze rolling trend indicators and relative strength momentum signals."

    @property
    def required_datasets(self) -> list[str]:
        return ["ohlcv_history"]

    @property
    def required_features(self) -> list[str]:
        return ["EMA", "RSI", "MACD", "Momentum"]

    @property
    def steps(self) -> list[str]:
        return [
            "1. Extract trend and strength features.",
            "2. Align and normalise metrics across assets.",
            "3. Generate trading rules (crossovers, RSI thresholds).",
            "4. Validate via Walk-Forward analysis.",
        ]

    @property
    def validation_criteria(self) -> dict[str, Any]:
        return {"min_sharpe": 1.5, "max_drawdown": 0.15, "min_win_rate": 0.52}


class MeanReversionResearchPlaybook(BasePlaybook):
    """Workflow template for researching statistical arbitrage and mean-reversion edges."""

    @property
    def name(self) -> str:
        return "Mean Reversion Research"

    @property
    def description(self) -> str:
        return "Analyze cointegrated asset pairs or boundary volatility bands."

    @property
    def required_datasets(self) -> list[str]:
        return ["ohlcv_history"]

    @property
    def required_features(self) -> list[str]:
        return ["RSI", "ATR", "Volatility"]

    @property
    def steps(self) -> list[str]:
        return [
            "1. Run cointegration or volatility band checks.",
            "2. Generate entry/exit bands (z-score boundary).",
            "3. Apply stop-losses based on Volatility/ATR.",
            "4. Run Out-of-Sample backtests.",
        ]

    @property
    def validation_criteria(self) -> dict[str, Any]:
        return {"min_sharpe": 1.8, "max_drawdown": 0.12, "min_profit_factor": 1.4}


class BreakoutResearchPlaybook(BasePlaybook):
    """Workflow template for researching breakout price channels and volume spikes."""

    @property
    def name(self) -> str:
        return "Breakout Research"

    @property
    def description(self) -> str:
        return "Analyze support/resistance price channels and volume profiles."

    @property
    def required_datasets(self) -> list[str]:
        return ["ohlcv_history", "orderbook_depth"]

    @property
    def required_features(self) -> list[str]:
        return ["ATR", "VWAP", "VolumeProfile", "Liquidity"]

    @property
    def steps(self) -> list[str]:
        return [
            "1. Compute price channels and volume clusters.",
            "2. Detect volume spikes breaking historical limits.",
            "3. Verify order book depth and spreads.",
            "4. Backtest returns with slippage adjustments.",
        ]

    @property
    def validation_criteria(self) -> dict[str, Any]:
        return {"min_sharpe": 1.2, "max_drawdown": 0.20}


class MacroResearchPlaybook(BasePlaybook):
    """Workflow template for researching macroeconomic indicators and regime shifts."""

    @property
    def name(self) -> str:
        return "Macro Research"

    @property
    def description(self) -> str:
        return "Analyze macroeconomic calendar publications and global rate regimes."

    @property
    def required_datasets(self) -> list[str]:
        return ["macro_calendar"]

    @property
    def required_features(self) -> list[str]:
        return ["Funding", "Volatility"]

    @property
    def steps(self) -> list[str]:
        return [
            "1. Load macroeconomic announcements times.",
            "2. Map market volatility before and after releases.",
            "3. Generate conditional regime allocation rules.",
        ]

    @property
    def validation_criteria(self) -> dict[str, Any]:
        return {"min_win_rate": 0.55}


class FactorResearchPlaybook(BasePlaybook):
    """Workflow template for researching arbitrage factors and anomalies."""

    @property
    def name(self) -> str:
        return "Factor Research"

    @property
    def description(self) -> str:
        return "Analyze multiple quantitative indicators using cross-sectional ranking."

    @property
    def required_datasets(self) -> list[str]:
        return ["ohlcv_history"]

    @property
    def required_features(self) -> list[str]:
        return ["EMA", "RSI", "ATR", "VWAP"]

    @property
    def steps(self) -> list[str]:
        return [
            "1. Calculate cross-sectional factor ranks.",
            "2. Compute rolling information coefficients (IC).",
            "3. Evaluate long-short quant portfolio returns.",
        ]

    @property
    def validation_criteria(self) -> dict[str, Any]:
        return {"min_information_coefficient": 0.05, "min_t_stat": 2.0}
