"""Configuration bootloader used by the platform composition root."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict

from research_platform.config.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class ConfigurationBootloader:
    """Load configuration without triggering durable persistence before DB boot."""

    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}

    def load_configuration(self) -> Dict[str, Any]:
        profile_name = os.environ.get("TOJI_PROFILE", "PAPER")
        is_pytest = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)
        loader = ConfigLoader(
            profile_name,
            # Unit/platform tests and explicit DEV runs remain local; the
            # deployed application path is strict for PAPER/PROD.
            require_secure_database=not is_pytest,
        )
        self._config = loader.load_configuration()
        logger.info(
            "Configuration loaded for platform boot (profile=%s, runtime_mode=%s).",
            profile_name,
            self._config.get("runtime", {}).get("mode"),
        )

        # Legacy backward compatibility mappings for R11-style subsystems & test suites.
        db_cfg = self._config.setdefault("database", {})

        # Under pytest/local runs, redirect legacy service names only when the
        # caller explicitly selected that host. No database fallback is added.
        if "PYTEST_CURRENT_TEST" in os.environ or "pytest" in os.environ.get("_", ""):
            if db_cfg.get("host") in ("postgres-prod", "toji-postgres"):
                db_cfg["host"] = "localhost"
            db_cfg["dbname"] = "toji_v1"
            db_cfg["user"] = "postgres"
        else:
            db_cfg.setdefault("host", "localhost")
            db_cfg.setdefault("port", 5432)
            db_cfg["dbname"] = db_cfg.get("database", db_cfg.get("dbname", "toji_v1"))
            db_cfg["user"] = db_cfg.get("username", db_cfg.get("user", "postgres"))

        self._config.setdefault("environment", "PRODUCTION")
        self._config.setdefault("log_level", "INFO")
        return self._config
