"""Feature Freshness Engine implementation.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict

from research_platform.feature_platform.interfaces import IFeatureFreshnessEngine
from research_platform.feature_platform.models import FeatureFreshnessMetrics


class FeatureFreshnessEngine(IFeatureFreshnessEngine):
    """Monitors feature calculated age metrics and applies exponential decay functions."""

    def __init__(self) -> None:
        pass

    def calculate_freshness(
        self,
        name: str,
        last_update: datetime,
        half_life_seconds: float = 3600.0,
        recalc_freq: str = "1m",
        expiration_sec: int = 86400
    ) -> FeatureFreshnessMetrics:
        """Compute freshness and age based on exponential decay half-life.

        Score decays from 1.0 (fresh) to 0.0 (expired) over time.
        """
        now = datetime.now(timezone.utc)
        # Ensure timezone compatibility
        last_up = last_update
        if last_up.tzinfo is None:
            last_up = last_up.replace(tzinfo=timezone.utc)

        age_seconds = max((now - last_up).total_seconds(), 0.0)

        # decay_rate = ln(2) / half_life
        decay_rate = math.log(2.0) / (half_life_seconds + 1e-10)
        freshness_score = math.exp(-decay_rate * age_seconds)

        expected_ref = datetime.fromtimestamp(
            last_up.timestamp() + expiration_sec,
            tz=timezone.utc
        )

        return FeatureFreshnessMetrics(
            feature_name=name,
            half_life_seconds=half_life_seconds,
            freshness_score=freshness_score,
            age_seconds=age_seconds,
            decay_rate=decay_rate,
            recalculation_frequency=recalc_freq,
            expiration_policy=expiration_sec,
            last_successful_refresh=last_up,
            expected_refresh=expected_ref
        )
