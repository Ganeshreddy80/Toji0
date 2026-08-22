# DATABASE_REPORT.md — PostgreSQL Connection Pooling & Mappings Audit

## 1. Database Connection Pool Diagnostics
TOJI leverages SQLAlchemy connection pools to coordinate multi-threaded sessions efficiently.

- **Pool Implementation**: `StaticPool`
- **Pool Size (max concurrent connections)**: `5`
- **Max Overflow**: `10`
- **Connection Timeout (seconds)**: `30`
- **Pre-Ping Connectivity Verification**: `True`

---

## 2. ORM Persistence Schema Mappings (16 tables)
Here is the active schema index mapped via `SQLAlchemy` models:

| Table Name | Columns Count | Primary Keys | Foreign Keys Mappings | Custom Indexes |
| :--- | :--- | :--- | :--- | :--- |
| `orders` | 8 | order_id | None | None |
| `trades` | 7 | trade_id | None | None |
| `positions` | 4 | position_id | None | None |
| `trade_journals` | 7 | journal_id | None | None |
| `daily_journals` | 2 | date | None | None |
| `trade_statistics` | 2 | stats_id | None | None |
| `portfolios` | 3 | portfolio_id | None | None |
| `analytics` | 4 | analytics_id | None | None |
| `strategies` | 4 | strategy_id | None | None |
| `experiments` | 4 | experiment_id | None | None |
| `monitoring_status` | 4 | service_name | None | None |
| `monitoring_alerts` | 5 | alert_id | None | None |
| `monitoring_metrics` | 2 | metric_name | None | None |
| `reports` | 5 | report_id | None | None |
| `configurations` | 2 | key | None | None |
| `jobs` | 6 | job_id | None | None |

### Database Verification Checklist
- **Session Lifecycle Boundaries**: Mapped using thread-local registry patterns.
- **Transaction Rollback Safety**: Automatic transactional rollback triggered on startup exceptions or validation failures.
- **Auto-Reconnect Strategy**: `pool_pre_ping=True` ensures stale connections are discarded and re-established automatically.
- **Migration Synchronization**: Automatic metadata schema alignment executed during application bootstrap stage.
