"""R52 Trade Logger — records every order placement, fill, and rejection.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from research_platform.logging.interfaces import ITradeLogger
from research_platform.logging.models import TradeLogRecord
from research_platform.logging.rotation import create_rotating_file_handler
from research_platform.logging.formatter import StructuredJsonFormatter

_trade_logger = logging.getLogger("toji.trade")
if not _trade_logger.handlers:
    _h = create_rotating_file_handler("logs", "trades.log", formatter=StructuredJsonFormatter())
    _trade_logger.addHandler(_h)
    _trade_logger.setLevel(logging.DEBUG)
    _trade_logger.propagate = False


class TradeLogger(ITradeLogger):
    """Persists structured trade records to trades.log."""

    def log_trade(self, record: TradeLogRecord) -> None:
        extra = {
            "correlation_id": record.order_id,
            "extra_data": {
                "side": record.side,
                "symbol": record.symbol,
                "quantity": record.quantity,
                "price": record.price,
                "status": record.status,
                "details": record.details,
            }
        }
        msg = (
            f"TRADE | order={record.order_id} | {record.side} {record.quantity} "
            f"{record.symbol} @ {record.price} | status={record.status}"
        )
        _trade_logger.info(msg, extra=extra)

    def record_order(
        self,
        order_id: str,
        side: str,
        symbol: str,
        quantity: float,
        price: float,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        rec = TradeLogRecord(
            order_id=order_id,
            side=side,
            symbol=symbol,
            quantity=quantity,
            price=price,
            status=status,
            details=details or {},
        )
        self.log_trade(rec)
