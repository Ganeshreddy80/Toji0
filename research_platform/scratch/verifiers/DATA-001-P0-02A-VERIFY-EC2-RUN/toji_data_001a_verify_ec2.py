#!/usr/bin/env python3
"""DATA-001-P0-02A-VERIFY-EC2-RUN.

Read-only verifier for the committed TOJI database/configuration wiring.

The verifier intentionally does not call DatabaseLifecycleManager.connect(),
which invokes TOJI's automatic schema creation. It initializes the committed
DatabaseConnection directly, then uses the committed ConfigRepository,
PostgresConfigurationRepository, DatabaseSessionManager, and
TransactionManager against already-existing tables. This keeps the check
read-only with respect to schema while allowing temporary data-row writes that
are always targeted and removed in finally blocks.

The script prints only sanitized JSON/Markdown evidence. It never prints a
secret selector value, secret payload, password, connection URL, account ID,
role ARN, hostname, or exception text.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import quote

TARGET_COMMIT_INPUT = "ae7897cd175a8f8964f6c2475933783f9f0042d"
TARGET_COMMIT_FULL = "ae7897cd175a8f8964f6c2475933783f9f0042d8"
TEST_KEY_PREFIX = "__toji_data_001a_verify__"
APPROVED_TLS_MODES = {"verify-full", "verify-ca"}


class VerificationError(RuntimeError):
    pass


class SecretSafeCapture(logging.Handler):
    """Capture log messages for scanning without emitting them to stdout."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.messages.append(record.getMessage())
        except Exception:
            self.messages.append(f"<log-format-error:{type(record).__name__}>")


@contextmanager
def capture_logs() -> Iterator[SecretSafeCapture]:
    handler = SecretSafeCapture()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield handler
    finally:
        root.removeHandler(handler)


def env_present(*names: str) -> bool:
    return any(bool(os.environ.get(name)) for name in names)


def choose_selector() -> tuple[str | None, str]:
    """Return a selector from supported non-secret environment variables."""
    for name in (
        "TOJI_DATABASE_SECRET_ARN",
        "TOJI_DATABASE_SECRET_NAME",
        "AWS_DATABASE_SECRET_NAME",
    ):
        value = os.environ.get(name)
        if value:
            return value, name
    return None, "UNSET"


def redact_text(value: Any, secret_values: list[str]) -> str:
    text = str(value)
    replacements = sorted((v for v in secret_values if v), key=len, reverse=True)
    for secret in replacements:
        text = text.replace(secret, "<redacted>")
        text = text.replace(quote(secret, safe=""), "<redacted>")
    # Prevent accidental URL/password disclosure even if a provider exception
    # formats a URL differently from the known normalized password.
    text = re.sub(r"(postgres(?:ql)?://[^:]*:)[^@\s]+(@)", r"\1<redacted>\2", text, flags=re.I)
    return text


def safe_exception(exc: BaseException, secret_values: list[str]) -> dict[str, str]:
    """Return error metadata without emitting raw SDK/database text."""
    return {
        "type": type(exc).__name__,
        "message": "verifier step failed; details withheld",
    }


