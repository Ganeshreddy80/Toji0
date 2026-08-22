"""Configuration manager implementation.

``ConfigurationManager`` reads environment variables with the
``TOJI_`` prefix and maps them to dot-separated config keys.

Mapping convention::

    TOJI_DATABASE_HOST → database.host
    TOJI_APP_ENV       → app.env
"""

from __future__ import annotations

import logging
import os
from typing import Any

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.errors import ConfigurationError, MissingConfigError
from toji_platform.core.types import Profile

logger = logging.getLogger(__name__)

_ENV_PREFIX = "TOJI_"


class ConfigurationManager(IConfigProvider):
    """Environment-driven config with profile support.

    Args:
        overrides: Optional key-value pairs that take precedence
            over environment variables.
    """

    def __init__(
        self,
        overrides: dict[str, Any] | None = None,
    ) -> None:
        self._store: dict[str, Any] = {}
        self._load_from_env()
        if overrides:
            self._store.update(overrides)
        self._profile = self._resolve_profile()

    # ── IConfigProvider ────────────────────────────────────────────────

    @property
    def profile(self) -> Profile:
        return self._profile

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def get_required(self, key: str) -> Any:
        if key not in self._store:
            raise MissingConfigError(key)
        return self._store[key]

    def get_section(self, prefix: str) -> dict[str, Any]:
        dot_prefix = f"{prefix}."
        return {
            k: v
            for k, v in self._store.items()
            if k.startswith(dot_prefix) or k == prefix
        }

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        logger.debug("Config override: %s", key)

    def validate(self, required_keys: list[str]) -> None:
        missing = [k for k in required_keys if k not in self._store]
        if missing:
            raise ConfigurationError(
                f"Missing required configuration keys: {', '.join(missing)}"
            )

    def all(self) -> dict[str, Any]:
        return dict(self._store)

    # ── Internals ──────────────────────────────────────────────────────

    def _load_from_env(self) -> None:
        """Scan environment for ``TOJI_*`` variables and map to
        dot-separated keys.

        ``TOJI_DATABASE_HOST`` → ``database.host``
        """
        for env_key, value in os.environ.items():
            if env_key.startswith(_ENV_PREFIX):
                config_key = (
                    env_key[len(_ENV_PREFIX):]
                    .lower()
                    .replace("_", ".")
                )
                self._store[config_key] = value
        logger.debug(
            "Loaded %d config keys from environment", len(self._store)
        )

    def _resolve_profile(self) -> Profile:
        """Determine the active profile from ``app.env`` or default."""
        raw = self._store.get("app.env", "development")
        try:
            return Profile(str(raw).lower())
        except ValueError:
            logger.warning(
                "Unknown profile '%s', defaulting to DEVELOPMENT", raw
            )
            return Profile.DEVELOPMENT
