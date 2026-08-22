# CONFIGURATION_REPORT.md — Configuration Environment & Overrides Audit

## 1. Central Configuration Settings
TOJI manages active settings under `CentralConfig` schemas backed by Pydantic validators.

- **Current Runtime Profile Mode**: `PAPER`
- **Active Database Target URL**: `postgresql://toji_paper:***@postgres-prod:5432/toji_paper`
- **Default Monitoring Alert Email**: `admin@toji.local`

---

## 2. Environment Variable Overrides & Hot-Reload Validation
- **Environment Overrides Checked**: Yes (validated `TOJI_DATABASE_HOST` override).
- **Environment Override Resolution Status**: `[SUCCESS]`
- **Hot-Reloading Mechanism**: Tested `ConfigManager.reload()` which successfully re-reads YAML configurations and synchronizes overrides dynamically.
- **Bounds and Constraint Checking**: All profile parameters are bounded and type-validated on initialization.
