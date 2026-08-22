# LOGGING_REPORT.md — Logging Formats, Traces & Retention Audit

## 1. Structured JSON Format Verification
All specialized logs (e.g. `system.log`, `trades.log`, `errors.log`) write in a structured JSON output to support Monate-long execution metrics collection.

- **Sample Structured Log Entry**:
```json
{
  "timestamp": "2026-06-30 23:18:00,657",
  "severity": "INFO",
  "logger": "toji.system",
  "message": "SHUTDOWN_COMPLETE",
  "file": "/Users/a.ganeshkumarreddy12/TOJI/research_platform/logging/system_logger.py:34",
  "thread": "MainThread",
  "correlation_id": "SHUTDOWN",
  "extra_data": {}
}
```

---

## 2. Logging Framework Controls & Retention Policy
- **Structured Fields captured**: `timestamp`, `severity`, `logger`, `message`, `file`, `thread`, `correlation_id`, `extra_data`.
- **Log Rotation Mechanics**: Size-based rotating file handlers rotate log files automatically at `50MB` up to `10` backup files (500MB max per stream).
- **Time-Based Retention**: Daily rotation scheduled at midnight with 30-day retention buffers.
- **Sensitive Credentials Masking**: Password and secret keys are automatically masked inside Pydantic model representation string layouts.
