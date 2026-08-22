"""Paper Trading Orchestrator serving as single entry point for subsystem (Sprint 9A)."""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional, Tuple

from paper_trading.broker import PaperBroker
from paper_trading.models.paper_models import (
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperOrderType,
    PaperPosition,
    PaperSession,
    PaperTrade,
)
from paper_trading.orders import PaperOrderEngine
from paper_trading.portfolio import PaperPortfolio
from paper_trading.repository import PaperRepository
from paper_trading.session import PaperSessionManager
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class PaperOrchestrator:
    """Authoritative orchestrator coordinating Paper Broker, Portfolio, Order Engine, Repository, and Session Manager."""

    def __init__(
        self,
        portfolio: Optional[PaperPortfolio] = None,
        broker: Optional[PaperBroker] = None,
        order_engine: Optional[PaperOrderEngine] = None,
        repository: Optional[PaperRepository] = None,
        session_manager: Optional[PaperSessionManager] = None,
        event_bus: Optional[IEventBus] = None,
        initial_capital: float = 100000.0,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus

        self._repository = repository or PaperRepository()
        self._portfolio = portfolio or PaperPortfolio(initial_capital=initial_capital)
        self._order_engine = order_engine or PaperOrderEngine()
        self._session_manager = session_manager or PaperSessionManager(
            repository=self._repository,
            event_bus=self._event_bus,
        )
        self._broker = broker or PaperBroker(
            portfolio=self._portfolio,
            order_engine=self._order_engine,
            repository=self._repository,
            event_bus=self._event_bus,
        )

        # Save initial account to repository
        self._repository.save_account(self._portfolio.get_account_snapshot())

    def start_session(
        self,
        initial_capital: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> PaperSession:
        """Initialize and start a paper trading session."""
        with self._lock:
            if initial_capital and initial_capital > 0.0:
                self._portfolio = PaperPortfolio(initial_capital=initial_capital)
                self._broker = PaperBroker(
                    portfolio=self._portfolio,
                    order_engine=self._order_engine,
                    repository=self._repository,
                    event_bus=self._event_bus,
                )

            account = self._portfolio.get_account_snapshot()
            self._repository.save_account(account)

            session = self._session_manager.start_session(account=account, session_id=session_id)
            return session

    def stop_session(self) -> PaperSession:
        """Stop active paper trading session."""
        with self._lock:
            return self._session_manager.stop_session()

    def submit_order(
        self,
        symbol: str,
        side: PaperOrderSide,
        quantity: float,
        order_type: PaperOrderType = PaperOrderType.MARKET,
        limit_price: float = 0.0,
        stop_price: float = 0.0,
        current_market_price: Optional[float] = None,
        order_id: Optional[str] = None,
    ) -> Tuple[PaperOrder, List[PaperTrade]]:
        """Submit paper order to virtual broker."""
        with self._lock:
            return self._broker.submit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                current_market_price=current_market_price,
                order_id=order_id,
            )

    def cancel_order(self, order_id: str) -> PaperOrder:
        """Cancel an active paper order."""
        with self._lock:
            return self._broker.cancel_order(order_id)

    def on_market_price_tick(self, symbol: str, price: float) -> List[Tuple[PaperOrder, PaperTrade]]:
        """Process market price update tick and evaluate pending fills."""
        with self._lock:
            return self._broker.on_market_tick(symbol=symbol, price=price)

    def get_account(self) -> PaperAccount:
        """Get current account snapshot."""
        with self._lock:
            return self._portfolio.get_account_snapshot()

    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        """Get position by symbol."""
        with self._lock:
            return self._portfolio.get_position(symbol)

    def get_all_positions(self) -> Dict[str, PaperPosition]:
        """Get all open positions."""
        with self._lock:
            return self._portfolio.get_all_positions()

    def get_order(self, order_id: str) -> Optional[PaperOrder]:
        """Get order by ID."""
        with self._lock:
            return self._repository.load_order(order_id)

    def list_orders(self) -> List[PaperOrder]:
        """List all paper orders."""
        with self._lock:
            return self._repository.list_orders()

    def list_trades(self) -> List[PaperTrade]:
        """List all executed paper trades."""
        with self._lock:
            return self._repository.list_trades()

    def get_session(self) -> Optional[PaperSession]:
        """Get active paper session."""
        with self._lock:
            return self._session_manager.get_current_session()
