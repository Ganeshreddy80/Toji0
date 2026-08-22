"""Fetches, normalizes, and classifies news articles from News API or mock fallbacks.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class NewsArticle:
    """Canonical normalized news article representation."""

    def __init__(
        self,
        title: str,
        source: str,
        timestamp: datetime,
        sentiment: str | None = None
    ) -> None:
        self.title = title
        self.source = source
        self.timestamp = timestamp
        self.sentiment = sentiment

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "sentiment": self.sentiment
        }


class NewsProvider:
    """Fetches and normalizes market news articles from provider streams."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("NEWS_API_KEY", "")

    def fetch_market_news(self, query: str = "crypto") -> List[NewsArticle]:
        """Fetch news from external News API or fallback to mock articles."""
        if not self.api_key:
            logger.info("News API key not configured. Returning fallback mock news.")
            return self._get_mock_news()

        try:
            import httpx
            url = f"https://newsapi.org/v2/everything?q={query}&apiKey={self.api_key}"
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                articles = data.get("articles", [])
                normalized = []
                for a in articles:
                    published_str = a.get("publishedAt", "")
                    try:
                        dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                    except Exception:
                        dt = datetime.now(timezone.utc)
                    
                    title = a.get("title", "")
                    description = a.get("description", "") or ""
                    sentiment = self._analyze_sentiment(title + " " + description)

                    normalized.append(NewsArticle(
                        title=title,
                        source=a.get("source", {}).get("name", "Unknown"),
                        timestamp=dt,
                        sentiment=sentiment
                    ))
                return normalized
            else:
                logger.warning("News API returned status %s. Using mocks.", response.status_code)
                return self._get_mock_news()
        except Exception as e:
            logger.warning("Failed to fetch news from News API: %s. Using mocks.", e)
            return self._get_mock_news()

    def _analyze_sentiment(self, text: str) -> str:
        text_lower = text.lower()
        bullish_words = ["bullish", "surge", "gain", "breakout", "rally", "growth", "high", "positive", "buy", "up"]
        bearish_words = ["bearish", "drop", "fall", "crash", "plunge", "down", "negative", "sell", "loss", "low"]
        
        bull_count = sum(1 for w in bullish_words if w in text_lower)
        bear_count = sum(1 for w in bearish_words if w in text_lower)
        
        if bull_count > bear_count:
            return "BULLISH"
        elif bear_count > bull_count:
            return "BEARISH"
        return "NEUTRAL"

    def _get_mock_news(self) -> List[NewsArticle]:
        return [
            NewsArticle(
                title="Bitcoin consolidates around key levels as market volatility eases",
                source="CoinDesk Mock",
                timestamp=datetime.now(timezone.utc),
                sentiment="NEUTRAL"
            ),
            NewsArticle(
                title="Ethereum gas fees plunge to record lows amid layer-2 migration",
                source="CoinTelegraph Mock",
                timestamp=datetime.now(timezone.utc),
                sentiment="BULLISH"
            )
        ]
