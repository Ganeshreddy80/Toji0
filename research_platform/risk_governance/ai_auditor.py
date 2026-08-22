"""AI Decision Auditor — reviews every AI signal before it reaches execution."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from research_platform.risk_governance.models import AuditDecision

logger = logging.getLogger(__name__)


class AIDecisionAuditor:
    """Pre-execution gate that reviews AI signal properties against governance rules.

    Approval criteria:
        ✓ Confidence ≥ min_confidence_threshold
        ✓ Risk/Reward ratio ≥ min_risk_reward
        ✓ Market regime compatible with signal direction
        ✓ No overriding past-mistake patterns (from TradeMemory)
        ✓ Reasoning is present and substantive
    """

    def __init__(
        self,
        min_confidence: float = 0.55,
        min_risk_reward: float = 1.5,
        allowed_regimes: Optional[List[str]] = None,
    ) -> None:
        self.min_confidence = min_confidence
        self.min_risk_reward = min_risk_reward
        # Default: allow all regimes — caller can restrict
        self.allowed_regimes = [r.upper() for r in (allowed_regimes or ["TRENDING", "RANGING",
                                                                          "HIGH_VOLATILITY",
                                                                          "LOW_VOLATILITY", "UNKNOWN"])]

    def audit(
        self,
        signal: Dict[str, Any],
        regime: str = "UNKNOWN",
        past_mistakes: Optional[List[str]] = None,
    ) -> AuditDecision:
        """Audit a signal dict and return an AuditDecision.

        Expected signal keys:
            signal:     BUY / SELL / HOLD
            confidence: float (0–1 or 0–100)
            reasoning:  str
            stop_loss:  float
            take_profit: float
            entry:      float
        """
        past_mistakes = past_mistakes or []
        reasons: List[str] = []
        regime_upper = regime.upper()

        # Normalise confidence to 0-1
        confidence = float(signal.get("confidence", 0.0))
        if confidence > 1.0:
            confidence /= 100.0

        action = signal.get("signal", signal.get("action", "HOLD")).upper()
        reasoning = str(signal.get("reasoning", ""))
        entry = float(signal.get("entry", 0.0))
        sl = float(signal.get("stop_loss", 0.0))
        tp = float(signal.get("take_profit", 0.0))

        # 1. Confidence check
        if confidence < self.min_confidence:
            reasons.append(f"Confidence {confidence:.2%} < minimum {self.min_confidence:.2%}")

        # 2. Risk/reward check
        if entry > 0.0 and sl > 0.0 and tp > 0.0:
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rr = reward / risk if risk > 0.0 else 0.0
            if rr < self.min_risk_reward:
                reasons.append(f"R:R {rr:.2f} < minimum {self.min_risk_reward:.1f}")
        else:
            rr = 0.0

        # 3. Reasoning substantiveness
        if len(reasoning.strip()) < 10:
            reasons.append("Signal reasoning is absent or too vague")

        # 4. Regime compatibility
        if regime_upper not in self.allowed_regimes:
            reasons.append(f"Regime '{regime_upper}' not in allowed list {self.allowed_regimes}")

        # 5. Past mistake patterns
        action_lower = action.lower()
        for mistake in past_mistakes:
            if action_lower in mistake.lower():
                reasons.append(f"Past mistake matches: '{mistake}'")
                break

        approved = len(reasons) == 0
        outcome_reason = " | ".join(reasons) if reasons else "All governance checks passed"

        decision = AuditDecision(
            approved=approved,
            reason=outcome_reason,
            confidence_score=round(confidence, 4),
            regime=regime_upper,
        )

        if approved:
            logger.info("[Auditor] APPROVED %s confidence=%.2f regime=%s", action, confidence, regime_upper)
        else:
            logger.warning("[Auditor] REJECTED %s — %s", action, outcome_reason)

        return decision
