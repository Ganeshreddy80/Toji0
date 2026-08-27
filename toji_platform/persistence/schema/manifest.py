"""Active schema manifest — version tracking and migration integrity.

Provides SchemaManifest and MigrationEntry for deterministic, checksummed
schema version management.  This module does NOT execute SQL against any
database; it is a pure-Python contract over the migration files on disk.

Migration ownership: DATA team — CTO approval required for changes.
Schema compatibility: toji_active schema only — no cross-schema references
to research-platform tables.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# ── Constants ────────────────────────────────────────────────────────────────

SCHEMA_NAME: str = "toji_active"
COMPONENT: str = "active_authority"

REQUIRED_TABLES: tuple[str, ...] = (
    "schema_version",
    "execution_requests",
    "order_intents",
    "routing_decisions",
    "orders",
    "fills",
    "execution_results",
    "execution_metrics",
    "execution_journal",
    "audit_records",
    "oms_state",
    "positions",
    "position_updates",
    "portfolio_snapshots",
    "ledger_entries",
    "outbox_messages",
)

VERSIONS_DIR: Path = Path(__file__).resolve().parent / "versions"

# Patterns that must NEVER appear in migration SQL
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"password\s*=", re.IGNORECASE),
    re.compile(r"PASSWORD\s+['\"]", re.IGNORECASE),
    re.compile(r"aws_access_key_id", re.IGNORECASE),
    re.compile(r"aws_secret_access_key", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),
    re.compile(r"DATABASE_URL\s*=", re.IGNORECASE),
    re.compile(r"postgres://[^\s]+:[^\s]+@", re.IGNORECASE),
    re.compile(r"postgresql://[^\s]+:[^\s]+@", re.IGNORECASE),
    re.compile(r"secret_key\s*=", re.IGNORECASE),
    re.compile(r"api_key\s*=", re.IGNORECASE),
)

# Research-platform table names that must NOT appear in active migrations
_RESEARCH_TABLE_NAMES: tuple[str, ...] = (
    "trade_ledger",
    "trade_journals",
    "daily_journals",
    "trade_statistics",
    "portfolios",
    "analytics",
    "strategies",
    "experiments",
    "monitoring_status",
    "monitoring_alerts",
    "monitoring_metrics",
    "reports",
    "configurations",
    "jobs",
)


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MigrationEntry:
    """A single versioned migration."""

    version: str
    name: str
    sql_path: Path
    checksum: str
    component: str = COMPONENT

    @property
    def sql_text(self) -> str:
        """Return raw SQL text of this migration."""
        return self.sql_path.read_text(encoding="utf-8")


# ── Manifest ─────────────────────────────────────────────────────────────────


@dataclass
class SchemaManifest:
    """Discovers, validates, and provides access to migration files.

    Migrations are loaded from the ``versions/`` directory adjacent to this
    module.  Each file must follow the naming convention::

        NNNN_<descriptive_name>.sql

    The manifest computes a deterministic SHA-256 checksum per file and
    enforces invariants (no secrets, no research-table references,
    no ``create_all()`` usage).
    """

    _entries: list[MigrationEntry] = field(default_factory=list, init=False)
    _loaded: bool = field(default=False, init=False)

    # ── public API ───────────────────────────────────────────────────────

    @property
    def schema_name(self) -> str:
        return SCHEMA_NAME

    @property
    def component(self) -> str:
        return COMPONENT

    @property
    def entries(self) -> Sequence[MigrationEntry]:
        self._ensure_loaded()
        return tuple(self._entries)

    def get_version(self, version: str) -> MigrationEntry | None:
        """Look up a migration by version string."""
        self._ensure_loaded()
        for entry in self._entries:
            if entry.version == version:
                return entry
        return None

    def required_tables(self) -> tuple[str, ...]:
        """Return the authoritative list of required tables."""
        return REQUIRED_TABLES

    # ── validation helpers ───────────────────────────────────────────────

    def validate_no_secrets(self) -> list[str]:
        """Return list of violations if secrets are detected."""
        violations: list[str] = []
        for entry in self.entries:
            sql = entry.sql_text
            for pat in _SECRET_PATTERNS:
                matches = pat.findall(sql)
                if matches:
                    violations.append(
                        f"{entry.version}: secret pattern '{pat.pattern}' matched"
                    )
        return violations

    def validate_no_research_tables(self) -> list[str]:
        """Return violations if migration references research tables."""
        violations: list[str] = []
        for entry in self.entries:
            sql = entry.sql_text
            for table_name in _RESEARCH_TABLE_NAMES:
                # Match qualified (public.<table>) or bare CREATE/ALTER/DROP on research tables
                patterns = [
                    rf"(?:CREATE|ALTER|DROP)\s+TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(?:public\.)?{re.escape(table_name)}\b",
                    rf"INSERT\s+INTO\s+(?:public\.)?{re.escape(table_name)}\b",
                    rf"UPDATE\s+(?:public\.)?{re.escape(table_name)}\b",
                    rf"DELETE\s+FROM\s+(?:public\.)?{re.escape(table_name)}\b",
                    rf"TRUNCATE\s+(?:public\.)?{re.escape(table_name)}\b",
                ]
                for pat_str in patterns:
                    if re.search(pat_str, sql, re.IGNORECASE):
                        violations.append(
                            f"{entry.version}: modifies research table '{table_name}'"
                        )
        return violations

    def validate_no_create_all(self) -> list[str]:
        """Return violations if create_all() is used."""
        violations: list[str] = []
        for entry in self.entries:
            sql = entry.sql_text
            if "create_all" in sql.lower():
                violations.append(
                    f"{entry.version}: contains 'create_all' reference"
                )
        return violations

    def validate_required_tables(self) -> list[str]:
        """Return list of missing required tables."""
        missing: list[str] = []
        for entry in self.entries:
            sql = entry.sql_text.lower()
            for table in REQUIRED_TABLES:
                qualified = f"toji_active.{table}"
                if qualified not in sql:
                    missing.append(f"{entry.version}: missing table '{table}'")
        return missing

    # ── internals ────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._load_migrations()
        self._loaded = True

    def _load_migrations(self) -> None:
        if not VERSIONS_DIR.is_dir():
            return
        sql_files = sorted(VERSIONS_DIR.glob("*.sql"))
        for sql_path in sql_files:
            version, name = self._parse_filename(sql_path.name)
            checksum = self._compute_checksum(sql_path)
            self._entries.append(
                MigrationEntry(
                    version=version,
                    name=name,
                    sql_path=sql_path,
                    checksum=checksum,
                )
            )

    @staticmethod
    def _parse_filename(filename: str) -> tuple[str, str]:
        """Extract version and name from ``NNNN_name.sql``."""
        stem = filename.removesuffix(".sql")
        parts = stem.split("_", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid migration filename: {filename}")
        return parts[0], parts[1]

    @staticmethod
    def _compute_checksum(path: Path) -> str:
        """Deterministic SHA-256 hex digest of the file contents."""
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
