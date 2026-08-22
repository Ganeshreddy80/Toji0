"""Global Kill Switch Engine — monitors risk thresholds and halts trading automatically."""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from research_platform.risk_governance.models import (
    KillSwitchState,
    KillSwitchEvent,
    TriggerReason,
)

logger = logging.getLogger(__name__)


class KillSwitchEngine:
    """Monitors portfolio and market health indicators and enforces trading halts.

    Configuration thresholds (all as positive magnitudes):
        daily_loss_limit_pct:       Stop trading when daily loss exceeds this % of capital.
        max_drawdown_pct:           Halt on portfolio peak-to-trough drawdown exceeding this %.
        max_consecutive_losses:     Reduce risk after N consecutive losing trades.
        min_execution_quality:      Halt if average execution quality score falls below this.
        volatility_multiplier:      Halt if ATR is > multiplier × baseline ATR.
    """

    def __init__(
        self,
        daily_loss_limit_pct: float = 3.0,
        max_drawdown_pct: float = 8.0,
        max_consecutive_losses: int = 5,
        min_execution_quality: float = 60.0,
        volatility_multiplier: float = 3.0,
        starting_capital: float = 100_000.0,
        alert_callback: Optional[Callable[[KillSwitchEvent], None]] = None,
    ) -> None:
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.min_execution_quality = min_execution_quality
        self.volatility_multiplier = volatility_multiplier
        self.starting_capital = starting_capital
        self._alert_callback = alert_callback

        self.state: KillSwitchState = KillSwitchState.NORMAL
        self.events: List[KillSwitchEvent] = []

    # ── public API ────────────────────────────────────────────────────────────

    def persist_state_to_redis(self) -> None:
        """Saves current state metrics to Redis key TOJI:risk_state."""
        try:
            import redis, os, json
            from datetime import datetime, timezone
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.Redis.from_url(redis_url, socket_timeout=1.0, decode_responses=True)
            
            last_trigger = "None"
            if self.events:
                last_trigger = self.events[-1].reason.value
                
            payload = {
                "state": self.state.value,
                "daily_loss": 0.0,
                "drawdown": 0.0,
                "consecutive_losses": 0,
                "last_trigger": last_trigger,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            r.set("TOJI:risk_state", json.dumps(payload))
            logger.info("Persisted KillSwitch risk state to Redis: %s", payload)
        except Exception as e:
            logger.debug("Failed to persist KillSwitch state to Redis: %s", e)

    def load_state_from_redis(self) -> None:
        """Loads state from Redis key TOJI:risk_state."""
        try:
            import redis, os, json
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.Redis.from_url(redis_url, socket_timeout=1.0, decode_responses=True)
            val = r.get("TOJI:risk_state")
            if val:
                payload = json.loads(val)
                self.state = KillSwitchState(payload.get("state", "NORMAL"))
                logger.info("Loaded KillSwitch state from Redis: %s", self.state)
        except Exception as e:
            logger.debug("Failed to load KillSwitch state from Redis: %s", e)

    def evaluate(
        self,
        daily_pnl: float,
        current_capital: float,
        peak_capital: float,
        consecutive_losses: int,
        avg_execution_quality: float,
        current_atr: float = 0.0,
        baseline_atr: float = 0.0,
        exchange_connected: bool = True,
    ) -> KillSwitchState:
        """Evaluate all thresholds and update the kill switch state.

        Returns the new KillSwitchState.
        """
        # Load from redis first to ensure we have the latest state
        self.load_state_from_redis()

        # If already HALTED, we remain HALTED (never automatically recover)
        if self.state == KillSwitchState.HALTED:
            return self.state

        # 1. Exchange disconnect → immediate halt
        if not exchange_connected:
            return self._trigger(
                KillSwitchState.HALTED,
                TriggerReason.EXCHANGE_DISCONNECT,
                "Exchange WebSocket / REST connection lost.",
                current_capital,
            )

        # 2. Daily loss limit
        daily_loss_pct = abs(daily_pnl) / self.starting_capital * 100.0 if daily_pnl < 0 else 0.0
        if daily_loss_pct >= self.daily_loss_limit_pct:
            return self._trigger(
                KillSwitchState.HALTED,
                TriggerReason.DAILY_LOSS_LIMIT,
                f"Daily loss {daily_loss_pct:.2f}% ≥ limit {self.daily_loss_limit_pct:.1f}%.",
                current_capital,
            )

        # 3. Max drawdown
        drawdown_pct = (peak_capital - current_capital) / peak_capital * 100.0 if peak_capital > 0 else 0.0
        if drawdown_pct >= self.max_drawdown_pct:
            return self._trigger(
                KillSwitchState.HALTED,
                TriggerReason.MAX_DRAWDOWN,
                f"Drawdown {drawdown_pct:.2f}% ≥ limit {self.max_drawdown_pct:.1f}%.",
                current_capital,
            )

        # 4. Consecutive losses → REDUCED_RISK
        if consecutive_losses >= self.max_consecutive_losses:
            return self._trigger(
                KillSwitchState.REDUCED_RISK,
                TriggerReason.CONSECUTIVE_LOSSES,
                f"{consecutive_losses} consecutive losses — reducing risk.",
                current_capital,
            )

        # 5. Execution quality drop
        if avg_execution_quality > 0 and avg_execution_quality < self.min_execution_quality:
            return self._trigger(
                KillSwitchState.WARNING,
                TriggerReason.EXECUTION_QUALITY_DROP,
                f"Execution quality {avg_execution_quality:.0f} < {self.min_execution_quality:.0f}.",
                current_capital,
            )

        # 6. Abnormal volatility
        if baseline_atr > 0 and current_atr > self.volatility_multiplier * baseline_atr:
            return self._trigger(
                KillSwitchState.WARNING,
                TriggerReason.ABNORMAL_VOLATILITY,
                f"ATR {current_atr:.2f} > {self.volatility_multiplier}× baseline {baseline_atr:.2f}.",
                current_capital,
            )

        # All clear
        if self.state != KillSwitchState.NORMAL:
            logger.info("KillSwitch: returning to NORMAL.")
        self.state = KillSwitchState.NORMAL
        self.persist_state_to_redis()
        return self.state

    def force_halt(self, reason: str = "Manual override") -> KillSwitchEvent:
        """Immediately halt trading — called by operator."""
        return self._trigger(
            KillSwitchState.HALTED,
            TriggerReason.MANUAL,
            reason,
            0.0,
        )

    @property
    def is_halted(self) -> bool:
        return self.state == KillSwitchState.HALTED

    @property
    def trading_allowed(self) -> bool:
        return self.state in (KillSwitchState.NORMAL, KillSwitchState.WARNING)

    # ── internal ─────────────────────────────────────────────────────────────

    def _trigger(
        self,
        state: KillSwitchState,
        reason: TriggerReason,
        detail: str,
        portfolio_usdt: float,
    ) -> KillSwitchState:
        self.state = state
        event = KillSwitchEvent(
            state=state,
            reason=reason,
            detail=detail,
            portfolio_usdt=portfolio_usdt,
        )
        self.events.append(event)
        logger.warning("KillSwitch [%s] — %s: %s", state.value, reason.value, detail)
        self.persist_state_to_redis()
        if self._alert_callback:
            try:
                self._alert_callback(event)
            except Exception as exc:
                logger.error("KillSwitch alert callback failed: %s", exc)
        return state
