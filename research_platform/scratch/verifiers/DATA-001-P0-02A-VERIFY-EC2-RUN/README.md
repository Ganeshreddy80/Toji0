# DATA-001-P0-02A — EC2 Read-Only Verification Package

This package verifies the exact TOJI implementation commit:

```text
ae7897cd175a8f8964f6c2475933783f9f0042d
```

The supplied token is 39 characters. The verifier requires it to resolve to the full commit SHA `ae7897cd175a8f8964f6c2475933783f9f0042d8`; any other resolution is `BLOCKED`.

Run it **only on the already-provisioned EC2 verifier**. Do not run it from the Manus sandbox. The verifier is read-only with respect to source code, Git history, AWS infrastructure, IAM, RDS configuration, and schema/DDL. It performs exactly two UUID-scoped temporary configuration-row writes to the existing `configurations` table for commit/rollback evidence, then deletes only those same rows in cleanup. It performs no migrations, schema changes, IAM changes, RDS changes, or Git writes.

## Contents

| File | Purpose |
|---|---|
| `toji_data_001a_verify_ec2.py` | Self-contained executable verifier |
|   `README.md` | EC2 commands, output contract, local tests, and verdict rules |
| `tests/test_verifier_local.py` | Local decision tests; not run on EC2 |

## EC2 prerequisites

The EC2 verifier must already contain a clean checkout of `Ganeshreddy80/Toji0`, Python, the committed runtime dependencies, and network access to the configured RDS PostgreSQL endpoint. The instance must expose its IAM role through the normal AWS SDK credential chain. The operator must provide only a **non-secret** selector and region, for example:

```bash
export AWS_REGION="<approved-region>"
export TOJI_DATABASE_SECRET_ARN="<approved-secret-arn>"
```

The script accepts `TOJI_DATABASE_SECRET_ARN`, `TOJI_DATABASE_SECRET_NAME`, or `AWS_DATABASE_SECRET_NAME`. It never prints the selector value. It does not accept a password, connection string, or long-lived AWS key as an input. A pre-existing `DATABASE_URL` is rejected as a bypass because it would prevent certification of the committed Secrets Manager path. Before any AWS call or database write, it requires the canonical remote, the requested commit token to resolve to full SHA `ae7897cd175a8f8964f6c2475933783f9f0042d8`, and a clean working tree.

The secret must contain the standard RDS JSON fields `host`, `port`, `dbname` or `database`, `username`, and `password`. It may alternatively contain a PostgreSQL URL under `DATABASE_URL`, `url`, or `raw_url`; the URL may include `sslmode`, `sslrootcert`, or `channel_binding` query fields.

## Exact EC2 commands

From the TOJI checkout parent directory:

```bash
set -euo pipefail
export TOJI_REPO="${TOJI_REPO:-$PWD/Toji0}"
export AWS_REGION="<approved-region>"
export TOJI_DATABASE_SECRET_ARN="<approved-secret-arn>"

# Confirm the verifier is not accidentally operating on a different tree.
cd "$TOJI_REPO"
git fetch --all --tags --prune
git checkout --detach ae7897cd175a8f8964f6c2475933783f9f0042d
git status --short --branch

git show --no-patch --format='commit=%H%nsubject=%s' ae7897cd175a8f8964f6c2475933783f9f0042d

# Copy this package outside the repository, then execute:
python3 /path/to/toji_data_001a_verify_ec2.py \
  --repo "$TOJI_REPO" \
  --output /tmp/toji-data-001a-evidence.md \
  --json-output /tmp/toji-data-001a-evidence.json
```

The script exits with status `0` only for `PASS`. It exits with status `1` for `FAIL` or `BLOCKED`; the JSON and Markdown evidence files are still written. Preserve both files as audit artifacts. Do not pipe raw AWS SDK errors or environment dumps into the report.

If the checkout is already at the exact commit and the operator must not fetch or change refs, the minimum execution command is:

```bash
python3 /path/to/toji_data_001a_verify_ec2.py \
  --repo /absolute/path/to/Toji0 \
  --output /tmp/toji-data-001a-evidence.md \
  --json-output /tmp/toji-data-001a-evidence.json
```

## What the script proves

| Gate | Evidence emitted |
|---|---|
| Exact source | Repository path, branch/detached state, exact commit, clean tree |
| IAM role | Boto3 credential provider availability and sanitized STS identity success; no account or ARN value |
| Secrets Manager | Configured selector variable name and successful `get_secret_value`; no selector or payload value; a `DATABASE_URL` bypass is rejected |
| Committed TOJI config path | `ConfigurationBootloader` resolves the application database configuration using the committed provider and matches the secret’s non-secret target fields |
| PostgreSQL engine | SQLAlchemy backend/driver and `fallback=false` |
| TLS | Exact `sslmode` value, strict policy result, `sslrootcert` configured flag, certificate-verification interpretation, server SSL state, TLS version/cipher presence, and cipher bits. Only `verify-full` or `verify-ca` passes; `require` fails certification. |
| Commit transaction | Actual `ConfigRepository` → `PostgresConfigurationRepository` path performs insert/read inside `TransactionManager`, commits, and reads again |
| Fresh process | A child Python process re-runs the committed configuration path and reads the committed UUID-scoped record |
| Rollback | Actual repository insert/read inside `TransactionManager` is aborted by an intentional sentinel exception and the row is absent afterward |
| Secret hygiene | Runtime password presence is recorded as allowed; durable persisted configuration is inspected for the secret; logs, errors, child output, and evidence are scanned for secret values. |
| Cleanup | Only the two UUID-scoped temporary configuration keys are deleted |

