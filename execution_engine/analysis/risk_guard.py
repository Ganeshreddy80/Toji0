from typing import List, Optional
import logging
from execution_engine.core.models import ExecutionRequest, ExecutionConfig
from execution_engine.brokers.broker_interface import IBrokerAdapter

logger = logging.getLogger(__name__)


class ExecutionRiskGuard:
    """Pre-trade safety check gate verifying connectivity, halts, locks, and drifts."""

    def __init__(self, config: ExecutionConfig) -> None:
        self._config = config
        self._halted_symbols = set()
        self._locked_positions = set()
        self._disabled_symbols = set()

    def set_market_halted(self, symbol: str, halted: bool) -> None:
        """Flag symbol trading status as halted."""
        if halted:
            self._halted_symbols.add(symbol.upper())
        else:
            self._halted_symbols.discard(symbol.upper())

    def lock_position(self, position_id: str, locked: bool) -> None:
        """Lock position parameters to block execution submissions."""
        if locked:
            self._locked_positions.add(position_id)
        else:
            self._locked_positions.discard(position_id)

    def disable_symbol(self, symbol: str, disabled: bool) -> None:
        """Flag symbol as disabled."""
        if disabled:
            self._disabled_symbols.add(symbol.upper())
        else:
            self._disabled_symbols.discard(symbol.upper())

    def check_request(self, request: ExecutionRequest, adapter: Optional[IBrokerAdapter]) -> List[str]:
        """Perform risk gate checks. Returns a list of check violations."""
        violations = []
        symbol = request.symbol.upper()

        # 1. Broker Online Connection Check
        if adapter is not None:
            try:
                if not adapter.ping():
                    violations.append("ExecutionRiskGuard: Broker connection is offline.")
            except Exception as e:
                violations.append(f"ExecutionRiskGuard: Broker ping failed: {e}")
        else:
            violations.append("ExecutionRiskGuard: No active broker adapter resolved.")

        # 2. Halted/Disabled checks
        if symbol in self._halted_symbols:
            violations.append(f"ExecutionRiskGuard: Trading is halted for symbol {symbol}.")
        if symbol in self._disabled_symbols:
            violations.append(f"ExecutionRiskGuard: Symbol {symbol} is disabled.")

        # 3. Position Locks
        if request.position_id in self._locked_positions:
            violations.append(f"ExecutionRiskGuard: Target position {request.position_id} is locked.")

        # 4. Margin Change Guard Checks
        max_margin = self._config.timeouts_ms.get("max_margin_per_order", 50000)
        if request.margin_required > max_margin:
            violations.append(
                f"ExecutionRiskGuard: Request margin required (${request.margin_required:.2f}) "
                f"exceeds limit (${max_margin:.2f})."
            )

        # 5. Price Drift / Slippage Checks
        if request.price is not None and request.stop_price is not None:
            drift = abs(request.price - request.stop_price) / request.stop_price
            max_drift = self._config.slippage_model.get("max_drift_percent", 0.05)
            if drift > max_drift:
                violations.append(
                    f"ExecutionRiskGuard: Price drift between limit and stop trigger ({drift:.2%}) "
                    f"exceeds maximum allowed ({max_drift:.2%})."
                )

        return violations
