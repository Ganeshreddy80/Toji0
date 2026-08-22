# TOJI Module Connection Report

This report audits the connection and integration flow across the complete TOJI trading stack to verify production readiness.

## Module Integration Status

| Module | Connection Status | Details / Call Paths |
|---|---|---|
| **Market Gateway** | **CONNECTED** | Receives WebSocket ticks, normalizes candles, and broadcasts `system.market_tick_received` via the Event Bus. |
| **Feature Platform** | **CONNECTED** | `FeaturePlatformOrchestrator` is resolved and executed in `run_paper_trading.py` on every tick. Computes EMA, RSI, ATR, Support/Resistance, Trend, etc. |
| **Price Action Engine** | **CONNECTED** | `PriceActionOrchestrator` is resolved in `run_paper_trading.py` and processes every tick to update candle history, VWAP, and ATR. |
| **Strategy Engine** | **CONNECTED** | `StrategyComposer` is resolved in `run_paper_trading.py` and evaluates rules (e.g., Mean Reversion) to generate BUY/SELL/HOLD decisions. |
| **AI Signal Engine** | **CONNECTED** | `AISignalGenerator` is resolved in `run_paper_trading.py` to produce final BUY/SELL suggestions based on confluence scores. |
| **AI Auditor** | **NOT USED (MOCKED / TEST ONLY)** | `AIDecisionAuditor` in `research_platform/risk_governance/ai_auditor.py` is fully tested in unit tests, but is **never imported or called** in `run_paper_trading.py` or the live pipeline. |
| **Risk Governance** | **NOT USED (MOCKED / TEST ONLY)** | The new `KillSwitchEngine`, `RealTimeRiskMonitor`, and `PositionGuardian` in `research_platform/risk_governance/` are not called by `run_paper_trading.py` or the OMS during runtime. Only the old `RiskManagementOrchestrator` is called. |
| **OMS** | **CONNECTED** | `OmsCore` is resolved in `run_paper_trading.py`. Validates limits, checks compliance (via old risk orchestrator), and routes orders. |
| **Execution Engine** | **NOT USED (MOCKED / TEST ONLY)** | The new institutional `ExchangeExecutionSimulator` (`research_platform/execution_engine/`) is not wired into `OmsCore` or the paper runner. OMS uses the old `PaperMarketOrchestrator` routing logic. |
| **Paper Trading** | **CONNECTED** | resolved in `run_paper_trading.py` and starts sessions/markets. |
| **Trade Journal** | **CONNECTED** | `TradeJournalOrchestrator` is resolved and subscribes to OMS `FILLED` order events, calculating metrics (MFE/MAE/PnL) and saving journals. |
| **Trade Memory** | **CONNECTED** | `TradeJournalOrchestrator` resolves `TradeMemoryEngine` and saves completed trades via `save_trade`. |
| **Feedback Learning** | **CONNECTED** | `AISignalGenerator` resolves `StrategyFeedbackEngine` to adjust AI confidence using historical memory stats. |

## Critical Findings & Blockers

1. **New Institutional Execution Engine is Dead Code in Production**: The new execution simulator, fees, spread, slippage model, and exchange fault injector are not wired into the actual trading loop.
2. **New Risk Governance is Dead Code in Production**: The new Kill Switch, Real-Time Risk Monitor, and Position Guardian are not actively protecting the live engine or API.
3. **Tests passing using mocks**: Risk governance, AI Auditor, and Institutional Execution Engine tests pass, but they do so in isolation by mock-instantiating the components. The actual runtime is not calling them.
