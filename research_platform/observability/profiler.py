"""Performance Profiler tracking resources load profiles.
"""

from __future__ import annotations

from research_platform.observability.models import PerformanceProfile


class PerformanceProfiler:
    """Collects CPU percentages and memory usages statistics."""

    def capture_profile(self) -> PerformanceProfile:
        """Estimate current CPU load and memory usage profile."""
        # Simple simulation values (no os dependency to keep it deterministic)
        return PerformanceProfile(
            cpu_load_pct=15.0,
            memory_used_mb=256.0
        )
