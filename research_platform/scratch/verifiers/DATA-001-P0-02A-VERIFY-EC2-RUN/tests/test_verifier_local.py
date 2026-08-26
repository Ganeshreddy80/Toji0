from __future__ import annotations

import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path

TOJI_REPO = next(
    (parent for parent in Path(__file__).resolve().parents if (parent / "research_platform").is_dir()),
    None,
)
if TOJI_REPO is not None:
    sys.path.insert(0, str(TOJI_REPO))

import pytest


SCRIPT = Path(__file__).parents[1] / "toji_data_001a_verify_ec2.py"
spec = importlib.util.spec_from_file_location("toji_verify_ec2", SCRIPT)
verifier = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(verifier)


GOOD_GIT = {
    "repository_present": True,
    "canonical_remote": True,
    "branch_present": False,
    "branch": "<detached>",
    "commit_matches_requested": True,
    "resolved_commit_exact": True,
    "commit_sha": verifier.TARGET_COMMIT_FULL,
    "working_tree_clean": True,
}


def test_dirty_worktree_blocks_before_aws_or_database(monkeypatch, tmp_path):
    dirty = {**GOOD_GIT, "working_tree_clean": False}
    calls = []
    monkeypatch.setattr(verifier, "git_identity", lambda repo: dirty)
    monkeypatch.setattr(verifier, "get_secret_and_iam", lambda values: calls.append("aws"))
    monkeypatch.setattr(verifier, "build_db_service", lambda config: calls.append("db"))

    result = verifier.run_verification(tmp_path)

    assert result["verdict"] == "BLOCKED"
    assert calls == []


def test_wrong_commit_blocks_before_aws_or_database(monkeypatch, tmp_path):
    wrong = {**GOOD_GIT, "commit_matches_requested": False, "resolved_commit_exact": False}
    calls = []
    monkeypatch.setattr(verifier, "git_identity", lambda repo: wrong)
    monkeypatch.setattr(verifier, "get_secret_and_iam", lambda values: calls.append("aws"))
    monkeypatch.setattr(verifier, "build_db_service", lambda config: calls.append("db"))

    result = verifier.run_verification(tmp_path)

    assert result["verdict"] == "BLOCKED"
    assert calls == []


def test_missing_selector_is_blocked_before_database_write(monkeypatch, tmp_path):
    monkeypatch.setattr(verifier, "git_identity", lambda repo: GOOD_GIT)
    monkeypatch.setattr(verifier, "choose_selector", lambda: (None, "UNSET"))
    calls = []
    monkeypatch.setattr(verifier, "build_db_service", lambda config: calls.append("db"))

    result = verifier.run_verification(tmp_path)

    assert result["verdict"] == "BLOCKED"
    assert calls == []
    assert result["errors"]


def test_runtime_password_is_allowed_when_persisted_value_is_safe():
    secret = "synthetic-unit-password"
    config = {"database": {"password": secret}, "runtime": {"mode": "PAPER"}}
    persisted = {"value": {"verification": "unrelated"}}

    result = verifier.verify_config_persistence_safety(config, secret, persisted)

    assert result["runtime_password_present_allowed"] is True
    assert result["persisted_central_config_contains_secret"] is False
    assert result["central_config_secret_safe"] is True


def test_persisted_password_fails_safety_assertion():
    secret = "synthetic-unit-password"
    config = {"database": {"password": secret}, "runtime": {"mode": "PAPER"}}
    persisted = {"database": {"password": secret}}

    result = verifier.verify_config_persistence_safety(config, secret, persisted)

    assert result["runtime_password_present_allowed"] is True
    assert result["persisted_central_config_contains_secret"] is True
    assert result["central_config_secret_safe"] is False


def test_tls_require_is_not_certification_pass():
    result = verifier.tls_policy_evidence("postgresql", "require", True)

    assert result["engine_is_postgresql"] is True
    assert result["server_ssl_active"] is True
    assert result["sslmode_policy_pass"] is False


@pytest.mark.parametrize("sslmode", ["verify-full", "verify-ca"])
def test_tls_certificate_verifying_modes_are_certification_passes(sslmode):
    result = verifier.tls_policy_evidence("postgresql", sslmode, True)

    assert result["engine_is_postgresql"] is True
    assert result["server_ssl_active"] is True
    assert result["sslmode_policy_pass"] is True


class DeleteRecorder:
    def __init__(self):
        self.deleted = []

    def delete(self, key):
        self.deleted.append(key)
        return True


class TransactionDouble:
    @contextmanager
    def transaction(self):
        yield


def test_cleanup_deletes_exactly_two_uuid_scoped_keys():
    repo = DeleteRecorder()
    results = {"rollback_test": {"rollback_absent_after_abort": True}}

    verifier.cleanup_temporary_rows(repo, TransactionDouble(), "commit-uuid", "rollback-uuid", results)

    assert repo.deleted == ["commit-uuid", "rollback-uuid"]
    assert results["cleanup"]["committed_key_removed"] is True
    assert results["cleanup"]["rollback_key_removed"] is True


def test_secret_error_redaction_does_not_emit_secret():
    secret = "synthetic-secret-value"
    result = verifier.safe_exception(RuntimeError(f"password={secret}"), [secret])

    assert secret not in result["message"]
    assert result["message"] == "verifier step failed; details withheld"


def complete_verdict_fixture():
    return {
        "errors": [],
        "git": {"canonical_remote": True, "commit_matches_requested": True, "resolved_commit_exact": True, "working_tree_clean": True},
        "iam": {"credential_provider_available": True, "sts_identity_pass": True},
        "secret": {"get_secret_value_pass": True, "database_fields_present": True},
        "application_configuration": {"configuration_bootloader_pass": True},
        "application_matches_secret_target": True,
        "connection": {"database_service_connected": True, "fallback": False, "engine": {"engine_is_postgresql": True, "server_ssl_active": True, "sslmode_policy_pass": True}},
        "commit_test": {"status": "PASS"},
        "rollback_test": {"status": "PASS"},
        "fresh_process": {"status": "PASS", "child_secret_in_output": False},
        "config_persistence_safety": {"central_config_secret_safe": True},
        "secret_hygiene": {"output_is_sanitized": True, "secret_values_in_logs_or_errors": False},
        "cleanup": {"committed_key_removed": True},
    }


def test_verdict_pass_requires_all_gates():
    assert verifier.determine_verdict(complete_verdict_fixture()) == "PASS"


def test_verdict_fail_for_sslmode_require():
    result = complete_verdict_fixture()
    result["connection"]["engine"]["sslmode_policy_pass"] = False

    assert verifier.determine_verdict(result) == "FAIL"


def test_verdict_blocked_for_git_gate():
    result = complete_verdict_fixture()
    result["git"]["working_tree_clean"] = False

    assert verifier.determine_verdict(result) == "BLOCKED"
