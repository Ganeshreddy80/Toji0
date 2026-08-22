"""Linear regression utilities for the Price Action Engine."""

from __future__ import annotations

from typing import Sequence
from price_action.core.models import PatternPoint


def fit_line(points: Sequence[PatternPoint]) -> tuple[float, float, float]:
    """Fit a linear regression line to a sequence of points.

    Returns:
        tuple: (slope, intercept, r_squared)
    """
    n = len(points)
    if n < 2:
        return 0.0, 0.0, 1.0

    x = [float(p.index) for p in points]
    y = [p.price for p in points]

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    den = sum((x[i] - mean_x) ** 2 for i in range(n))

    if den == 0.0:
        return 0.0, 0.0, 1.0

    slope = num / den
    intercept = mean_y - slope * mean_x

    # Compute R^2
    y_pred = [slope * xi + intercept for xi in x]
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))

    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0.0 else 1.0

    return slope, intercept, r_squared


def fit_quadratic(points: Sequence[PatternPoint]) -> tuple[float, float, float, float]:
    """Fit a quadratic regression curve (y = a*x^2 + b*x + c) to a sequence of points.

    Returns:
        tuple: (a, b, c, r_squared)
    """
    n = len(points)
    if n < 3:
        return 0.0, 0.0, 0.0, 1.0

    x = [float(p.index) for p in points]
    y = [p.price for p in points]

    sum_x = sum(x)
    sum_y = sum(y)
    sum_x2 = sum(xi ** 2 for xi in x)
    sum_x3 = sum(xi ** 3 for xi in x)
    sum_x4 = sum(xi ** 4 for xi in x)
    sum_xy = sum(x[i] * y[i] for i in range(n))
    sum_x2y = sum((x[i] ** 2) * y[i] for i in range(n))

    # Construct the 3x3 matrix and vectors
    # [ sum_x4, sum_x3, sum_x2 ] [a]   [ sum_x2y ]
    # [ sum_x3, sum_x2, sum_x  ] [b] = [ sum_xy  ]
    # [ sum_x2, sum_x,  n      ] [c]   [ sum_y   ]

    m = [
        [sum_x4, sum_x3, sum_x2],
        [sum_x3, sum_x2, sum_x],
        [sum_x2, sum_x, float(n)],
    ]

    def det3(matrix: list[list[float]]) -> float:
        return (
            matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
            - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
            + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
        )

    d = det3(m)
    if abs(d) < 1e-9:
        return 0.0, 0.0, sum_y / n, 1.0

    m_a = [
        [sum_x2y, sum_x3, sum_x2],
        [sum_xy, sum_x2, sum_x],
        [sum_y, sum_x, float(n)],
    ]
    m_b = [
        [sum_x4, sum_x2y, sum_x2],
        [sum_x3, sum_xy, sum_x],
        [sum_x2, sum_y, float(n)],
    ]
    m_c = [
        [sum_x4, sum_x3, sum_x2y],
        [sum_x3, sum_x2, sum_xy],
        [sum_x2, sum_x, sum_y],
    ]

    a = det3(m_a) / d
    b = det3(m_b) / d
    c = det3(m_c) / d

    mean_y = sum_y / n
    y_pred = [a * xi**2 + b * xi + c for xi in x]
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))

    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0.0 else 1.0

    return a, b, c, r_squared

