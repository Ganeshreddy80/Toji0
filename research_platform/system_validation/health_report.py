"""Health cards compiler.
"""

from __future__ import annotations

import logging
from typing import List
from research_platform.system_validation.models import SubsystemHealth

logger = logging.getLogger(__name__)


class HealthReportCompiler:
    """Aggregates and formats detailed subsystem validation health check status summaries."""

    def compile_markdown(self, cards: List[SubsystemHealth]) -> str:
        lines = ["# TOJI System Subsystems Health Report\n"]
        for card in cards:
            lines.append(f"## {card.name}")
            lines.append(f"- **Score:** {card.score:.1f}/100")
            lines.append(f"- **Checks Run:** {len(card.checks)}")
            lines.append(f"- **Duration:** {card.duration_seconds:.4f} sec")
            if card.failures:
                lines.append("- **Failures:**")
                for f in card.failures:
                    lines.append(f"  - `[FAIL]` {f.name}: {f.message}")
            else:
                lines.append("- **Status:** `[HEALTHY]` All checks passed.")
            lines.append("")
        return "\n".join(lines)
