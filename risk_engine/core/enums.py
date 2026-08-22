"""Enums for the Risk Engine subsystem."""

from __future__ import annotations

import enum


class RiskDecision(enum.Enum):
    """Permissibility status of a proposed trading setup or execution request."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"


class RiskSeverity(enum.Enum):
    """Severity levels of identified risk factors and violations."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CircuitBreakerTriggerType(enum.Enum):
    """Trigger reasons for circuit breakers."""

    DAILY_LOSS = "DAILY_LOSS"
    WEEKLY_LOSS = "WEEKLY_LOSS"
    MONTHLY_LOSS = "MONTHLY_LOSS"
    VOLATILITY = "VOLATILITY"
    CONSECUTIVE_LOSS = "CONSECUTIVE_LOSS"
    HIGH_CORRELATION = "HIGH_CORRELATION"
    LATENCY = "LATENCY"
    BROKER_FAILURE = "BROKER_FAILURE"
    EXCHANGE_FAILURE = "EXCHANGE_FAILURE"
    EMERGENCY_STOP = "EMERGENCY_STOP"
