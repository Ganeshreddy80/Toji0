"""R51 Configuration loading engine merging profile profiles and env parameters.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, Any, Optional

from research_platform.config.profiles import ConfigProfileLoader
from research_platform.config.environment import EnvironmentLoader
from research_platform.config.secrets import SecretsManager
from research_platform.config.config_validator import ConfigValidator

logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None


class ConfigLoader:
    """Orchestrates configuration profile retrieval, YAML parses, and dictionary mergers."""

    def __init__(self, default_profile: str = "PAPER") -> None:
        self.default_profile = default_profile

    def merge_dicts(self, dict_a: Dict[str, Any], dict_b: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge dict_b overrides into dict_a."""
        merged = dict(dict_a)
        for key, val in dict_b.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
                merged[key] = self.merge_dicts(merged[key], val)
            else:
                merged[key] = val
        return merged

    def load_configuration(self, yaml_path: Optional[str] = None, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Merges: profile defaults -> YAML file -> Environment overrides -> dynamic parameters."""
        # 1. Base default profile dictionary
        profile_name = self.default_profile
        
        # Pull profile from env if specified
        if "TOJI_PROFILE" in os.environ:
            profile_name = os.environ["TOJI_PROFILE"]
            
        config = ConfigProfileLoader.get_profile_defaults(profile_name)

        # 2. Merge YAML if specified and exists
        if yaml_path:
            if os.path.exists(yaml_path):
                try:
                    with open(yaml_path, "r", encoding="utf-8") as f:
                        if yaml:
                            yaml_data = yaml.safe_load(f)
                            if isinstance(yaml_data, dict):
                                config = self.merge_dicts(config, yaml_data)
                        else:
                            # Fallback parse as json
                            json_data = json.load(f)
                            if isinstance(json_data, dict):
                                config = self.merge_dicts(config, json_data)
                except Exception as e:
                    logger.error("Failed to parse configuration file at %s: %s", yaml_path, e)

        # 3. Merge Environment variable overrides
        env_overrides = EnvironmentLoader.load_from_env()
        config = self.merge_dicts(config, env_overrides)

        # 4. Merge manual overrides (e.g. from runtime updates)
        if overrides:
            config = self.merge_dicts(config, overrides)

        # 5. Mask/Resolve base64 credentials secrets
        config = SecretsManager.resolve_secrets(config)

        # 6. Verify consistency
        errors = ConfigValidator.validate(config)
        if errors:
            logger.warning("Configuration validation failed with errors: %s", errors)
            # We raise or log, but continue to let components fallback gracefully

        return config
