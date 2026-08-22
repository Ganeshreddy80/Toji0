"""Circuit Breaker Engine for managing risk-based halts, emergency stops, and cooldown periods."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from risk_engine.core.enums import CircuitBreakerTriggerType
from risk_engine.core.models import CircuitBreakerState

logger = logging.getLogger(__name__)


class CircuitBreakerEngine:
    """Manages active circuit breakers, manual overrides, and release cooldowns."""

    def __init__(self) -> None:
        pass

    def evaluate_breakers(
        self,
        current_state: CircuitBreakerState | None = None,
        daily_loss_triggered: bool = False,
        weekly_loss_triggered: bool = False,
        monthly_loss_triggered: bool = False,
        consecutive_losses_triggered: bool = False,
        volatility_triggered: bool = False,
        correlation_triggered: bool = False,
        latency_triggered: bool = False,
        broker_failure: bool = False,
        exchange_failure: bool = False,
        manual_emergency_stop: bool = False,
        cooldown_until: datetime | None = None,
    ) -> tuple[CircuitBreakerState, list[tuple[CircuitBreakerTriggerType, str]]]:
        """
        Evaluate breaker flags and return the CircuitBreakerState and list of transitions.
        Returns:
            - Updated CircuitBreakerState
            - List of (trigger_type, action) transitions (where action is "TRIGGERED" or "RELEASED")
        """
        active_now: list[CircuitBreakerTriggerType] = []
        transitions: list[tuple[CircuitBreakerTriggerType, str]] = []

        mapping = [
            (CircuitBreakerTriggerType.DAILY_LOSS, daily_loss_triggered),
            (CircuitBreakerTriggerType.WEEKLY_LOSS, weekly_loss_triggered),
            (CircuitBreakerTriggerType.MONTHLY_LOSS, monthly_loss_triggered),
            (CircuitBreakerTriggerType.CONSECUTIVE_LOSS, consecutive_losses_triggered),
            (CircuitBreakerTriggerType.VOLATILITY, volatility_triggered),
            (CircuitBreakerTriggerType.HIGH_CORRELATION, correlation_triggered),
            (CircuitBreakerTriggerType.LATENCY, latency_triggered),
            (CircuitBreakerTriggerType.BROKER_FAILURE, broker_failure),
            (CircuitBreakerTriggerType.EXCHANGE_FAILURE, exchange_failure),
            (CircuitBreakerTriggerType.EMERGENCY_STOP, manual_emergency_stop),
        ]

        previous_breakers = current_state.active_breakers if current_state else []

        for trigger_type, is_active in mapping:
            if is_active:
                active_now.append(trigger_type)
                if trigger_type not in previous_breakers:
                    transitions.append((trigger_type, "TRIGGERED"))
                    logger.critical("CircuitBreaker: Breaker triggered: %s", trigger_type.name)
            else:
                if trigger_type in previous_breakers:
                    transitions.append((trigger_type, "RELEASED"))
                    logger.info("CircuitBreaker: Breaker released: %s", trigger_type.name)

        # Check cooldown until condition
        halt_trading = len(active_now) > 0
        now = datetime.now(timezone.utc)
        if cooldown_until and now < cooldown_until:
            halt_trading = True

        state = CircuitBreakerState(
            active_breakers=active_now,
            halt_trading=halt_trading,
            cooldown_until=cooldown_until,
        )

        return state, transitions
