"""Session scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_session(
    market_state: MarketState,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate session alignment and volatility impact [0.0, 100.0]."""
    supporting = []
    conflicting = []

    session_state = market_state.session
    if session_state is None:
        return 75.0, [], []

    score = 75.0
    active_sessions = getattr(session_state, "active_sessions", []) or []
    
    # Active high-volume sessions (London/NY) increase confirmation
    high_volume_active = any(s in ["London", "New York"] for s in active_sessions)
    if high_volume_active:
        supporting.append(
            SupportingFactor(
                name="High Volume Session Active",
                category="SESSION",
                value=85.0,
                description="Trade setup during liquid London/New York hours.",
            )
        )
        score = 90.0

    return score, supporting, conflicting
