"""Scanner for evaluating registered assets and producing ranked opportunities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from intelligence.models import Opportunity, RiskGrade
from intelligence.universe.manager import UniverseManager
from intelligence.market_pulse.pulse import MarketPulseGenerator
from intelligence.regime.engine import RegimeEngine
from intelligence.timing.engine import TimingEngine
from intelligence.asset_health.calculator import AssetHealthCalculator
from intelligence.eligibility.evaluator import StrategyEligibilityEvaluator, StrategyEligibilityConstraints
from intelligence.opportunities.engine import OpportunityEngine


class Scanner:
    """Orchestrates asset scanning, filtering, and opportunity ranking across multiple engines."""

    def __init__(
        self,
        universe_manager: UniverseManager,
        pulse_generator: MarketPulseGenerator | None = None,
        regime_engine: RegimeEngine | None = None,
        timing_engine: TimingEngine | None = None,
        health_calculator: AssetHealthCalculator | None = None,
        eligibility_evaluator: StrategyEligibilityEvaluator | None = None,
        opportunity_engine: OpportunityEngine | None = None,
    ) -> None:
        """Initialize the Scanner.

        Args:
            universe_manager: Injected UniverseManager.
            pulse_generator: Optional injected MarketPulseGenerator.
            regime_engine: Optional injected RegimeEngine.
            timing_engine: Optional injected TimingEngine.
            health_calculator: Optional injected AssetHealthCalculator.
            eligibility_evaluator: Optional injected StrategyEligibilityEvaluator.
            opportunity_engine: Optional injected OpportunityEngine.
        """
        self.universe_manager = universe_manager
        self.pulse_generator = pulse_generator or MarketPulseGenerator()
        self.regime_engine = regime_engine or RegimeEngine()
        self.timing_engine = timing_engine or TimingEngine()
        self.health_calculator = health_calculator or AssetHealthCalculator()
        self.eligibility_evaluator = eligibility_evaluator or StrategyEligibilityEvaluator()
        self.opportunity_engine = opportunity_engine or OpportunityEngine()

    def _determine_risk_grade(self, health_score: float) -> RiskGrade:
        """Map a health score to a RiskGrade enum."""
        if health_score >= 0.8:
            return RiskGrade.A
        elif health_score >= 0.6:
            return RiskGrade.B
        elif health_score >= 0.4:
            return RiskGrade.C
        elif health_score >= 0.2:
            return RiskGrade.D
        else:
            return RiskGrade.F

    def scan(
        self,
        market_data: dict[str, dict[str, list[float]]],
        strategy_constraints: list[StrategyEligibilityConstraints],
        strategy_stats: dict[str, dict[str, float]],  # strategy_id -> {'win_rate': float, 'sharpe': float}
        event_times: list[datetime] | None = None,
        filters: dict[str, Any] | None = None,
        evaluation_time: datetime | None = None,
    ) -> list[Opportunity]:
        """Scan registered assets, evaluate eligibility constraints, and produce ranked opportunities.

        Args:
            market_data: Dictionary of historical market data series:
                         symbol -> {
                             'prices': list[float],
                             'volumes': list[float],
                             'spreads': list[float],
                             'funding_rates': list[float] (optional),
                             'open_interests': list[float] (optional)
                         }
            strategy_constraints: List of StrategyEligibilityConstraints definitions.
            strategy_stats: Stats dictionary with performance statistics for scoring.
            event_times: Global calendar macro event datetimes.
            filters: Universe group filter criteria (passed to UniverseManager.filter_assets).
            evaluation_time: Reference time for timing evaluations. Defaults to UTC now.

        Returns:
            List of scored and ranked Opportunity objects.
        """
        if evaluation_time is None:
            evaluation_time = datetime.now(timezone.utc)

        # 1. Determine assets to scan
        if filters:
            assets = self.universe_manager.filter_assets(filters)
        else:
            assets = self.universe_manager.get_all_assets()

        opportunities: list[Opportunity] = []

        # 2. Iterate and evaluate assets
        for asset in assets:
            sym = asset.symbol
            data = market_data.get(sym)
            if not data or "prices" not in data or "volumes" not in data:
                continue

            prices = data["prices"]
            volumes = data["volumes"]
            spreads = data.get("spreads", [0.0005] * len(prices))
            funding = data.get("funding_rates")
            oi = data.get("open_interests")

            # A. Detect regime
            regime = self.regime_engine.detect_regime(prices, volumes)

            # B. Generate market pulse
            pulse = self.pulse_generator.generate_pulse(
                prices=prices,
                volumes=volumes,
                fear_index=50.0,
                confidence=0.8,
            )

            # C. Evaluate health & assign RiskGrade
            health_report = self.health_calculator.evaluate_health(
                prices=prices,
                volumes=volumes,
                spreads=spreads,
                funding_rates=funding,
                open_interests=oi,
            )
            risk_grade = self._determine_risk_grade(health_report["health_score"])

            # D. Evaluate strategy eligibility
            for constraints in strategy_constraints:
                is_eligible, _ = self.eligibility_evaluator.evaluate(
                    constraints=constraints,
                    pulse=pulse,
                    current_regime=regime,
                )

                if not is_eligible:
                    continue

                # E. Calculate timing signals
                # Assume a recent signal time or equal to evaluation_time
                signal_time = evaluation_time
                decay = self.timing_engine.calculate_signal_decay(signal_time, evaluation_time)
                is_crypto = asset.asset_class.value == "crypto"
                window = self.timing_engine.determine_execution_window(
                    signal_time=signal_time,
                    evaluation_time=evaluation_time,
                    event_times=event_times,
                    is_crypto=is_crypto,
                )

                # F. Compute opportunity score
                stats = strategy_stats.get(constraints.strategy_id, {"win_rate": 0.5, "sharpe": 1.0})
                # Check for rules/beliefs count from metadata or custom attributes if any
                asset_info = self.universe_manager.get_asset_info(sym)
                evidence_count = 0
                if asset_info and "evidence_count" in asset_info.custom_attributes:
                    evidence_count = asset_info.custom_attributes["evidence_count"]

                opportunity = self.opportunity_engine.evaluate_opportunity(
                    symbol=sym,
                    strategy_id=constraints.strategy_id,
                    regime=regime,
                    timing_window=window,
                    win_rate=stats.get("win_rate", 0.5),
                    sharpe=stats.get("sharpe", 1.0),
                    timing_decay=decay,
                    risk_grade=risk_grade,
                    evidence_count=evidence_count,
                )
                opportunities.append(opportunity)

        # 3. Sort opportunities by score descending
        return self.opportunity_engine.rank_opportunities(opportunities)