def recursive_contains(value: Any, needle: str) -> bool:
    if not needle:
        return False
    if isinstance(value, Mapping):
        return any(recursive_contains(k, needle) or recursive_contains(v, needle) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(recursive_contains(item, needle) for item in value)
    return needle in str(value)


def git_identity(repo: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=repo, text=True, stderr=subprocess.STDOUT).strip()

    branch = run("branch", "--show-current")
    commit = run("rev-parse", "HEAD")
    porcelain = run("status", "--porcelain")
    remotes = run("remote", "-v")
    canonical_remote = "Ganeshreddy80/Toji0" in remotes.replace(".git", "")
    return {
        "repository_present": (repo / ".git").exists(),
        "canonical_remote": canonical_remote,
        "branch_present": bool(branch),
        "branch": branch if branch else "<detached>",
        "commit_matches_requested": commit.startswith(TARGET_COMMIT_INPUT),
        "resolved_commit_exact": commit == TARGET_COMMIT_FULL,
        "commit_sha": commit,
        "working_tree_clean": porcelain == "",
        "requested_commit_token": TARGET_COMMIT_INPUT,
        "requested_token_length": len(TARGET_COMMIT_INPUT),
        "target_commit_full_sha": TARGET_COMMIT_FULL,
    }


def import_application(repo: Path) -> None:
    repo_string = str(repo)
    if repo_string not in sys.path:
        sys.path.insert(0, repo_string)


def resolve_application_config(repo: Path, secret_values: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Exercise the committed ConfigurationBootloader, not a duplicate parser."""
    import_application(repo)
    from research_platform.platform.configuration_boot import ConfigurationBootloader

    if os.environ.get("DATABASE_URL"):
        raise VerificationError("DATABASE_URL override is set; secure secret path not proven")
    selector, selector_source = choose_selector()
    if not selector:
        raise VerificationError("no configured database secret selector")

    # The committed provider supports TOJI_DATABASE_SECRET_NAME and the AWS
    # alias. If the verifier exposes an ARN variable, use the same ARN as the
    # provider's SecretId without revealing it or changing source code.
    original_name = os.environ.get("TOJI_DATABASE_SECRET_NAME")
    original_profile = os.environ.get("TOJI_PROFILE")
    os.environ["TOJI_DATABASE_SECRET_NAME"] = selector
    os.environ["TOJI_PROFILE"] = "PAPER"

    try:
        with capture_logs() as logs:
            config = ConfigurationBootloader().load_configuration()
        database = dict(config.get("database", {}))
        password = str(database.get("password", ""))
        if password:
            secret_values.append(password)
        secret_values.extend(
            [str(database.get("username", "")), str(database.get("raw_url", ""))]
        )
        log_text = "\n".join(logs.messages)
    finally:
        if original_name is None:
            os.environ.pop("TOJI_DATABASE_SECRET_NAME", None)
        else:
            os.environ["TOJI_DATABASE_SECRET_NAME"] = original_name
        if original_profile is None:
            os.environ.pop("TOJI_PROFILE", None)
        else:
            os.environ["TOJI_PROFILE"] = original_profile
    application_result = {
        "configuration_bootloader_pass": bool(database),
        "database_keys_present": all(
            database.get(key) not in (None, "") for key in ("host", "port", "database", "username", "password")
        ),
        "runtime_mode": str(config.get("runtime", {}).get("mode", "")),
        "selector_source": selector_source,
        "runtime_password_present_allowed": bool(password),
        "secret_value_in_configuration_logs": any(value and value in log_text for value in secret_values),
    }
    return config, application_result


def get_secret_and_iam(secret_values: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    import boto3

    selector, selector_source = choose_selector()
    if not selector:
        raise VerificationError("no configured database secret selector")

    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials is None:
        raise VerificationError("AWS credential provider returned no credentials")

    try:
        identity = session.client("sts").get_caller_identity()
    except Exception as exc:
        raise VerificationError(f"STS identity call failed: {type(exc).__name__}") from None
    iam_result = {
        "credential_provider_available": True,
        "sts_identity_pass": bool(identity.get("Account") and identity.get("Arn")),
        "identity_type": "assumed-role" if ":assumed-role/" in str(identity.get("Arn", "")) else "other",
    }

    from research_platform.config.aws_database import AWSDatabaseSecretProvider

    provider = AWSDatabaseSecretProvider(secret_name=selector)
    try:
        with capture_logs() as logs:
            database = provider.load_database_config()
    except Exception as exc:
        raise VerificationError(f"Secrets Manager retrieval failed: {type(exc).__name__}") from None
    if not database:
        raise VerificationError("Secrets Manager returned no database configuration")

    password = str(database.get("password", ""))
    secret_values.append(password)
    secret_values.extend(
        [str(database.get("username", "")), str(database.get("raw_url", ""))]
    )
    log_text = "\n".join(logs.messages)
    secret_result = {
        "selector_present": True,
        "selector_source": selector_source,
        "get_secret_value_pass": True,
        "database_fields_present": all(
            database.get(key) not in (None, "") for key in ("host", "port", "database", "username", "password")
        ),
        "secret_value_in_provider_logs": any(value and value in log_text for value in secret_values),
    }
    return dict(database), {"iam": iam_result, "secret": secret_result}


def build_db_service(config: Mapping[str, Any]):
    """Initialize the real connection without invoking schema auto-creation."""
    from research_platform.persistence.postgres.connection import DatabaseConnection
    from research_platform.platform.database_boot import DatabaseLifecycleManager

    db_config = dict(config["database"])
    db_config["_runtime_mode"] = config.get("runtime", {}).get("mode", "PAPER")
    db_connection = DatabaseConnection(db_config)
    db_connection.initialize()
    if db_connection.is_fallback:
        raise VerificationError("TOJI selected SQLite/in-memory fallback")
    service = DatabaseLifecycleManager(db_config)
    # DatabaseLifecycleManager.connect() automatically calls create_all(); the
    # verifier must not modify schema. Reuse its concrete service wrapper after
    # initializing the committed DatabaseConnection directly.
    service._connection = db_connection
    service.connected = True
    return service, db_connection


def tls_policy_evidence(backend: str, sslmode: str | None, server_ssl_active: bool) -> dict[str, Any]:
    """Evaluate the approved TLS certification policy without contacting a server."""
    normalized = sslmode or "UNSET"
    return {
        "engine_backend": backend,
        "engine_is_postgresql": backend == "postgresql",
        "sslmode": normalized,
        "sslmode_policy_pass": normalized in APPROVED_TLS_MODES,
        "server_ssl_active": server_ssl_active,
    }


def tls_evidence(engine: Any) -> dict[str, Any]:
    from sqlalchemy import text

    backend = engine.url.get_backend_name()
    driver = engine.url.drivername
    query = dict(engine.url.query)
    sslmode = query.get("sslmode")
    sslrootcert = query.get("sslrootcert")
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT ssl, version, cipher, bits FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
        ).mappings().first()
    actual_ssl = bool(row and row.get("ssl"))
    policy = tls_policy_evidence(backend, sslmode, actual_ssl)
    certificate_verification = (
        "required" if sslmode in APPROVED_TLS_MODES else
        "not-required" if sslmode == "require" else
        "not-configured"
    )
    return {
        **policy,
        "engine_driver": driver,
        "sslrootcert_configured": bool(sslrootcert),
        "certificate_verification": certificate_verification,
        "server_tls_version_present": bool(row and row.get("version")),
        "server_cipher_present": bool(row and row.get("cipher")),
        "server_cipher_bits": int(row.get("bits") or 0) if row else 0,
    }


def verify_config_persistence_safety(
    config: Mapping[str, Any], secret_password: str, persisted_value: Any = None
) -> dict[str, Any]:
    """Check the actual CentralConfig serialization without writing the secret."""
    from research_platform.config.models import CentralConfig

    central = CentralConfig.model_validate(config)
    payload = central.model_dump()
    db = payload.get("database", {})
    password_present = bool(db.get("password"))
    persisted_secret_present = recursive_contains(persisted_value, secret_password)
    return {
        "central_config_serializable": True,
        "runtime_password_present_allowed": password_present,
        "persisted_central_config_row_checked": persisted_value is not None,
        "persisted_central_config_contains_secret": persisted_secret_present,
        "central_config_secret_safe": not persisted_secret_present,
    }


def run_read_child(repo: Path, key: str, secret_values: list[str]) -> dict[str, Any]:
    script = Path(__file__).resolve()
    command = [sys.executable, str(script), "--repo", str(repo), "--read-key", key]
    completed = subprocess.run(
        command,
        cwd=repo,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    combined = completed.stdout + "\n" + completed.stderr
    leaked = any(value and value in combined for value in secret_values)
    try:
        child = json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception:
        child = {"child_json_parse": False}
    child["child_returncode"] = completed.returncode
    child["child_secret_in_output"] = leaked
    return child


def cleanup_temporary_rows(
    pg_repo: Any, tx_mgr: Any, commit_key: str, rollback_key: str, results: dict[str, Any]
) -> None:
    """Delete only the two UUID-scoped rows created by this verifier."""
    if pg_repo is None or tx_mgr is None:
        return
    try:
        with tx_mgr.transaction():
            removed_commit = pg_repo.delete(commit_key)
            removed_rollback = pg_repo.delete(rollback_key)
        results.setdefault("cleanup", {"attempted": True})
        results["cleanup"]["committed_key_removed"] = bool(removed_commit)
        results["cleanup"]["rollback_key_removed"] = bool(removed_rollback) or results.get("rollback_test", {}).get("rollback_absent_after_abort", False)
    except Exception as exc:
        results.setdefault("cleanup", {"attempted": True})
        results["cleanup"]["error_type"] = type(exc).__name__


def run_verification(repo: Path) -> dict[str, Any]:
    results: dict[str, Any] = {
        "task_id": "DATA-001-P0-02A-VERIFY-EC2-RUN",
        "target_commit": TARGET_COMMIT_FULL,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_modification_attempted": False,
        "trades_placed": False,
        "errors": [],
    }
    secret_values: list[str] = []
    global_log_capture = None
    service = None
    db_connection = None
    pg_repo = None
    tx_mgr = None
    commit_key = f"{TEST_KEY_PREFIX}{uuid.uuid4().hex}"
    rollback_key = f"{TEST_KEY_PREFIX}{uuid.uuid4().hex}"

    results["git"] = git_identity(repo)
    if (
        not results["git"].get("canonical_remote")
        or not results["git"].get("commit_matches_requested")
        or not results["git"].get("resolved_commit_exact")
        or not results["git"].get("working_tree_clean")
    ):
        results["verdict"] = "BLOCKED"
        results["errors"].append("repository identity or clean-worktree gate failed")
        return results

    global_log_capture = SecretSafeCapture()
    logging.getLogger().addHandler(global_log_capture)
    try:
        secret_database, aws = get_secret_and_iam(secret_values)
        results.update(aws)
        config, application = resolve_application_config(repo, secret_values)
        results["application_configuration"] = application
        expected = {key: secret_database.get(key) for key in ("host", "port", "database", "username")}
        resolved = config.get("database", {})
        results["application_matches_secret_target"] = all(resolved.get(key) == value for key, value in expected.items())
        secret_password = str(secret_database.get("password", ""))

        service, db_connection = build_db_service(config)
        engine = db_connection.engine
        results["connection"] = {
            "database_service_connected": bool(service.connected),
            "fallback": bool(db_connection.is_fallback),
            "engine": tls_evidence(engine),
        }
        from research_platform.config.repository import ConfigRepository

        from research_platform.persistence.postgres.session import DatabaseSessionManager
        from research_platform.persistence.postgres.transaction_manager import TransactionManager
        from research_platform.platform.service_registry import ServiceRegistry

        registry = ServiceRegistry()
        registry.clear()
        registry.register_service("Database", service)
        config_repo = ConfigRepository()
        pg_repo = config_repo._get_pg_repo()
        if pg_repo is None:
            raise VerificationError("TOJI ConfigRepository did not resolve a PostgreSQL repository")
        persisted_central = pg_repo.get_parameter("central_config")
        results["config_persistence_safety"] = verify_config_persistence_safety(
            config, secret_password, persisted_central
        )
        session_manager = DatabaseSessionManager(service)
        tx_mgr = TransactionManager(session_manager)
        payload = {"verification": "DATA-001-P0-02A", "created_at": datetime.now(timezone.utc).isoformat()}

        with tx_mgr.transaction() as session:
            pg_repo.save_parameter(commit_key, payload)
            selected = pg_repo.get_parameter(commit_key)
            results["commit_test"] = {
                "begin_insert_select_same_transaction": selected == payload,
                "selected_record_matches": selected == payload,
            }
        committed = pg_repo.get_parameter(commit_key)
        results["commit_test"]["commit_persisted"] = committed == payload
        results["commit_test"]["status"] = "PASS" if results["commit_test"]["commit_persisted"] else "FAIL"

        try:
            with tx_mgr.transaction():
                pg_repo.save_parameter(rollback_key, payload)
                if pg_repo.get_parameter(rollback_key) != payload:
                    raise VerificationError("rollback probe could not read its inserted row")
                raise RuntimeError("intentional rollback sentinel")
        except RuntimeError as exc:
            if str(exc) != "intentional rollback sentinel":
                raise
        after_rollback = pg_repo.get_parameter(rollback_key)
        results["rollback_test"] = {
            "rollback_absent_after_abort": after_rollback is None,
            "status": "PASS" if after_rollback is None else "FAIL",
        }

        results["fresh_process"] = run_read_child(repo, commit_key, secret_values)
        results["fresh_process"]["status"] = (
            "PASS" if results["fresh_process"].get("read_persisted_record")
            and not results["fresh_process"].get("fallback")
            else "FAIL"
        )

        results["cleanup"] = {"attempted": True, "committed_key_removed": False, "rollback_key_removed": False}
    except Exception as exc:
        results["errors"].append(safe_exception(exc, secret_values))
    finally:
        # Remove only the two UUID-scoped temporary configuration rows. No
        # migrations, schema DDL, unrelated keys, or trading rows are touched.
        cleanup_temporary_rows(pg_repo, tx_mgr, commit_key, rollback_key, results)
        if service is not None:
            try:
                service.disconnect()
            except Exception:
                pass
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            ServiceRegistry().clear()
        except Exception:
            pass
        if global_log_capture is not None:
            logging.getLogger().removeHandler(global_log_capture)

    serialized_results = json.dumps(results, default=str)
    logs_text = "\n".join(global_log_capture.messages)
    leaked_in_report = any(value and value in serialized_results for value in secret_values)
    leaked_in_logs = any(value and value in logs_text for value in secret_values)
    results["secret_hygiene"] = {
        "secret_values_in_report": leaked_in_report,
        "secret_values_in_logs_or_errors": leaked_in_logs,
        "output_is_sanitized": not leaked_in_report and not leaked_in_logs,
    }
    results["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    results["verdict"] = determine_verdict(results)
    return results


def determine_verdict(results: Mapping[str, Any]) -> str:
    if results.get("errors"):
        return "BLOCKED"
    git = results.get("git", {})
    if not git.get("canonical_remote") or not git.get("commit_matches_requested") or not git.get("resolved_commit_exact") or not git.get("working_tree_clean", False):
        return "BLOCKED"
    aws = results.get("iam", {})
    secret = results.get("secret", {})
    app = results.get("application_configuration", {})
    conn = results.get("connection", {})
    engine = conn.get("engine", {})
    commit = results.get("commit_test", {})
    rollback = results.get("rollback_test", {})
    fresh = results.get("fresh_process", {})
    cleanup = results.get("cleanup", {})
    safety = results.get("config_persistence_safety", {})
    hygiene = results.get("secret_hygiene", {})
    required = [
        aws.get("credential_provider_available"),
        aws.get("sts_identity_pass"),
        secret.get("get_secret_value_pass"),
        secret.get("database_fields_present"),
        app.get("configuration_bootloader_pass"),
        results.get("application_matches_secret_target"),
        conn.get("database_service_connected"),
        conn.get("fallback") is False,
        engine.get("engine_is_postgresql"),
        engine.get("server_ssl_active"),
        engine.get("sslmode_policy_pass"),
        commit.get("status") == "PASS",
        rollback.get("status") == "PASS",
        fresh.get("status") == "PASS",
        not fresh.get("child_secret_in_output"),
        safety.get("central_config_secret_safe"),
        hygiene.get("output_is_sanitized"),
        hygiene.get("secret_values_in_logs_or_errors") is False,
        cleanup.get("committed_key_removed"),
    ]
    return "PASS" if all(required) else "FAIL"


def child_read(repo: Path, key: str) -> dict[str, Any]:
    secret_values: list[str] = []
    result: dict[str, Any] = {"mode": "fresh-process-read", "key_scope": "temporary"}
    try:
        secret_database, aws = get_secret_and_iam(secret_values)
        config, _ = resolve_application_config(repo, secret_values)
        service, db_connection = build_db_service(config)
        from research_platform.config.repository import ConfigRepository
        from research_platform.platform.service_registry import ServiceRegistry

        registry = ServiceRegistry()
        registry.clear()
        registry.register_service("Database", service)
        pg_repo = ConfigRepository()._get_pg_repo()
        value = pg_repo.get_parameter(key) if pg_repo else None
        result.update({
            "iam_pass": aws["iam"]["sts_identity_pass"],
            "secret_pass": aws["secret"]["get_secret_value_pass"],
            "engine_is_postgresql": db_connection.engine.url.get_backend_name() == "postgresql",
            "fallback": bool(db_connection.is_fallback),
            "read_persisted_record": value is not None and value.get("verification") == "DATA-001-P0-02A",
            "secret_value_in_output": any(value and value in json.dumps(result, default=str) for value in secret_values),
        })
        service.disconnect()
        registry.clear()
    except Exception as exc:
        result.update({"read_persisted_record": False, "error_type": type(exc).__name__})
    return result


def markdown_report(results: Mapping[str, Any]) -> str:
    verdict = results.get("verdict", "BLOCKED")
    lines = [
        "# DATA-001-P0-02A EC2 Verification Evidence",
        "",
        f"**FINAL VERDICT: {verdict}**",
        "",
        "> This report is generated by the read-only verifier. Values that could identify or authenticate AWS resources are intentionally omitted.",
        "",
        "## Evidence",
        "",
        "```json",
        json.dumps(results, indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Interpretation",
        "",
        "`PASS` requires the exact commit, IAM/STS identity, Secrets Manager retrieval, committed TOJI configuration resolution, PostgreSQL engine, active TLS, commit, rollback, fresh-process read, secret-safe configuration persistence, no fallback, sanitized output, and targeted cleanup to all pass.",
        "",
        "`FAIL` means the verifier reached the target execution path and one or more assertions failed. `BLOCKED` means the verifier could not establish the required target commit or prerequisite AWS/application execution context.",
        "",
        "`schema_modification_attempted` must remain false. The verifier intentionally does not invoke the lifecycle method that runs automatic schema creation.",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only DATA-001-P0-02A EC2 verifier")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="TOJI checkout directory")
    parser.add_argument("--output", type=Path, help="write Markdown evidence report")
    parser.add_argument("--json-output", type=Path, help="write JSON evidence")
    parser.add_argument("--read-key", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    if args.read_key:
        result = child_read(repo, args.read_key)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("read_persisted_record") else 1

    try:
        results = run_verification(repo)
    except Exception as exc:
        results = {
            "task_id": "DATA-001-P0-02A-VERIFY-EC2-RUN",
            "target_commit": TARGET_COMMIT_FULL,
            "verdict": "BLOCKED",
            "errors": [{"type": type(exc).__name__, "message": "top-level verifier failure; details withheld"}],
        }
    report = markdown_report(results)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    if args.json_output:
        args.json_output.write_text(json.dumps(results, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(report)
    return 0 if results.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
