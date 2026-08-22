# Structured Logging

> **Module:** `platform.core.logging`

## Purpose

Per-module structured logging with JSON output support. Every log call accepts `**context` kwargs that are included in the structured output.

## Usage

```python
from platform.core.logging import get_logger

logger = get_logger("my_module", json_output=True)
logger.info("Processing started", user_id="abc", batch_size=100)
# → {"timestamp": "...", "level": "INFO", "logger": "my_module", "message": "Processing started", "context": {"user_id": "abc", "batch_size": 100}}
```
