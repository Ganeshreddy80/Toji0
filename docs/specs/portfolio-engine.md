# Portfolio Engine (PE) Subsystem Specification

## Why
The Portfolio Engine is the authoritative portfolio management and position tracking subsystem of the TOJI platform. It consumes execution completed events, keeps track of active long/short positions, calculates realized and unrealized PnL, tracks exposures, computes equity stats (win rate, etc.), and exposes portfolio states to the Dashboard Platform.

## Scope
* **In-Scope**:
  * Position lifecycle management (opening, adding, reducing, and closing LONG/SHORT positions).
  * Real-time Realized PnL, Unrealized PnL, and weighted average entry/exit calculations.
  * Exposure metrics (net exposure, gross exposure, leverage ratios).
  * Rolling portfolio stats (winning %, losing %, average win/loss, profit factor).
  * API endpoints for positions, metrics, and snapshots.
  * Event-driven updates publishing position changes to the Dashboard.
* **Deferred**:
  * Advanced portfolio optimization (e.g. mean-variance optimization, Kelly portfolio weights calculations - framework stubs only).
  * Tax lot accounting (FIFO/LIFO/MinTax matching - simple weighted average cost calculation is used).

## Technical Architecture

### 1. Enums
* `PositionSide`: `LONG`, `SHORT`
* `PositionState`: `OPEN`, `CLOSED`

### 2. Pydantic Models (Immutable V2)
* `Position`
* `ClosedPosition`
* `PortfolioSnapshot`
* `PortfolioMetrics`
* `PortfolioHealth`
* `PositionUpdate`
* `PortfolioStatistics`

### 3. Events
* Subscribes to:
  * `system.execution_completed`
  * `system.execution_partial_fill`
  * `system.execution_cancelled`
* Publishes:
  * `system.position_opened`
  * `system.position_updated`
  * `system.position_closed`
  * `system.portfolio_updated`
  * `system.pnl_updated`
  * `system.exposure_updated`

### 4. Integration Impact
* Dashboard Platform will be updated to display the `Portfolio` tab.
* API endpoints added to Dashboard APIRouter.

## Quality Gate Audit
* **Clarity**: 9/10
* **Completeness**: 9/10
* **Feasibility**: 10/10
* **Overall Score**: 9.3/10 (Passed >= 7.0 gate)
