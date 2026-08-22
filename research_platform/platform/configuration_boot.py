"""Centralized configuration bootloader — delegates to R51 ConfigManager.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ConfigurationBootloader:
    """Loads system configuration via R51 ConfigManager, falling back to defaults."""

    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}

    def load_configuration(self) -> Dict[str, Any]:
        try:
            from research_platform.config.config_manager import ConfigManager
            mgr = ConfigManager()
            cfg = mgr.get_config()
            self._config = cfg.model_dump()
            logger.info("R51 ConfigManager loaded configuration (profile=%s).", cfg.runtime.mode)
        except Exception as e:
            logger.warning("R51 ConfigManager unavailable (%s), using defaults.", e)
            self._config = {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "toji_v1",
                    "username": "postgres",
                    "password": "",
                },
                "runtime": {"mode": "PAPER"},
            }

        # Legacy backward compatibility mappings for R11-style subsystems & test suites
        db_cfg = self._config.setdefault("database", {})

        # Parse DATABASE_URL if present in environment (e.g. passed from .env via Docker)
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            try:
                from urllib.parse import urlparse
                # Normalize scheme for urlparse (strip driver prefix)
                parse_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
                parsed = urlparse(parse_url)
                if parsed.hostname:
                    db_cfg["host"] = parsed.hostname
                if parsed.port:
                    db_cfg["port"] = parsed.port
                if parsed.path:
                    db_cfg["database"] = parsed.path.lstrip("/")
                if parsed.username:
                    db_cfg["username"] = parsed.username
                if parsed.password is not None:
                    db_cfg["password"] = parsed.password
                # Preserve the full raw URL so connection.py can use it directly
                # (Neon requires sslmode=require&channel_binding=require query params)
                # Use the normalized postgresql:// form so psycopg2 driver handles it
                db_cfg["raw_url"] = parse_url
            except Exception as e:
                logger.warning("Failed to parse DATABASE_URL: %s", e)
        
        # Under pytest/local runs, redirect toji-postgres to localhost and use legacy db/user credentials
        if "PYTEST_CURRENT_TEST" in os.environ or "pytest" in os.environ.get("_", ""):
            if db_cfg.get("host") in ("postgres-prod", "toji-postgres"):
                db_cfg["host"] = "localhost"
            db_cfg["dbname"] = "toji_v1"
            db_cfg["user"] = "postgres"
        else:
            db_cfg.setdefault("host", "localhost")
            db_cfg.setdefault("port", 5432)

            if "database" in db_cfg:
                db_cfg["dbname"] = db_cfg["database"]
            else:
                db_cfg.setdefault("dbname", "toji_v1")

            if "username" in db_cfg:
                db_cfg["user"] = db_cfg["username"]
            else:
                db_cfg.setdefault("user", "postgres")

        self._config.setdefault("environment", "PRODUCTION")
        self._config.setdefault("log_level", "INFO")

        return self._config
