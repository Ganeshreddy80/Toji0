"""Optimization search algorithms (Grid, Random, Genetic, and Bayesian Proxy).
"""

from __future__ import annotations

import copy
import random
from typing import List

from research_platform.optimization_engine.interfaces import IOptimizer
from research_platform.optimization_engine.models import (
    OptimizationConfiguration,
    ParameterCombination
)
from research_platform.optimization_engine.space import ParameterSpaceSampler


class GridSearchOptimizer(IOptimizer):
    """Exhaustive grid sweep search algorithm."""

    def generate_combinations(self, config: OptimizationConfiguration) -> List[ParameterCombination]:
        # Divide steps evenly based on total requested trials
        steps = int(round(config.num_trials ** (1.0 / max(len(config.space.parameters), 1))))
        steps = max(steps, 2)
        return ParameterSpaceSampler.sample_grid(config.space, steps=steps)[:config.num_trials]


class RandomSearchOptimizer(IOptimizer):
    """Randomized parameter search algorithm."""

    def generate_combinations(self, config: OptimizationConfiguration) -> List[ParameterCombination]:
        return ParameterSpaceSampler.sample_random(config.space, num_samples=config.num_trials)


class GeneticAlgorithmOptimizer(IOptimizer):
    """Evolutionary parameter search algorithm using crossover mutations."""

    def generate_combinations(self, config: OptimizationConfiguration) -> List[ParameterCombination]:
        # Generate initial population randomly
        pop = ParameterSpaceSampler.sample_random(config.space, num_samples=config.num_trials)
        return pop

    @classmethod
    def evolve_population(
        cls,
        parents: List[ParameterCombination],
        config: OptimizationConfiguration,
        mutation_rate: float = 0.2
    ) -> List[ParameterCombination]:
        """Produce next generation using uniform crossover and bounds mutation."""
        next_gen = []
        n = len(parents)
        if n < 2:
            return parents

        # Elitism: retain top 10%
        elite_count = max(1, n // 10)
        next_gen.extend(parents[:elite_count])

        while len(next_gen) < n:
            # Selection: pick two random parents
            p1 = random.choice(parents)
            p2 = random.choice(parents)

            # Crossover: crossover values
            child_values = {}
            for param in config.space.parameters:
                name = param.name
                child_values[name] = p1.values[name] if random.random() < 0.5 else p2.values[name]

                # Mutation
                if random.random() < mutation_rate:
                    if param.type == "categorical" and param.categorical_values:
                        child_values[name] = random.choice(param.categorical_values)
                    elif param.bounds and len(param.bounds) == 2:
                        lower, upper = param.bounds
                        if param.type == "int":
                            child_values[name] = random.randint(int(lower), int(upper))
                        else:
                            child_values[name] = random.uniform(lower, upper)

            next_gen.append(ParameterCombination(values=child_values))

        return next_gen


class BayesianOptimizerProxy(IOptimizer):
    """Surrogate search proxy simulating Bayesian parameter optimizations."""

    def generate_combinations(self, config: OptimizationConfiguration) -> List[ParameterCombination]:
        # LHS sampling serves as a robust initial design/proxy for Bayesian iterations
        return ParameterSpaceSampler.sample_lhs(config.space, num_samples=config.num_trials)
