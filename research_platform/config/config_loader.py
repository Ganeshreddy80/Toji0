"""Configuration profile, environment, and secure database secret loading."""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, Any, Optional

from research_platform.config.profiles import ConfigProfileLoader
from research_platform.config.environment import EnvironmentLoader
from research_platform.config.secrets import SecretsManager
from research_platform.config.config_validator import ConfigValidator
from research_platform.config.aws_database import AWSDatabaseSecretProvider, database_config_from_url

logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None


class ConfigLoader:
    """Orchestrates profiles, files, secure database configuration, and overrides."""

    def __init__(
        self,
        default_profile: str = "PAPER",
        *,
        require_secure_database: bool = False,
        secret_provider: Optional[AWSDatabaseSecretProvider] = None,
    ) -> None:
        self.default_profile = default_profile
        self.require_secure_database = require_secure_database
        self.secret_provider = secret_provider or AWSDatabaseSecretProvider()

    def merge_dicts(self, dict_a: Dict[str, Any], dict_b: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge dict_b overrides into dict_a."""
        merged = dict(dict_a)
        for key, val in dict_b.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
                merged[key] = self.merge_dicts(merged[key], val)
            else:
                merged[key] = val
        return merged

    def load_configuration(
        self,
        yaml_path: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Merge profile, YAML, secure DB source, environment, and manual overrides."""
        profile_name = os.environ.get("TOJI_PROFILE", self.default_profile)
        config = self.merge_dicts({}, ConfigProfileLoader.get_profile_defaults(profile_name))

        if yaml_path and os.path.exists(yaml_path):
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    if yaml:
                        yaml_data = yaml.safe_load(f)
                    else:
                        yaml_data = json.load(f)
                if isinstance(yaml_data, dict):
                    config = self.merge_dicts(config, yaml_data)
            except Exception as exc:
                logger.error("Failed to parse configuration file (error_type=%s).", type(exc).__name__)

        env_overrides = EnvironmentLoader.load_from_env()
        config = self.merge_dicts(config, env_overrides)
        mode = str(config.get("runtime", {}).get("mode", profile_name)).upper()
        database_url = os.environ.get("DATABASE_URL")
        env_database = env_overrides.get("database", {})
        explicit_database_env = all(
            env_database.get(field) not in (None, "")
            for field in ("host", "port", "database", "username", "password")
        )
        if self.require_secure_database and mode in {"PAPER", "PROD"} and not database_url and not explicit_database_env:
            if not self.secret_provider.configured:
                raise RuntimeError(
                    "Secure database configuration is required for PAPER/PROD; "
                    "set DATABASE_URL or TOJI_DATABASE_SECRET_NAME"
                )
            secret_database = self.secret_provider.load_database_config()
            if not secret_database:
                raise RuntimeError("Secure database configuration was not returned by AWS Secrets Manager")
            config["database"] = self.merge_dicts(config.get("database", {}), secret_database)
            # Environment values are explicit operator overrides and remain
            # authoritative over non-sensitive secret fields when supplied.
            config = self.merge_dicts(config, env_overrides)
        elif self.secret_provider.configured and not database_url:
            secret_database = self.secret_provider.load_database_config()
            if secret_database:
                config["database"] = self.merge_dicts(config.get("database", {}), secret_database)
                config = self.merge_dicts(config, env_overrides)

        if overrides:
            config = self.merge_dicts(config, overrides)

        # DATABASE_URL is an explicit connection-string override and therefore
        # wins over profile, secret, environment, and manual database fields.
        if database_url:
            try:
                config["database"] = self.merge_dicts(
                    config.get("database", {}), database_config_from_url(database_url)
                )
            except ValueError:
                raise RuntimeError("DATABASE_URL must be a valid PostgreSQL URL") from None

        config = SecretsManager.resolve_secrets(config)
        errors = ConfigValidator.validate(config)
        if errors:
            logger.warning("Configuration validation failed (error_count=%d).", len(errors))
        return config