The script deliberately initializes the committed `DatabaseConnection` directly instead of calling `DatabaseLifecycleManager.connect()`, because that lifecycle method runs the repository’s automatic `create_all()` schema synchronization. The verifier sets `schema_modification_attempted=false` and does not run migrations or DDL. It requires the existing `configurations` table to be present. Runtime password presence in the in-memory `CentralConfig` is allowed; certification fails only if the retrieved secret is found in durable central-configuration data, logs, errors, child output, or the evidence artifact.

## Expected sanitized output shape

The values below are illustrative labels, not a claim about the EC2 run. The real output omits resource identifiers, hostnames, selectors, passwords, URLs, and raw exception text.

```text
# DATA-001-P0-02A EC2 Verification Evidence

FINAL VERDICT: PASS

{
  "git": {
    "commit_matches_requested": true,
    "resolved_commit_exact": true,
    "commit_sha": "ae7897cd175a8f8964f6c2475933783f9f0042d8",
    "working_tree_clean": true
  },
  "iam": {
    "credential_provider_available": true,
    "sts_identity_pass": true,
    "identity_type": "assumed-role"
  },
  "secret": {
    "selector_present": true,
    "get_secret_value_pass": true,
    "database_fields_present": true,
    "secret_value_in_provider_logs": false
  },
  "application_matches_secret_target": true,
  "connection": {
    "fallback": false,
    "engine": {
      "engine_backend": "postgresql",
      "engine_is_postgresql": true,
      "sslmode": "verify-full",
      "certificate_verification": "required",
      "server_ssl_active": true
    }
  },
  "commit_test": {"status": "PASS", "commit_persisted": true},
  "rollback_test": {"status": "PASS", "rollback_absent_after_abort": true},
  "fresh_process": {"status": "PASS"},
  "config_persistence_safety": {
    "runtime_password_present_allowed": true,
    "persisted_central_config_contains_secret": false,
    "central_config_secret_safe": true
  },
  "secret_hygiene": {"output_is_sanitized": true},
  "cleanup": {"committed_key_removed": true},
  "verdict": "PASS"
}
```

## Verdict criteria

### PASS

Return `PASS` only when every required gate is true: canonical remote; exact commit resolution and clean tree; IAM/STS identity; Secrets Manager retrieval; committed application configuration resolution; target match; connected TOJI database service; PostgreSQL SQLAlchemy backend; `fallback=false`; active TLS; `sslmode` is exactly `verify-full` or `verify-ca`; successful commit transaction; successful rollback absence check; successful fresh-process read; runtime password allowed but absent from durable central configuration; no password/secret in logs, errors, child output, or evidence; sanitized output; and targeted cleanup.

### FAIL

Return `FAIL` when the verifier reaches the AWS/application/database path but an assertion fails, such as a SQLite backend, fallback flag, wrong target, inactive TLS, missing TLS policy, `sslmode=require`, failed transaction, failed rollback, missing fresh-process record, secret in durable configuration, leaked secret in logs/errors/output/evidence, or incomplete cleanup.

### BLOCKED

Return `BLOCKED` when prerequisites prevent a meaningful verification, including a wrong commit, dirty checkout, missing Python dependency, missing AWS credential provider, missing region/selector, denied IAM/STS, Secrets Manager access failure, unavailable RDS network path, missing existing schema, or a configuration/provider exception before the requested assertion can be evaluated.

## Safety and cleanup guarantees

The script never prints AWS account IDs, role ARNs, secret selectors, hostnames, connection URLs, passwords, or raw SDK/database exception text. It does not call AWS mutation APIs, IAM mutation APIs, RDS APIs, migration functions, schema DDL, trading/OMS code, or live execution code. Before any AWS access or database write, all Git identity checks must pass. Its only database writes are exactly two temporary configuration rows with random UUID suffixes. The `finally` block deletes only those exact keys, and it always attempts engine disposal and service-registry cleanup.

If the script is interrupted before cleanup, do not delete broadly. Use the UUID keys recorded only in the local JSON artifact, or inspect the `configurations` table under an authorized DBA procedure without exposing values. The package itself does not issue broad cleanup statements.

## Local verifier tests

Run from the package directory, not against EC2:

```bash
python3 -m pytest -q tests/test_verifier_local.py
```

The tests must cover dirty-worktree blocking, wrong-commit blocking, missing-selector blocking, runtime password allowed with safe persisted data, persisted password failure, `sslmode=require` failure, both `sslmode=verify-full` and `sslmode=verify-ca` success, exact two-key cleanup, secret error suppression, and PASS/FAIL/BLOCKED verdict decisions.

Last local run in this remediation: `13 passed in 1.80s`, with no failures, skips, xfails, or errors.

## Evidence handoff

Preserve:

1. `/tmp/toji-data-001a-evidence.md`;
2. `/tmp/toji-data-001a-evidence.json`;
3. the exact `git show` output for the target commit;
4. the command line used, with secret selector values redacted; and
5. the EC2 timestamp and verifier hostname handled under the organization’s normal audit controls.

The package does not certify the result in advance. The emitted verdict is the result of the EC2 execution only.
