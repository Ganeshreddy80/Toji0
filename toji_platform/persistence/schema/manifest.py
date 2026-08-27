"""Active schema manifest — version tracking and migration integrity.

Checksum Policy
---------------
The ``SchemaManifest`` computes a deterministic SHA-256 of each migration
file on disk.  The ``MigrationRunner`` is the checksum authority:

  1. **First application**: apply SQL, then insert schema_version row with the
     actual checksum (replacing the ``__CHECKSUM_SELF__`` sentinel).
  2. **Repeat — same checksum**: version row exists with matching checksum →
     log and skip (idempotent re-run).
  3. **Repeat — different checksum**: version row exists with a DIFFERENT
     checksum → raise ``ChecksumMismatchError`` (fail closed).
  4. **Duplicate version (different name)**: unique index on ``version`` in
     schema_version will raise ``IntegrityError`` during INSERT → propagated
     as ``DuplicateVersionError``.

This module does NOT execute SQL against any database; it is pure-Python
over the migration files on disk.

Migration ownership: DATA team — CTO approval required for changes.
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
CHECKSUM_SENTINEL: str = "__CHECKSUM_SELF__"

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

# Patterns that must NEVER appear in migration SQL (as actual values)
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"password\s*=\s*['\"]", re.IGNORECASE),
    re.compile(r"aws_access_key_id\s*=", re.IGNORECASE),
    re.compile(r"aws_secret_access_key\s*=", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"DATABASE_URL\s*=", re.IGNORECASE),
    re.compile(r"(?:postgres|postgresql)://[^\s]+:[^\s]+@", re.IGNORECASE),
    re.compile(r"secret_key\s*=\s*['\"]", re.IGNORECASE),
    re.compile(r"api_key\s*=\s*['\"]", re.IGNORECASE),
)

# Research-platform table names that must NOT be touched by active migrations
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


# ── Exceptions ───────────────────────────────────────────────────────────────


class MigrationError(Exception):
    """Base class for migration errors."""


class ChecksumMismatchError(MigrationError):
    """Raised when the on-disk migration checksum differs from the applied one."""

    def __init__(self, version: str, expected: str, found: str) -> None:
        super().__init__(
            f"Migration {version} checksum mismatch: "
            f"applied={found!r} on-disk={expected!r}. "
            "Do not modify applied migrations."
        )
        self.version = version
        self.expected = expected
        self.found = found


class DuplicateVersionError(MigrationError):
    """Raised when two migration files share the same version number."""

    def __init__(self, version: str) -> None:
        super().__init__(f"Duplicate migration version: {version!r}")
        self.version = version


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MigrationEntry:
    """A single versioned migration discovered on disk."""

    version: str
    name: str
    sql_path: Path
    checksum: str
    component: str = COMPONENT

    @property
    def sql_text(self) -> str:
        """Return raw SQL text of this migration."""
        return self.sql_path.read_text(encoding="utf-8")

    def sql_for_apply(self) -> str:
        """Return SQL with the ``__CHECKSUM_SELF__`` sentinel replaced by the
        actual checksum so the schema_version INSERT records correctly."""
        return self.sql_text.replace(CHECKSUM_SENTINEL, self.checksum)


# ── Manifest ─────────────────────────────────────────────────────────────────


@dataclass
class SchemaManifest:
    """Discovers, validates, and provides access to versioned migration files.

    Migrations are loaded from the ``versions/`` directory adjacent to this
    module.  Each file must follow the naming convention::

        NNNN_<descriptive_name>.sql

    The manifest computes a deterministic SHA-256 checksum per file and
    enforces invariants (no secrets, no research-table references,
    no ``create_all()`` usage, no duplicate versions).
    """

    _entries: list[MigrationEntry] = field(default_factory=list, init=False)
    _loaded: bool = field(default=False, init=False)

    # ── public API ────────────────────────────────────────────────────────

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
        """Look up a migration entry by version string (e.g. ``'0001'``)."""
        self._ensure_loaded()
        for entry in self._entries:
            if entry.version == version:
                return entry
        return None

    def required_tables(self) -> tuple[str, ...]:
        """Return the authoritative list of required table names."""
        return REQUIRED_TABLES

    # ── validation helpers ────────────────────────────────────────────────

    def validate_no_secrets(self) -> list[str]:
        """Return a list of violations if secret patterns are detected."""
        violations: list[str] = []
        for entry in self.entries:
            # Strip SQL line comments before checking to avoid false positives
            # on comment text that describes what we're looking for
            sql = _strip_sql_comments(entry.sql_text)
            for pat in _SECRET_PATTERNS:
                if pat.search(sql):
                    violations.append(
                        f"{entry.version}: secret pattern matched: {pat.pattern!r}"
                    )
        return violations

    def validate_no_research_tables(self) -> list[str]:
        """Return violations if migration references research-platform tables."""
        violations: list[str] = []
        for entry in self.entries:
            sql = entry.sql_text
            for table_name in _RESEARCH_TABLE_NAMES:
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
                            f"{entry.version}: modifies research table {table_name!r}"
                        )
        return violations

    def validate_no_create_all(self) -> list[str]:
        """Return violations if ``create_all()`` is used anywhere."""
        violations: list[str] = []
        for entry in self.entries:
            if "create_all" in entry.sql_text.lower():
                violations.append(f"{entry.version}: contains 'create_all' reference")
        return violations

    def validate_required_tables(self) -> list[str]:
        """Return list of required tables missing from any migration."""
        missing: list[str] = []
        all_sql = "\n".join(e.sql_text.lower() for e in self.entries)
        for table in REQUIRED_TABLES:
            if f"toji_active.{table}" not in all_sql:
                missing.append(f"Missing table: toji_active.{table}")
        return missing

    def validate_no_placeholder_checksum(self) -> list[str]:
        """Return violations if migration SQL still has the old placeholder."""
        violations: list[str] = []
        for entry in self.entries:
            if "__CHECKSUM_PLACEHOLDER__" in entry.sql_text:
                violations.append(
                    f"{entry.version}: contains forbidden '__CHECKSUM_PLACEHOLDER__' sentinel"
                )
        return violations

    def validate_no_duplicate_versions(self) -> list[str]:
        """Return violations if multiple files share the same version number."""
        seen: dict[str, str] = {}
        violations: list[str] = []
        for entry in self.entries:
            if entry.version in seen:
                violations.append(
                    f"Duplicate version {entry.version!r}: "
                    f"{seen[entry.version]} and {entry.sql_path.name}"
                )
            else:
                seen[entry.version] = entry.sql_path.name
        return violations

    # ── internals ─────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._load_migrations()
        self._loaded = True

    def _load_migrations(self) -> None:
        if not VERSIONS_DIR.is_dir():
            return
        sql_files = sorted(VERSIONS_DIR.glob("*.sql"))
        seen_versions: set[str] = set()
        for sql_path in sql_files:
            version, name = self._parse_filename(sql_path.name)
            if version in seen_versions:
                raise DuplicateVersionError(version)
            seen_versions.add(version)
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
            raise ValueError(f"Invalid migration filename: {filename!r}")
        return parts[0], parts[1]

    @staticmethod
    def _compute_checksum(path: Path) -> str:
        """Deterministic SHA-256 hex digest of file bytes."""
        return hashlib.sha256(path.read_bytes()).hexdigest()


# ── MigrationRunner ───────────────────────────────────────────────────────────


class MigrationRunner:
    """Applies migrations against a live database connection.

    Parameters
    ----------
    conn:
        A ``psycopg2`` (or compatible) connection object.  The runner
        manages its own transaction boundaries.

    Usage::

        manifest = SchemaManifest()
        with psycopg2.connect(...) as conn:
            runner = MigrationRunner(conn)
            runner.run(manifest)

    Repeat / mismatch policy (enforced here, not only via DB constraints):
      - Already applied, same checksum  → skip (idempotent).
      - Already applied, different checksum → raise ChecksumMismatchError.
      - Version conflict at INSERT → DuplicateVersionError.
    """

    def __init__(self, conn: object) -> None:
        self._conn = conn

    def run(self, manifest: SchemaManifest) -> None:
        """Apply all pending migrations from *manifest*."""
        for entry in manifest.entries:
            self._apply_one(entry)

    def _apply_one(self, entry: MigrationEntry) -> None:
        import psycopg2  # type: ignore[import-untyped]
        import psycopg2.extras  # type: ignore[import-untyped]

        conn = self._conn
        row = None
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Check whether the schema_version table exists yet (first apply)
                cur.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='toji_active' AND table_name='schema_version'"
                )
                schema_exists = cur.fetchone() is not None
                if schema_exists:
                    cur.execute(
                        "SELECT checksum FROM toji_active.schema_version WHERE version = %s",
                        (entry.version,),
                    )
                    row = cur.fetchone()
        except Exception:
            conn.rollback()
            raise

        if row is not None:
            applied_checksum = row["checksum"]
            if applied_checksum == entry.checksum:
                # Already applied with same content — skip
                return
            else:
                raise ChecksumMismatchError(
                    version=entry.version,
                    expected=entry.checksum,
                    found=applied_checksum,
                )

        # Not yet applied — apply the migration
        sql = entry.sql_for_apply()
        with conn.cursor() as cur:
            try:
                cur.execute(sql)
            except Exception:
                conn.rollback()
                raise
        conn.commit()

    def check_applied(self, manifest: SchemaManifest) -> dict[str, str | None]:
        """Return mapping of version → applied checksum (or None if not applied)."""
        import psycopg2.extras  # type: ignore[import-untyped]
        conn = self._conn
        result: dict[str, str | None] = {}
        for entry in manifest.entries:
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema='toji_active' AND table_name='schema_version'"
                    )
                    if cur.fetchone() is None:
                        result[entry.version] = None
                        continue
                    cur.execute(
                        "SELECT checksum FROM toji_active.schema_version WHERE version = %s",
                        (entry.version,),
                    )
                    row = cur.fetchone()
                    result[entry.version] = row["checksum"] if row else None
            except Exception:
                conn.rollback()
                result[entry.version] = None
        return result


# ── Utilities ─────────────────────────────────────────────────────────────────


def _strip_sql_comments(sql: str) -> str:
    """Remove SQL line comments (``-- ...``) from SQL text."""
    return "\n".join(
        line for line in sql.splitlines()
        if not line.strip().startswith("--")
    )
