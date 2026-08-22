"""R51 JSON Schema generator.
"""

from __future__ import annotations

from typing import Dict, Any
from research_platform.config.models import CentralConfig


class ConfigSchemaGenerator:
    """Generates JSON Schema structural maps of the configuration models."""

    @staticmethod
    def get_json_schema() -> Dict[str, Any]:
        """Generate schema structure dictionary."""
        return CentralConfig.model_json_schema()
