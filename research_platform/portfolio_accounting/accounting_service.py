"""Portfolio Accounting Service — top-level facade.

Subscribes to EventBus events and orchestrates all accounting engines.
This is the single entry point for all accounting operations.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from research_platform.portfolio_accounting.performance_engine import PerformanceEngine
from research_platform.portfolio_accounting.ledger_repository import LedgerRepository
from research_platform.portfolio_accounting.models import PortfolioMetrics, PortfolioSnapshot, TradeLedgerEntry
from research_platform.portfolio_accounting.portfolio_accounting_engine import PortfolioAccountingEngine
from research_platform.portfolio_accounting.position_history import PositionHistory
from research_platform.portfolio_accounting.position_valuation_engine import PositionValuationEngine
from research_platform.portfolio_accounting.trade_journal import TradeJournal

logger = logging.getLogger(__name__)


class AccountingService:
    """Wires all portfolio accounting engines and routes events."""

    COMMISSION_RATE = 0.0005   # 0.05% per fill (Binance standard)
    SLIPPAGE_RATE   = 0.0001   # 0.01% market impact estimate

    def __init__(
        self,
        event_bus: Any,
        initial_balance: float = 100_000.0,
    ) -> None:
        self._event_bus = event_bus
        self._initial_balance = initial_balance

        self._valuation_engine = PositionValuationEngine()
        self._accounting_engine = PortfolioAccountingEngine(initial_balance)
        self._metrics_engine = PerformanceEngine()
        self._ledger_repository = LedgerRepository()
        self._journal = TradeJournal()
        self._history = PositionHistory()

        # Track entry times for completed trade records
        self._entry_times: dict[str, datetime] = {}
        self._entry_prices: dict[str, float] = {}

        self._latest_metrics: Optional[PortfolioMetrics] = None

    @property
    def ledger_repository(self) -> LedgerRepository:
        return self._ledger_repository

    @property
    def metrics_engine(self) -> PerformanceEngine:
        return self._metrics_engine

    # ── Event Handlers ────────────────────────────────────────────────────────

    def on_market_tick(self, event: Any) -> None:
        """Handle system.market_data_received — update all open positions."""
        try:
            payload = getattr(event, "payload", {}) or {}
            symbol = payload.get("symbol") or payload.get("s") or payload.get("ticker")
            price_raw = payload.get("price") or payload.get("p") or payload.get("last_price") or payload.get("c")
            if not symbol or price_raw is None:
                return
            price = float(price_raw)

            # Update valuation for this symbol
            pos = self._valuation_engine.on_tick(symbol, price)
            if pos is None:
                return  # no open position for this symbol

            # Publish PositionValuationUpdated
            try:
                from research_platform.portfolio_accounting.events import PositionValuationUpdated
                self._event_bus.publish(PositionValuationUpdated(payload={
                    "symbol": symbol,
                    "price": price,
                    "unrealized_pnl": round(pos.unrealized_pnl, 4),
                    "pnl_percent": round(pos.pnl_percent, 4),
                    "mfe": round(pos.max_favorable_excursion, 4),
                    "mae": round(pos.max_adverse_excursion, 4),
                }))
            except Exception:
                pass

            # Publish central portfolio state updates
            self._publish_portfolio_state()

        except Exception as e:
            logger.error("AccountingService.on_market_tick error: %s", e)

    def on_fill(self, event: Any) -> None:
        """Handle order matched / filled events — open/update/close position."""
        try:
            payload = getattr(event, "payload", {}) or {}
            symbol   = payload.get("symbol", "")
            side     = payload.get("side", "BUY")
            quantity = float(payload.get("quantity", 0.0))
            price    = float(payload.get("price", 0.0))
            rationale = payload.get("rationale", "signal_trade")
            strategy  = payload.get("strategy", "")
            ai_conf   = float(payload.get("ai_confidence", 0.0))
            order_id = payload.get("order_id", f"ord_{uuid.uuid4().hex[:8]}")

            if not symbol or quantity == 0.0 or price == 0.0:
                return

            commission = price * quantity * self.COMMISSION_RATE
            slippage   = price * quantity * self.SLIPPAGE_RATE

            realized_pnl = 0.0
            pos_after = None
            pos = None
            if side == "SELL":
                # Closing / reducing trade
                existing = self._valuation_engine.get_position(symbol)
                entry_price = existing.average_entry if existing else price
                entry_time  = self._entry_times.pop(symbol, datetime.now(timezone.utc))

                pos_after, realized_pnl = self._valuation_engine.on_close(
                    symbol, quantity, price, commission
                )
                self._accounting_engine.apply_fill(side, quantity, price, commission, slippage)
                self._accounting_engine.apply_close_pnl(realized_pnl)

                # Trade journal
                record = TradeJournal.build_record(
                    symbol=symbol,
                    side="BUY",
                    quantity=quantity,
                    entry_price=entry_price,
                    exit_price=price,
                    entry_time=entry_time,
                    realized_pnl=realized_pnl,
                    commission=commission,
                    slippage=slippage,
                    strategy=strategy,
                    ai_confidence=ai_conf,
                    rationale=rationale,
                    reason_closed="SIGNAL",
                )
                self._journal.record(record)
                self._metrics_engine.ingest_trade(record)

                # Publish TradeClosed
                try:
                    from research_platform.portfolio_accounting.events import TradeClosed
                    self._event_bus.publish(TradeClosed(payload={
                        "symbol": symbol,
                        "realized_pnl": round(realized_pnl, 4),
                        "net_pnl": round(record.net_pnl, 4),
                        "return_pct": record.return_pct,
                    }))
                except Exception:
                    pass

            else:
                # Opening / adding to position
                pos = self._valuation_engine.on_fill(symbol, side, quantity, price, commission)
                self._accounting_engine.apply_fill(side, quantity, price, commission, slippage)
                if symbol not in self._entry_times:
                    self._entry_times[symbol] = datetime.now(timezone.utc)
                    self._entry_prices[symbol] = price

            # Record in Ledger Repository
            ledger_entry = TradeLedgerEntry(
                trade_id=f"trd_{uuid.uuid4().hex[:8]}",
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=self._entry_prices.get(symbol, price) if side == "SELL" else price,
                exit_price=price if side == "SELL" else 0.0,
                commission=commission,
                slippage=slippage,
                realized_pnl=realized_pnl,
                timestamp=datetime.now(timezone.utc)
            )
            self._ledger_repository.append(ledger_entry)

            # Resolve service container and update OMS status
            from research_platform.platform.service_registry import ServiceRegistry
            registry = ServiceRegistry()
            container = registry.get_service("Container")
            if container and container.has("OrderManagementSystemOrchestrator"):
                oms = container.resolve("OrderManagementSystemOrchestrator")
                try:
                    # Let's get the order from repo using the strategy field (OMS order_id or strategy_id)
                    oms_order = oms.repository.get_order(strategy)
                    if not oms_order:
                        all_orders = oms.repository.list_orders()
                        for o in all_orders:
                            if (o.strategy_id == strategy or o.order_id == strategy) and o.symbol == symbol and o.status != "FILLED":
                                oms_order = o
                                break
                        if not oms_order:
                            for o in all_orders:
                                if (o.strategy_id == strategy or o.order_id == strategy) and o.status != "FILLED":
                                    oms_order = o
                                    break
                    
                    if oms_order and oms_order.status != "FILLED":
                        current_order = oms_order
                        if current_order.status == "ROUTED":
                            current_order = oms._state_machine.transition(current_order, "PENDING")
                            oms.repository.save_order(current_order)
                        if current_order.status == "PENDING":
                            filled_order = oms._state_machine.transition(current_order, "FILLED")
                            filled_order = filled_order.model_copy(update={
                                "executed_price": price,
                                "executed_quantity": quantity,
                                "filled_quantity": quantity,
                                "avg_price": price
                            })
                            oms.repository.save_order(filled_order)
                            
                            from research_platform.oms.models import OrderAudit
                            audit = OrderAudit(
                                audit_id=str(uuid.uuid4()),
                                order_id=oms_order.order_id,
                                previous_status=oms_order.status,
                                new_status="FILLED",
                                message="Simulated fill completed on exchange."
                            )
                            oms.repository.save_audit(audit)
                            logger.info("AccountingService: transitioned OMS order %s to FILLED ✓", oms_order.order_id)
                except Exception as e:
                    logger.error("AccountingService: failed to transition OMS order status: %s", e)

            # Persist executed fill to trades, positions, and trade_ledger tables
            # DB-009: explicit ERROR log when Database service is absent so failures are never silent.
            db = registry.get_service("Database")
            if db is None:
                logger.error(
                    "AccountingService.on_fill: Database service not registered in ServiceRegistry — "
                    "trade/position/ledger writes skipped for order_id=%s symbol=%s. "
                    "This is a persistence failure, not expected behaviour.",
                    order_id, symbol
                )
            else:
                try:
                    from research_platform.persistence.postgres.session import DatabaseSessionManager
                    from research_platform.persistence.postgres.transaction_manager import TransactionManager
                    from research_platform.persistence.repositories.trade_repository import PostgresTradeRepository
                    from research_platform.persistence.repositories.position_repository import PostgresPositionRepository
                    from research_platform.persistence.repositories.ledger_repository import PostgresLedgerRepository
                    from research_platform.paper_trading.models import PaperPosition

                    session_mgr = DatabaseSessionManager(db)
                    trade_repo = PostgresTradeRepository(session_mgr)
                    pos_repo = PostgresPositionRepository(session_mgr)
                    ledger_repo = PostgresLedgerRepository(session_mgr)
                    tx_mgr = TransactionManager(session_mgr)

                    # DB-001: single atomic transaction — all three writes share one session_scope().
                    # TransactionManager.transaction() calls session_scope(), which sets
                    # _local.active_session. Each subsequent repository call into session_scope()
                    # hits the re-entrancy guard and yields the SAME session without committing.
                    # The outer context manager commits (or rolls back) all three writes together.
                    with tx_mgr.transaction():
                        # 1. Save trade record
                        trade_repo.save_trade(
                            trade_id=ledger_entry.trade_id,
                            order_id=order_id,
                            symbol=symbol,
                            side=side,
                            quantity=quantity,
                            price=price,
                            timestamp=ledger_entry.timestamp
                        )

                        # 2. Save/update position
                        if side == "SELL":
                            if pos_after is None or pos_after.quantity == 0.0:
                                pos_repo.delete(symbol)
                            else:
                                pos_repo.save_position(
                                    PaperPosition(
                                        symbol=symbol,
                                        quantity=pos_after.quantity,
                                        entry_price=pos_after.average_entry,
                                        current_price=price
                                    )
                                )
                        else:
                            pos_repo.save_position(
                                PaperPosition(
                                    symbol=symbol,
                                    quantity=pos.quantity,
                                    entry_price=pos.average_entry,
                                    current_price=price
                                )
                            )

                        # 3. Save trade_ledger entry
                        ledger_repo.save_entry(ledger_entry)

                    logger.info("AccountingService: saved trade, position & ledger updates to PostgreSQL ✓")
                except Exception as db_err:
                    logger.error("AccountingService: database persistence error (all writes rolled back): %s", db_err)

            # Publish central portfolio state updates
            self._publish_portfolio_state()

        except Exception as e:
            logger.error("AccountingService.on_fill error: %s", e, exc_info=True)

    def on_position_closed(self, event: Any) -> None:
        """Handle position closed from broker or external source."""
        try:
            payload = getattr(event, "payload", {}) or {}
            symbol = payload.get("symbol")
            if symbol:
                self._valuation_engine.on_close(symbol, 0.0, 0.0, 0.0) # clean valuation
                
                # Delete from SQL database
                from research_platform.platform.service_registry import ServiceRegistry
                registry = ServiceRegistry()
                db = registry.get_service("Database")
                if db:
                    from research_platform.persistence.postgres.session import DatabaseSessionManager
                    from research_platform.persistence.repositories.position_repository import PostgresPositionRepository
                    session_mgr = DatabaseSessionManager(db)
                    pos_repo = PostgresPositionRepository(session_mgr)
                    pos_repo.delete(symbol)
                    
                self._publish_portfolio_state()
        except Exception as e:
            logger.error("AccountingService.on_position_closed error: %s", e)

    def on_position_updated(self, event: Any) -> None:
        """Handle position updated from broker or external source."""
        try:
            payload = getattr(event, "payload", {}) or {}
            symbol = payload.get("symbol")
            quantity = float(payload.get("quantity") or payload.get("amount") or 0.0)
            price = float(payload.get("price") or payload.get("entry_price") or 0.0)
            side = payload.get("side") or ("BUY" if quantity >= 0 else "SELL")
            quantity = abs(quantity)
            if symbol:
                self._valuation_engine.on_fill(symbol, side, quantity, price, 0.0)
                
                # Save to SQL database
                from research_platform.platform.service_registry import ServiceRegistry
                registry = ServiceRegistry()
                db = registry.get_service("Database")
                if db:
                    from research_platform.persistence.postgres.session import DatabaseSessionManager
                    from research_platform.persistence.repositories.position_repository import PostgresPositionRepository
                    from research_platform.paper_trading.models import PaperPosition
                    session_mgr = DatabaseSessionManager(db)
                    pos_repo = PostgresPositionRepository(session_mgr)
                    pos_repo.save_position(
                        PaperPosition(
                            symbol=symbol,
                            quantity=quantity,
                            entry_price=price,
                            current_price=price
                        )
                    )
                self._publish_portfolio_state()
        except Exception as e:
            logger.error("AccountingService.on_position_updated error: %s", e)

    def _publish_portfolio_state(self) -> None:
        """Helper to compute latest snapshot and publish PnL, Drawdown, and Performance updates."""
        try:
            positions = self._valuation_engine.get_all_positions()
            snapshot = self._accounting_engine.recalculate(positions)
            
            # Recalculate metrics
            self._latest_metrics = self._metrics_engine.compute(
                self._initial_balance,
                snapshot.equity,
                positions
            )

            # Record equity for curves
            self._metrics_engine.record_equity(snapshot.equity)

            from research_platform.portfolio_accounting.events import (
                PortfolioUpdated,
                PnLUpdated,
                DrawdownUpdated,
                PerformanceUpdated
            )

            # Publish PortfolioUpdated
            self._event_bus.publish(PortfolioUpdated(payload={
                "equity": snapshot.equity,
                "cash": snapshot.cash_balance,
                "portfolio_value": snapshot.portfolio_value,
                "buying_power": snapshot.buying_power,
                "realized_pnl": snapshot.realized_pnl,
                "unrealized_pnl": snapshot.unrealized_pnl,
                "exposure": snapshot.total_exposure,
            }))

            # Publish PnLUpdated
            self._event_bus.publish(PnLUpdated(payload={
                "realized_pnl": snapshot.realized_pnl,
                "unrealized_pnl": snapshot.unrealized_pnl,
                "daily_pnl": snapshot.daily_pnl,
            }))

            # Publish DrawdownUpdated
            self._event_bus.publish(DrawdownUpdated(payload={
                "drawdown": self._latest_metrics.max_drawdown_pct,
                "peak_equity": self._metrics_engine._peak_equity,
                "max_drawdown": self._latest_metrics.max_drawdown,
            }))

            # Publish PerformanceUpdated
            self._event_bus.publish(PerformanceUpdated(payload={
                "win_rate": self._latest_metrics.win_rate,
                "profit_factor": self._latest_metrics.profit_factor,
                "sharpe_ratio": self._latest_metrics.sharpe_ratio,
                "sortino_ratio": self._latest_metrics.sortino_ratio,
                "expectancy": self._latest_metrics.expectancy,
                "trade_count": self._latest_metrics.total_trades,
            }))

        except Exception as e:
            logger.error("AccountingService._publish_portfolio_state error: %s", e)

    # ── Read API ──────────────────────────────────────────────────────────────

    def get_portfolio_summary(self) -> dict:
        """Return a dict suitable for the runtime status API."""
        snapshot = self._accounting_engine.get_snapshot()
        positions = self._valuation_engine.get_all_positions()

        # Recompute metrics dynamically
        self._latest_metrics = self._metrics_engine.compute(
            self._initial_balance,
            snapshot.equity if snapshot else self._initial_balance,
            positions,
        )

        pos_list = [
            {
                "symbol": p.symbol,
                "side": p.side,
                "quantity": p.quantity,
                "average_entry": p.average_entry,
                "current_price": p.current_price,
                "market_value": round(p.market_value, 4),
                "unrealized_pnl": round(p.unrealized_pnl, 4),
                "pnl_percent": round(p.pnl_percent, 4),
                "mfe": round(p.max_favorable_excursion, 4),
                "mae": round(p.max_adverse_excursion, 4),
                "opened_at": p.opened_at.isoformat(),
                "last_update": p.last_update.isoformat(),
            }
            for p in positions
        ]

        equity = snapshot.equity if snapshot else self._initial_balance
        daily_pnl = snapshot.daily_pnl if snapshot else 0.0
        daily_return = (daily_pnl / (equity - daily_pnl) * 100.0) if (equity - daily_pnl) > 0 else 0.0

        base: dict = {
            # Original keys for backward compatibility
            "cash_balance": snapshot.cash_balance if snapshot else self._initial_balance,
            "equity": equity,
            "portfolio_value": snapshot.portfolio_value if snapshot else self._initial_balance,
            "buying_power": snapshot.buying_power if snapshot else self._initial_balance,
            "realized_pnl": snapshot.realized_pnl if snapshot else 0.0,
            "unrealized_pnl": snapshot.unrealized_pnl if snapshot else 0.0,
            "daily_pnl": daily_pnl,
            "fees": snapshot.fees if snapshot else 0.0,
            "open_positions": len(positions),
            "positions": pos_list,

            # Phase 16 mapped keys
            "cash": snapshot.cash_balance if snapshot else self._initial_balance,
            "commission": snapshot.commission if snapshot else 0.0,
            "slippage": snapshot.slippage if snapshot else 0.0,
            "drawdown": self._latest_metrics.max_drawdown_pct if self._latest_metrics else 0.0,
            "peak_equity": self._metrics_engine._peak_equity if self._metrics_engine._peak_equity > 0 else self._initial_balance,
            "daily_return": round(daily_return, 4),
            "total_return": self._latest_metrics.total_return_pct if self._latest_metrics else 0.0,
            "trade_count": self._latest_metrics.total_trades if self._latest_metrics else 0,
            "win_rate": self._latest_metrics.win_rate if self._latest_metrics else 0.0,
            "profit_factor": self._latest_metrics.profit_factor if self._latest_metrics else 0.0,
        }

        if self._latest_metrics:
            base["metrics"] = {
                "total_return_pct": self._latest_metrics.total_return_pct,
                "win_rate": self._latest_metrics.win_rate,
                "profit_factor": self._latest_metrics.profit_factor,
                "sharpe_ratio": self._latest_metrics.sharpe_ratio,
                "max_drawdown_pct": self._latest_metrics.max_drawdown_pct,
                "expectancy": self._latest_metrics.expectancy,
                "total_trades": self._latest_metrics.total_trades,
                "winning_trades": self._latest_metrics.winning_trades,
            }

        return base

    @property
    def trade_journal(self) -> TradeJournal:
        return self._journal

    @property
    def position_history(self) -> PositionHistory:
        return self._history

    @property
    def valuation_engine(self) -> PositionValuationEngine:
        return self._valuation_engine

    def rehydrate_from_db(self, db: Any = None) -> bool:
        """Reconstruct authoritative portfolio state from PostgreSQL tables (positions, trade_ledger).
        
        Reads committed positions and ledger entries, populates in-memory valuation, accounting,
        metrics, and trade journal engines, and publishes state update events.
        
        Returns True if state was successfully rehydrated.
        Raises RuntimeError under PAPER/PROD mode if database is absent or state is invalid (fail-closed).
        """
        if db is None:
            from research_platform.platform.service_registry import ServiceRegistry
            db = ServiceRegistry().get_service("Database")

        if db is None or not getattr(db, "connected", False):
            mode = os.getenv("DATABASE_MODE", os.getenv("TOJI_MODE", "PAPER")).upper()
            if mode != "DEV":
                raise RuntimeError(
                    "FAIL-CLOSED: Database service unavailable for portfolio rehydration in PAPER mode."
                )
            logger.warning("AccountingService.rehydrate_from_db: Database service not connected. Rehydration skipped.")
            return False

        try:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            from research_platform.persistence.repositories.position_repository import PostgresPositionRepository
            from research_platform.persistence.repositories.ledger_repository import PostgresLedgerRepository

            session_mgr = DatabaseSessionManager(db)
            pos_repo = PostgresPositionRepository(session_mgr)
            ledger_repo = PostgresLedgerRepository(session_mgr)

            db_positions = pos_repo.list_positions()
            db_ledger_entries = ledger_repo.list_entries()

            # 1. Clear in-memory valuation engine positions and history for clean rehydration
            with self._valuation_engine._lock:
                self._valuation_engine._positions.clear()
                self._valuation_engine._history.clear()
                self._entry_times.clear()
                self._entry_prices.clear()

            # 2. Rehydrate positions into PositionValuationEngine
            for pos in db_positions:
                side = "BUY" if pos.quantity >= 0 else "SELL"
                qty = abs(pos.quantity)
                self._valuation_engine.on_fill(
                    symbol=pos.symbol,
                    side=side,
                    quantity=qty,
                    price=pos.entry_price,
                    commission=0.0
                )
                self._entry_prices[pos.symbol] = pos.entry_price
                self._entry_times[pos.symbol] = datetime.now(timezone.utc)

            # 3. Clear and rehydrate in-memory ledger repository
            with self._ledger_repository._lock:
                self._ledger_repository._entries.clear()
                for entry in db_ledger_entries:
                    if not any(x.trade_id == entry.trade_id for x in self._ledger_repository._entries):
                        self._ledger_repository._entries.append(entry)

            # 4. Calculate cumulative financial metrics from ledger and positions
            realized_pnl = sum(e.realized_pnl for e in db_ledger_entries)
            commission = sum(e.commission for e in db_ledger_entries)
            slippage = sum(e.slippage for e in db_ledger_entries)
            fees = commission + slippage

            buy_ledger_spent = sum(e.quantity * e.entry_price for e in db_ledger_entries if e.side == "BUY")
            sell_cash_received = sum(e.quantity * e.exit_price for e in db_ledger_entries if e.side == "SELL")
            open_outlay = sum(p.quantity * p.entry_price for p in db_positions)

            buy_cash_spent = buy_ledger_spent if buy_ledger_spent > 0 else open_outlay
            rehydrated_cash = self._initial_balance + sell_cash_received - buy_cash_spent - fees

            # 5. Reconstruct PortfolioAccountingEngine state

            with self._accounting_engine._lock:
                self._accounting_engine._cash_balance = rehydrated_cash
                self._accounting_engine._realized_pnl = realized_pnl
                self._accounting_engine._commission = commission
                self._accounting_engine._slippage = slippage
                self._accounting_engine._fees = fees

            # 6. Reconstruct TradeJournal and MetricsEngine records from completed trade entries
            with self._journal._lock:
                self._journal._records.clear()

            with self._metrics_engine._lock:
                self._metrics_engine._trades.clear()
                self._metrics_engine._equity_curve.clear()

            for entry in db_ledger_entries:
                if entry.exit_price > 0 or entry.side == "SELL":
                    entry_time = entry.timestamp
                    if entry_time and entry_time.tzinfo is None:
                        entry_time = entry_time.replace(tzinfo=timezone.utc)

                    record = TradeJournal.build_record(
                        symbol=entry.symbol,
                        side=entry.side,
                        quantity=entry.quantity,
                        entry_price=entry.entry_price,
                        exit_price=entry.exit_price,
                        entry_time=entry_time,
                        realized_pnl=entry.realized_pnl,
                        commission=entry.commission,
                        slippage=entry.slippage,
                        strategy="",
                        ai_confidence=0.0,
                        rationale="rehydrated_trade",
                        reason_closed="SIGNAL"
                    )
                    self._journal.record(record)
                    self._metrics_engine.ingest_trade(record)


            # 7. Recalculate portfolio snapshot & publish state
            positions_list = self._valuation_engine.get_all_positions()
            snapshot = self._accounting_engine.recalculate(positions_list)
            self._metrics_engine.record_equity(snapshot.equity)

            # Fail-closed guard: negative equity or invalid cash
            if snapshot.equity < 0:
                raise RuntimeError(
                    f"FAIL-CLOSED: Rehydrated portfolio equity is negative ({snapshot.equity}). "
                    "Cannot resume trading with invalid state."
                )

            self._publish_portfolio_state()
            logger.info(
                "AccountingService: state rehydrated from DB ✓ — "
                "open_positions=%d, cash=%.2f, equity=%.2f, realized_pnl=%.2f",
                len(positions_list), snapshot.cash_balance, snapshot.equity, snapshot.realized_pnl
            )
            return True

        except Exception as e:
            logger.error("AccountingService: state rehydration failed: %s", e, exc_info=True)
            mode = os.getenv("DATABASE_MODE", os.getenv("TOJI_MODE", "PAPER")).upper()
            if mode != "DEV":
                raise RuntimeError(f"FAIL-CLOSED: Portfolio rehydration failed: {e}") from e
            return False

