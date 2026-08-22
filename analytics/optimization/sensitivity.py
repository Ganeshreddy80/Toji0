"""Sensitivity analysis of strategy parameters to evaluate robustness and parameter stability."""

from __future__ import annotations

from typing import Any, Callable


class SensitivityAnalyzer:
    """Analyzes how local changes in parameter values impact strategy metric outcomes."""

    @staticmethod
    def analyze_sensitivity(
        runner_factory: Callable[[dict[str, Any]], Any],
        base_parameters: dict[str, Any],
        perturbations: dict[str, list[Any]],
        metric_evaluator: Callable[[Any], float],
    ) -> dict[str, dict[str, float]]:
        """Evaluate performance changes when individual parameter values are perturbed.
        
        Evaluates one parameter at a time while keeping all other parameters at base values.
        
        Args:
            runner_factory: callable mapping parameters dict to runner object
            base_parameters: dict of anchor strategy parameters
            perturbations: dict of parameter name -> list of values to test
            metric_evaluator: callable mapping runner to target float metric
            
        Returns:
            dict of parameter name -> dict of {value: metric_value}
        """
        sensitivity_report: dict[str, dict[str, float]] = {}
        
        # Calculate metric at baseline first
        base_runner = runner_factory(base_parameters)
        base_metric = metric_evaluator(base_runner)
        
        for param_name, values in perturbations.items():
            if param_name not in base_parameters:
                continue
                
            param_results: dict[str, float] = {}
            # Include baseline
            param_results[str(base_parameters[param_name])] = base_metric
            
            for val in values:
                if val == base_parameters[param_name]:
                    continue
                # Clone and update parameter value
                test_params = dict(base_parameters)
                test_params[param_name] = val
                
                try:
                    runner = runner_factory(test_params)
                    m_val = metric_evaluator(runner)
                    param_results[str(val)] = m_val
                except Exception:
                    # Capture execution crashes if parameter is invalid
                    param_results[str(val)] = float("-inf")
                    
            sensitivity_report[param_name] = param_results
            
        return sensitivity_report
