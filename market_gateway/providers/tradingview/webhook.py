"""TradingView Webhook receiver for processing external alerts."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from data.schemas.market_data import OHLCV, NewsEvent
from market_gateway.core.events import MarketCandleEvent, MarketNewsEvent
from market_gateway.normalizer.normalizer import MarketDataNormalizer
from market_gateway.validation.validator import MarketDataValidator
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class TradingViewWebhookReceiver:
    """FastAPI Router webhook receiver for TradingView alerts."""

    def __init__(self, event_bus: IEventBus, validator: MarketDataValidator | None = None) -> None:
        self._event_bus = event_bus
        self._validator = validator or MarketDataValidator()
        self.router = APIRouter()

        @self.router.post("/webhooks/tradingview")
        async def handle_alert(payload: dict[str, Any]) -> dict[str, str]:
            logger.info("Received TradingView alert webhook payload: %s", payload)

            # 1. Normalize
            try:
                normalized = MarketDataNormalizer.normalize_tradingview_alert(payload)
            except Exception as e:
                logger.error("TradingView normalization failed: %s", e)
                raise HTTPException(status_code=400, detail=f"Normalization failed: {e}") from e

            # 2. Validate
            errors = self._validator.validate_event(normalized)
            if errors:
                logger.warning("TradingView alert validation failed: %s", errors)
                raise HTTPException(status_code=400, detail=f"Data validation failed: {errors}")

            # 3. Publish onto event bus
            if isinstance(normalized, OHLCV):
                event = MarketCandleEvent(
                    source="tradingview.webhook",
                    payload={
                        "symbol": normalized.symbol,
                        "data_type": "ohlcv",
                        "prices": [normalized.close],
                        "volumes": [normalized.volume],
                        "data": normalized.model_dump(),
                    },
                )
            elif isinstance(normalized, NewsEvent):
                symbol = normalized.associated_symbols[0] if normalized.associated_symbols else "GLOBAL"
                event = MarketNewsEvent(
                    source="tradingview.webhook",
                    payload={
                        "symbol": symbol,
                        "data_type": "news",
                        "data": normalized.model_dump(),
                    },
                )
            else:
                raise HTTPException(status_code=400, detail="Unsupported normalized model type")

            try:
                self._event_bus.publish(event)
            except Exception as e:
                logger.error("Failed to publish TradingView webhook event: %s", e)
                raise HTTPException(status_code=500, detail=f"Event bus dispatch failed: {e}") from e

            return {"status": "success", "event_id": str(event.event_id)}
