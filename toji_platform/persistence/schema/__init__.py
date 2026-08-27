"""Public API for toji_platform.persistence.schema."""

from toji_platform.persistence.schema.manifest import (
    CHECKSUM_SENTINEL,
    COMPONENT,
    REQUIRED_TABLES,
    SCHEMA_NAME,
    VERSIONS_DIR,
    ChecksumMismatchError,
    DuplicateVersionError,
    MigrationEntry,
    MigrationError,
    MigrationRunner,
    SchemaManifest,
)

__all__ = [
    # Constants
    "SCHEMA_NAME",
    "COMPONENT",
    "CHECKSUM_SENTINEL",
    "REQUIRED_TABLES",
    "VERSIONS_DIR",
    # Exceptions
    "MigrationError",
    "ChecksumMismatchError",
    "DuplicateVersionError",
    # Data classes
    "MigrationEntry",
    # Classes
    "SchemaManifest",
    "MigrationRunner",
]
