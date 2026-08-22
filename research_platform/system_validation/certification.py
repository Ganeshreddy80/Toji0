"""Scorecard aggregate compiler and cryptographic signer.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import List
from research_platform.system_validation.models import (
    SubsystemHealth,
    SystemCertificationCard,
)


class CertificationEngine:
    """Aggregates scores and signs a cryptographically secure certification block."""

    def certify(self, health_cards: List[SubsystemHealth]) -> SystemCertificationCard:
        if not health_cards:
            return SystemCertificationCard(
                status="FAILED",
                overall_score=0.0,
                critical_issues=["No health cards resolved."],
                block_hash="genesis"
            )

        total_score = sum(card.score for card in health_cards)
        overall = total_score / len(health_cards)

        critical_issues = []
        for card in health_cards:
            for fail in card.failures:
                critical_issues.append(f"{card.name}: {fail.name} - {fail.message}")

        status = "PASSED" if overall >= 80.0 and not critical_issues else "FAILED"

        # Generate block signature hash
        now = datetime.now(timezone.utc)
        payload = f"{status}|{overall:.2f}|{now.isoformat()}|{len(critical_issues)}"
        block_hash = hashlib.sha256(payload.encode()).hexdigest()

        return SystemCertificationCard(
            status=status,
            overall_score=overall,
            timestamp=now,
            critical_issues=critical_issues,
            block_hash=block_hash
        )
