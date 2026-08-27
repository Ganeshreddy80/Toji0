"""Active schema persistence — schema manifest and migration management.

Public API
----------
- ``SchemaManifest``: discovers and validates migration files
- ``MigrationEntry``: represents a single versioned migration
- ``SCHEMA_NAME``: canonical schema name (``toji_active``)
- ``REQUIRED_TABLES``: authoritative tuple of required table names
"""

from toji_platform.persistence.schema.manifest import (
    COMPONENT,
    REQUIRED_TABLES,
    SCHEMA_NAME,
    MigrationEntry,
    SchemaManifest,
)

__all__ = [
    "SchemaManifest",
    "MigrationEntry",
    "SCHEMA_NAME",
    "REQUIRED_TABLES",
    "COMPONENT",
]
