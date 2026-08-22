# CONFIGURATION.md — Central Config Schema & Mappings

The configuration engine (R51) manages YAML profiles, secrets parsing, environment variable overrides, and dynamic hot-reloads.

## Profile Defaults
- **DEV**: Runs against `localhost` database, short telemetry intervals, validation enabled.
- **PAPER**: Uses local `toji_paper` database, paper trading gateway broker, latency thresholds set to 50ms.
- **PROD**: Live credentials, production server bindings, risk limit strictness.

## Environment Variable Overrides
Prefix all overrides with `TOJI_` (e.g. `TOJI_DATABASE_PORT=5432`). These take precedence over profile defaults.

## Secrets Resolution
Encrypted credentials (e.g., base64 string inputs) are decapsulated automatically during runtime mapping via the secrets parser.
