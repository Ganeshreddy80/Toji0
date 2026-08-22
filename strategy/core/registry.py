"""Thread-safe Strategy Registry managing strategy instances and lifecycle."""

from __future__ import annotations

import logging
import threading
from typing import Any

from market_intelligence.core.models import MarketState
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.interfaces import IStrategy, IStrategyRegistry
from strategy.core.models import StrategySignal

logger = logging.getLogger(__name__)


class StrategyRegistry(IStrategyRegistry):
    """Thread-safe registry for registering, managing, and executing strategy modules."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._strategies: dict[StrategyType, IStrategy] = {}
        self._enabled: dict[StrategyType, bool] = {}

    def register_strategy(self, strategy: IStrategy) -> None:
        """Register a strategy module instance."""
        if not hasattr(strategy, "strategy_type") or strategy.strategy_type is None:
            raise ValueError("Strategy must declare a valid strategy_type property.")

        with self._lock:
            st_type = strategy.strategy_type
            self._strategies[st_type] = strategy
            if st_type not in self._enabled:
                self._enabled[st_type] = True
            logger.info("StrategyRegistry: Registered strategy '%s' [%s]", strategy.name, st_type.value)

    def unregister_strategy(self, strategy_type: StrategyType) -> None:
        """Unregister a strategy by type."""
        with self._lock:
            if strategy_type in self._strategies:
                del self._strategies[strategy_type]
                self._enabled.pop(strategy_type, None)
                logger.info("StrategyRegistry: Unregistered strategy [%s]", strategy_type.value)

    def get_strategy(self, strategy_type: StrategyType) -> IStrategy | None:
        """Fetch registered strategy by type."""
        with self._lock:
            return self._strategies.get(strategy_type)

    def list_strategies(self) -> list[IStrategy]:
        """List all currently registered strategy instances."""
        with self._lock:
            return list(self._strategies.values())

    def set_strategy_enabled(self, strategy_type: StrategyType, enabled: bool) -> None:
        """Enable or disable a specific strategy type."""
        with self._lock:
            if strategy_type not in self._strategies:
                raise KeyError(f"Strategy type [{strategy_type.value}] is not registered.")
            self._enabled[strategy_type] = enabled
            logger.info("StrategyRegistry: Set strategy [%s] enabled=%s", strategy_type.value, enabled)

    def is_strategy_enabled(self, strategy_type: StrategyType) -> bool:
        """Check if a strategy type is currently enabled."""
        with self._lock:
            return self._enabled.get(strategy_type, False)

    def evaluate_all(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
        min_confidence: float = 0.0,
    ) -> list[StrategySignal]:
        """
        Evaluate all active, enabled strategies.
        Isolates failures per strategy module so a crash in one strategy does not fail the rest.
        """
        with self._lock:
            active_pairs = [
                (st_type, strat)
                for st_type, strat in self._strategies.items()
                if self._enabled.get(st_type, True)
            ]

        valid_signals: list[StrategySignal] = []

        for st_type, strat in active_pairs:
            try:
                signal = strat.evaluate(market_state, pattern_state, confluence_state)
                if (
                    signal is not None
                    and signal.decision != StrategyDecision.WAIT
                    and signal.confidence >= min_confidence
                ):
                    valid_signals.append(signal)
            except Exception as e:
                logger.error(
                    "StrategyRegistry: Isolated strategy execution failure in '%s' [%s]: %s",
                    getattr(strat, "name", "Unknown"),
                    st_type.value,
                    e,
                    exc_info=True,
                )

        return valid_signals
