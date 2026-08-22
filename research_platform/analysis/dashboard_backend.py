"""Research dashboard backend models generator for the Research Platform (Sprint 6)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from research_platform.core.interfaces import IExperimentRepository, IResearchDashboardBackend
from research_platform.core.models import ExperimentResult, ResearchDashboardView


class ResearchDashboardBackend(IResearchDashboardBackend):
    """Aggregates historical and active experiment metrics into dashboard visualization state."""

    def __init__(self, repository: IExperimentRepository) -> None:
        self._repository = repository

    def build_dashboard_view(self, experiment_ids: Optional[List[str]] = None) -> ResearchDashboardView:
        """Build visualization state snapshot for the research dashboard."""
        all_experiments = self._repository.list_experiments()

        if experiment_ids:
            target_set = set(experiment_ids)
            experiments = [e for e in all_experiments if e.experiment_id in target_set]
        else:
            experiments = all_experiments

        if not experiments:
            return ResearchDashboardView(
                experiment_count=0,
                top_experiments=[],
                metric_summaries={},
                heatmap_data={},
                equity_curves={},
                updated_at=datetime.now(timezone.utc),
            )

        # Sort experiments by Sharpe ratio descending
        sorted_experiments = sorted(experiments, key=lambda e: e.metrics.sharpe_ratio, reverse=True)
        top_experiments = sorted_experiments[:10]

        # Calculate metric summary averages
        total_sharpe = sum(e.metrics.sharpe_ratio for e in experiments)
        total_win_rate = sum(e.metrics.win_rate for e in experiments)
        total_drawdown = sum(e.metrics.max_drawdown for e in experiments)
        count = len(experiments)

        metric_summaries = {
            "avg_sharpe_ratio": round(total_sharpe / count, 4) if count > 0 else 0.0,
            "avg_win_rate": round(total_win_rate / count, 4) if count > 0 else 0.0,
            "avg_max_drawdown": round(total_drawdown / count, 4) if count > 0 else 0.0,
        }

        # Extract equity curves
        equity_curves: Dict[str, List[float]] = {}
        heatmap_points: List[Dict[str, float]] = []

        for e in top_experiments:
            if hasattr(e, "equity_curve") and getattr(e, "equity_curve"):
                equity_curves[e.experiment_id] = getattr(e, "equity_curve")
            if e.parameter_sweep and e.parameter_sweep.trials:
                for trial in e.parameter_sweep.trials:
                    params = trial.parameters
                    # Extract any numeric parameters for heatmap scatter
                    num_params = [v for v in params.values() if isinstance(v, (int, float))]
                    if len(num_params) >= 2:
                        heatmap_points.append({
                            "param_x": float(num_params[0]),
                            "param_y": float(num_params[1]),
                            "sharpe": trial.metrics.sharpe_ratio,
                        })

        heatmap_data = {"points": heatmap_points}

        return ResearchDashboardView(
            experiment_count=count,
            top_experiments=top_experiments,
            metric_summaries=metric_summaries,
            heatmap_data=heatmap_data,
            equity_curves=equity_curves,
            updated_at=datetime.now(timezone.utc),
        )
