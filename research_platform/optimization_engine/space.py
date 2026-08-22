"""Parameter Space sampler (Grid, Random, and Latin Hypercube).
"""

from __future__ import annotations

import itertools
import random
from typing import Any, List

from research_platform.optimization_engine.models import (
    ParameterCombination,
    ParameterSpace
)


class ParameterSpaceSampler:
    """Generates parameter combinations from defined spaces using various sampling techniques."""

    @staticmethod
    def sample_grid(space: ParameterSpace, steps: int = 5) -> List[ParameterCombination]:
        """Generate grid combinations spanning discrete parameter bounds."""
        param_grids = []
        param_names = []

        for p in space.parameters:
            param_names.append(p.name)
            if p.type == "categorical" and p.categorical_values:
                param_grids.append(p.categorical_values)
            elif p.bounds and len(p.bounds) == 2:
                lower, upper = p.bounds
                if p.type == "int":
                    # Discrete integer range
                    pts = list(range(int(lower), int(upper) + 1, max(1, int((upper - lower) / steps))))
                    param_grids.append(list(set(pts)))
                else:
                    # Floating point grid
                    pts = [float(lower + i * (upper - lower) / steps) for i in range(steps + 1)]
                    param_grids.append(pts)
            else:
                param_grids.append([None])

        # Cartesian product combinations
        combos = []
        for combo in itertools.product(*param_grids):
            combos.append(
                ParameterCombination(
                    values={name: val for name, val in zip(param_names, combo)}
                )
            )
        return combos

    @staticmethod
    def sample_random(space: ParameterSpace, num_samples: int = 20) -> List[ParameterCombination]:
        """Generate randomized configurations within parameter bounds."""
        combos = []
        for _ in range(num_samples):
            values = {}
            for p in space.parameters:
                if p.type == "categorical" and p.categorical_values:
                    values[p.name] = random.choice(p.categorical_values)
                elif p.bounds and len(p.bounds) == 2:
                    lower, upper = p.bounds
                    if p.type == "int":
                        values[p.name] = random.randint(int(lower), int(upper))
                    else:
                        values[p.name] = random.uniform(lower, upper)
            combos.append(ParameterCombination(values=values))
        return combos

    @staticmethod
    def sample_lhs(space: ParameterSpace, num_samples: int = 20) -> List[ParameterCombination]:
        """Latin Hypercube Sampling (LHS) for uniform coverage of parameter dimensions."""
        combos = []
        param_points = {}

        # Generate partitioned bins for each parameter
        for p in space.parameters:
            if p.type == "categorical" and p.categorical_values:
                # Repeat categorical values to fit sample count, then shuffle
                vals = [random.choice(p.categorical_values) for _ in range(num_samples)]
                random.shuffle(vals)
                param_points[p.name] = vals
            elif p.bounds and len(p.bounds) == 2:
                lower, upper = p.bounds
                # Create bins
                bins = np.linspace(lower, upper, num_samples + 1)
                pts = []
                for i in range(num_samples):
                    # Pick random value inside each bin
                    val = random.uniform(bins[i], bins[i + 1])
                    if p.type == "int":
                        val = int(round(val))
                    pts.append(val)
                random.shuffle(pts)
                param_points[p.name] = pts

        for i in range(num_samples):
            combos.append(
                ParameterCombination(
                    values={name: param_points[name][i] for name in param_points}
                )
            )
        return combos


import numpy as np
