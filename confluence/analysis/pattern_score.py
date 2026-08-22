"""Pattern scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from price_action.core.models import PatternState
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_pattern(
    market_state: MarketState,
    pattern_state: PatternState | None = None,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate pattern presence and alignment [0.0, 100.0]."""
    supporting = []
    conflicting = []

    if pattern_state is None:
        return 50.0, [], []

    active_matches = pattern_state.active_patterns
    candidates = pattern_state.candidate_patterns

    if not active_matches and not candidates:
        return 50.0, [], []

    score = 70.0

    # 1. Process active matches (confirmed patterns)
    if active_matches:
        for match in active_matches:
            match_dir = match.direction
            pattern_name = str(match.pattern_type)

            if pattern_direction is not None:
                if match_dir == pattern_direction:
                    supporting.append(
                        SupportingFactor(
                            name=f"Confirmed Pattern: {pattern_name}",
                            category="PATTERN",
                            value=95.0,
                            description=f"Confirmed {pattern_name} aligns with setup direction.",
                        )
                    )
                    score = max(score, 95.0)
                else:
                    conflicting.append(
                        ConflictingFactor(
                            name=f"Opposing Pattern: {pattern_name}",
                            category="PATTERN",
                            penalty=3.0,
                            description=f"Confirmed {pattern_name} opposes setup direction.",
                        )
                    )
                    score = min(score, 40.0)
            else:
                # No specific direction requested, positive since a pattern is confirmed
                supporting.append(
                    SupportingFactor(
                        name=f"Confirmed Pattern: {pattern_name}",
                        category="PATTERN",
                        value=90.0,
                        description=f"Confirmed {pattern_name} pattern present.",
                    )
                )
                score = max(score, 90.0)

    # 2. Process candidate patterns if no active match boosts the score to max
    if score < 90.0 and candidates:
        for cand in candidates:
            cand_dir = cand.direction
            pattern_name = str(cand.pattern_type)

            if pattern_direction is not None:
                if cand_dir == pattern_direction:
                    supporting.append(
                        SupportingFactor(
                            name=f"Candidate Pattern: {pattern_name}",
                            category="PATTERN",
                            value=80.0,
                            description=f"Candidate {pattern_name} aligns with setup direction.",
                        )
                    )
                    score = max(score, 80.0)
                else:
                    conflicting.append(
                        ConflictingFactor(
                            name=f"Opposing Candidate: {pattern_name}",
                            category="PATTERN",
                            penalty=1.5,
                            description=f"Candidate {pattern_name} opposes setup direction.",
                        )
                    )
                    score = min(score, 55.0)
            else:
                supporting.append(
                    SupportingFactor(
                        name=f"Candidate Pattern: {pattern_name}",
                        category="PATTERN",
                        value=75.0,
                        description=f"Candidate {pattern_name} pattern in formation.",
                    )
                )
                score = max(score, 75.0)

    return score, supporting, conflicting
