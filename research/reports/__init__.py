"""Quantitative reports generator for comparing and summarizing research components."""

from __future__ import annotations

from typing import Any


class ReportGenerator:
    """Helper to generate structured research summaries, comparisons, and optimization reports."""

    @staticmethod
    def generate_summary(experiments_count: int, knowledge_entries: list[Any]) -> dict[str, Any]:
        """Aggregate total research overview metrics."""
        learnings_count = sum(1 for e in knowledge_entries if not e.is_lessons_learned)
        lessons_count = sum(1 for e in knowledge_entries if e.is_lessons_learned)

        return {
            "report_type": "Research Summary",
            "metrics": {
                "total_experiments": experiments_count,
                "alpha_learnings": learnings_count,
                "risk_lessons": lessons_count,
            },
        }

    @staticmethod
    def compare_experiments(runs: list[Any]) -> dict[str, Any]:
        """Compare performance metrics across multiple experiment runs."""
        comparison_matrix = {}
        for run in runs:
            comparison_matrix[run.run_id] = {
                "experiment_id": run.experiment_id,
                "status": run.status.value,
                "metrics": run.metrics,
            }
        return {
            "report_type": "Experiment Comparison",
            "comparison": comparison_matrix,
        }

    @staticmethod
    def compare_strategies(strategies: list[Any]) -> dict[str, Any]:
        """Collate strategy rules and metadata configurations."""
        comparison_matrix = {}
        for strat in strategies:
            comparison_matrix[strat.strategy_id] = {
                "name": strat.name,
                "version": strat.version,
                "rules_count": len(strat.entry_rules) + len(strat.exit_rules),
                "metadata": strat.metadata,
            }
        return {
            "report_type": "Strategy Comparison",
            "comparison": comparison_matrix,
        }

    @staticmethod
    def generate_optimization_report(
        parameters_sweep: list[dict[str, Any]], metrics_key: str = "sharpe"
    ) -> dict[str, Any]:
        """Evaluate hyperparameter combinations to find the optimal settings."""
        if not parameters_sweep:
            return {"report_type": "Optimization", "best_parameters": {}, "best_metric": 0.0}

        sorted_sweep = sorted(parameters_sweep, key=lambda x: x.get(metrics_key, 0.0), reverse=True)
        best_run = sorted_sweep[0]
        return {
            "report_type": "Optimization Report",
            "best_parameters": best_run.get("parameters", {}),
            "best_metric": best_run.get(metrics_key, 0.0),
            "total_sweeps": len(parameters_sweep),
        }

    @staticmethod
    def generate_validation_report(results: list[Any]) -> dict[str, Any]:
        """Aggregate multiple validation checks outcomes."""
        passed_count = sum(1 for r in results if r.passed)
        total = len(results)

        return {
            "report_type": "Validation Report",
            "passed_checks": passed_count,
            "total_checks": total,
            "passed_ratio": passed_count / total if total > 0 else 0.0,
            "results": [r.model_dump() for r in results],
        }
