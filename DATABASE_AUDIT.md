# TOJI Database Production Readiness Audit

## 1. Schema Analysis

PostgreSQL contains the following tables:
- `orders` (mapped to `OrderModel`): Active and historical orders.
- `trades` (mapped to `TradeModel`): Executed trade fills.
- `trade_journals` (mapped to `TradeJournalModel`): Journals compiling post-trade metrics.
- `daily_journals` (mapped to `DailyJournalModel`): Daily journal aggregates.
- `trade_statistics` (mapped to `TradeStatisticsModel`): Total trading expectancy statistics.
- `positions` (mapped to `PositionModel`): Local cache of active positions.
- `strategies`
- `portfolios`
- `analytics`
- `experiments`
- `jobs`
- `monitoring_status`, `monitoring_alerts`, `monitoring_metrics`
- `reports`
- `configurations`

### Missing Tables
- **Signals Table**: There is no table in PostgreSQL to store incoming, audited, or rejected signals.
- **Risk Events Table**: There is no table to store Kill Switch trigger events, state transitions, or Position Guardian alerts.

---

## 2. Persistence Verification

### Checkpoint / Recovery
Upon container restart via `docker compose restart`, local state (such as orders in `OMSRepository` and journals in `TradeJournalRepository`) is retrieved from PostgreSQL if the connection is active.
However, because risk state is in-memory only, a restart wipes out the active Risk/Kill Switch state.

---

## 3. Database Fallback Risk

### SQLite Fallback
The `DatabaseConnection` class falls back to an in-memory SQLite database (`sqlite:///:memory:`) if PostgreSQL connection fails.
- **Critical Risk**: In fallback mode, all trading history, orders, and journals are written to memory and **permanently lost** on process restart or crash.
- **Lack of Alerting**: If fallback occurs, the platform logs a warning but continues booting. There is no critical alert dispatched to Telegram notifying SRE of the database connection failure.
