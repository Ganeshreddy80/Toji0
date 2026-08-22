"""SQLAlchemy Connection and Engine Pool Configuration.
"""

from __future__ import annotations

import logging
from typing import Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages SQLAlchemy Engine lifecycle with automatic SQLite fallback."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._engine: Engine | None = None
        self._fallback_mode = False

    def initialize(self) -> None:
        """Create SQLAlchemy Engine connection pool."""
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 5432)
        dbname = self.config.get("dbname", "toji_v1")
        user = self.config.get("user", "postgres")
        password = self.config.get("password", "")

        # If a full raw URL is available (e.g. Neon with sslmode query params), use it directly
        # so that SSL parameters are not stripped by the host/port reconstruction below.
        raw_url = self.config.get("raw_url", "")
        if raw_url:
            pg_url = raw_url
        else:
            pg_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

        # Detect if SSL is required based on URL (Neon always requires it)
        # sslmode=require or ssl in query string means we must not strip these params
        is_ssl = "sslmode" in pg_url or "ssl" in pg_url
        # Neon pooler connections use port 5432 — no special port needed, but longer timeout
        connect_timeout = 10 if is_ssl else 2

        try:
            logger.info("Initializing PostgreSQL Connection Pool on %s:%s (ssl=%s)", host, port, is_ssl)
            engine = create_engine(
                pg_url,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                # DB-004: pool_pre_ping emits a lightweight SELECT 1 before each
                # connection checkout, preventing use of dead connections in long-running
                # paper trading sessions without significant throughput cost.
                pool_pre_ping=True,
                # DB-004: pool_recycle=1800 (30 min) forces connection retirement
                # after 30 minutes, preventing stale connections after network events.
                pool_recycle=1800,
                connect_args={"connect_timeout": connect_timeout}
            )
            # Test connection
            with engine.connect() as conn:
                pass
            self._engine = engine
            logger.info("PostgreSQL connection verified successfully.")
        except Exception as e:
            if host in ("toji-postgres", "postgres-prod") or host != "localhost":
                logger.warning("PostgreSQL connection to %s failed: %s. Retrying with localhost...", host, e)
                try:
                    local_url = f"postgresql://{user}:{password}@localhost:{port}/{dbname}"
                    engine = create_engine(
                        local_url,
                        pool_size=20,
                        max_overflow=10,
                        pool_timeout=5,
                        pool_pre_ping=True,
                        pool_recycle=1800,
                        connect_args={"connect_timeout": 2}
                    )
                    with engine.connect() as conn:
                        pass
                    self._engine = engine
                    logger.info("PostgreSQL connection to localhost verified successfully.")
                    return
                except Exception as local_err:
                    logger.warning("PostgreSQL localhost retry failed: %s", local_err)
                    e = local_err

            import os
            import sys
            is_pytest = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)
            toji_mode = os.getenv("TOJI_MODE", "PAPER").upper()
            force_check = os.getenv("FORCE_DB_FALLBACK_CHECK") == "true"
            if toji_mode != "DEV" and (not is_pytest or force_check):
                # 1. Alert Telegram directly via urllib
                try:
                    token = os.getenv("TELEGRAM_BOT_TOKEN")
                    chat_id = os.getenv("TELEGRAM_CHAT_ID")
                    if token and chat_id:
                        import urllib.request
                        import urllib.parse
                        msg = f"🚨 TOJI DATABASE ERROR\n\nPostgreSQL connection failed: {e}\nMode: {toji_mode}\nPlatform is halting."
                        url = f"https://api.telegram.org/bot{token}/sendMessage"
                        data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode("utf-8")
                        req = urllib.request.Request(url, data=data)
                        with urllib.request.urlopen(req, timeout=5.0) as response:
                            pass
                except Exception as alert_err:
                    logger.debug("Failed to dispatch raw telegram alert: %s", alert_err)
                
                # 2. Raise exception to stop trading safely
                raise RuntimeError(f"Database connection failed in {toji_mode} mode. Fallback SQLite is disabled. Reason: {e}") from e
            else:
                logger.warning(
                    "PostgreSQL connection failed: %s. Falling back to in-memory SQLite for stability.", e
                )
                from sqlalchemy.pool import StaticPool
                self._fallback_mode = True
                self._engine = create_engine(
                    "sqlite:///:memory:",
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool
                )

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self.initialize()
        return self._engine

    def connect(self) -> Any:
        return self.engine.connect()

    def reconnect(self) -> None:
        """DB-005: Dispose the existing engine and re-initialize from scratch.

        Previously DatabaseRecoveryManager called db.connect() on an already-initialized
        DatabaseLifecycleManager — that was a no-op because connect() short-circuits
        when _connection is not None. This method disposes the dead engine pool and
        calls initialize() to create a fresh engine with live connections.
        """
        if self._engine is not None:
            try:
                self._engine.dispose()
                logger.info("DatabaseConnection: disposed stale engine pool for reconnect.")
            except Exception as dispose_err:
                logger.warning("DatabaseConnection: engine dispose warning: %s", dispose_err)
        self._engine = None
        self._fallback_mode = False
        self.initialize()
        logger.info("DatabaseConnection: reconnect complete.")

    @property
    def is_fallback(self) -> bool:
        return self._fallback_mode
