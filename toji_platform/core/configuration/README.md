# Configuration Manager

> **Module:** `platform.core.configuration`

## Purpose

Central configuration loading from environment variables with profile support (Development, Testing, Production).

## Convention

Environment variables with the `TOJI_` prefix are mapped to dot-separated config keys:

```
TOJI_DATABASE_HOST → database.host
TOJI_APP_ENV       → app.env
```

## Profiles

| Profile | Behaviour |
|---------|-----------|
| `development` | Verbose logging, debug mode |
| `testing` | Isolated, deterministic |
| `production` | JSON logging, strict validation |

## Usage

```python
from platform.core.configuration import ConfigurationManager

config = ConfigurationManager(overrides={"app.debug": "true"})
config.get("database.host", "localhost")
config.get_required("app.secret.key")
config.validate(["database.host", "database.port"])
```
