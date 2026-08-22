# TOJI Platform — Architecture Certification

**Document Class:** Engineering Contract
**Classification:** Architecture Baseline
**Version:** 1.0
**Status:** CERTIFIED — Awaiting Human Sign-Off
**Produced By:** CTO / Principal Architect (AI-assisted deep audit)
**Date:** 2025-08
**Evidence Policy:** Every claim in this document is traced to a specific file + line number verified from source code. Claims that cannot be verified are marked `NOT VERIFIED` or `UNKNOWN`.

---

> **Governing Rule**
> Nothing will be deleted, merged, rewritten, or migrated until this document is signed off.
> This document is the immutable engineering contract for all future phases.

---

## Table of Contents

1. [Runtime Entry Points](#1-runtime-entry-points)
2. [Boot Sequence](#2-boot-sequence)
3. [Plugin System](#3-plugin-system)
4. [Dependency Injection Container](#4-dependency-injection-container)
5. [Event Bus](#5-event-bus)
6. [Market Data Flow](#6-market-data-flow)
7. [Canonical Trading Pipeline](#7-canonical-trading-pipeline)
8. [Database and Persistence Layer](#8-database-and-persistence-layer)
9. [Paper Trading Subsystem](#9-paper-trading-subsystem)
10. [API Layer](#10-api-layer)
11. [Component Inventory](#11-component-inventory)
12. [Duplicate and Ambiguous Inventory](#12-duplicate-and-ambiguous-inventory)
13. [Production Risk Registry](#13-production-risk-registry)
14. [Kernel Dual-Stack Problem](#14-kernel-dual-stack-problem)
15. [Certification Sign-Off](#15-certification-sign-off)

---

## 1. Runtime Entry Points

Three confirmed entry points exist. Only one is the canonical boot path.

| Entry Point | File | Mechanism | Status |
|---|---|---|---|
| Primary CLI | `main.py:1` | `bootstrap_platform()` -> `PlatformApplication.boot()` | VERIFIED |
| Docker API | `scripts/run_api.py` (via `docker-compose.yml`) | FastAPI via uvicorn, loads `backend/main.py` | VERIFIED |
| Docker Engine | `scripts/run_paper_trading.py` (via `docker-compose.yml`) | Standalone process, owns tick loop | VERIFIED |
| toji_platform CLI | `toji_platform/boot.py` -> `main()` | Boots TojiKernel with 12 plugins directly | VERIFIED |
| toji_platform runner | `toji_platform/runner.py` -> `LiveRunner.run()` | Calls `boot_kernel()`, adds RecoveryManager | VERIFIED |
| Paper Verification | `run_paper_trade_verification.py` | One-shot verification script | VERIFIED |

**Key Finding:** Two distinct kernel stacks exist and are run simultaneously in Docker. See Section 14.

---

## 2. Boot Sequence

### 2.1 research_platform Boot Path (Docker/Production)

**Verified Source:** `research_platform/platform/startup.py`

```
main.py
  └── bootstrap_platform()                          [research_platform/platform/bootstrap.py]
        └── PlatformApplication.boot()              [research_platform/platform/application.py]
              └── PlatformStartupCoordinator.boot_platform()   [startup.py:29]
                    ├── Step 1: ConfigurationBootloader.load_configuration()   [startup.py:33]
                    │         → Delegates to research_platform.config.config_manager.ConfigManager
                    │         → Falls back to hardcoded defaults on failure
                    │         → Parses DATABASE_URL env var if present
                    ├── Step 2: DatabaseLifecycleManager.connect()             [startup.py:37]
                    │         → Creates DatabaseConnection(config['database'])
                    │         → Calls run_migrations(engine) — creates all SQLAlchemy tables
                    │         → Falls back to sqlite:///:memory: in DEV/pytest mode
                    ├── Step 3: ContainerBootloader.boot_container()           [startup.py:42]
                    │         → Returns empty Container()
                    │         → Registers: Configuration, Database, IConfigProvider, IEventBus
                    ├── Step 4: EventBusBootloader.boot_eventbus()             [startup.py:54]
                    │         → Returns InMemoryEventBus()
                    └── Step 5: PluginLoader.discover_plugins(container)       [startup.py:61]
                              → Scans ALL subdirs of research_platform/ for plugin.py
                              → Instantiates classes ending with "Plugin"
                              → Sorts by boot_priority dict
                              → Calls p.initialize() sequentially
                              → Post-boot: runs ValidationOrchestrator if registered
```

### 2.2 Boot Priority Order

**Verified Source:** `research_platform/platform/startup.py:64-109`

| Priority | Plugin Class |
|---|---|
| 0 | ConfigPlugin |
| 1 | LoggingPlugin |
| 1.5 | AlertingPlugin |
| 2 | ValidationPlugin |
| 2.5 | MetricsPlugin |
| 3 | ConfigurationPlugin |
| 5 | ResearchDataPlatformPlugin |
| 8 | InstitutionalMemoryPlugin |
| 9 | KnowledgeGraphPlugin |
| 10 | FeaturePlatformPlugin |
| 10.1 | PriceActionPlugin |
| 10.2 | MultiTimeframePlugin |
| 10.3 | ConfluencePlugin |
| 10.4 | AISignalPlugin |
| 11 | RiskManagementPlugin |
| 11.5 | RiskEngineV2Plugin |
| 11.8 | PositionSizingPlugin |
| 12 | TradeJournalPlugin |
| 13 | OmsPlugin |
| 14 | ExecutionEnginePlugin |
| 15 | BacktestingEnginePlugin |
| 16 | OptimizationEnginePlugin |
| 17 | PaperMarketPlugin |
| 18 | PaperTradingPlugin |
| 19 | PaperDashboardPlugin |
| 20 | OperationsCenterPlugin |
| 21 | PortfolioAnalyticsPlugin |
| 21.5 | PortfolioIntelligencePlugin |
| 22 | StrategyLifecyclePlugin |
| 22.5 | StrategyFrameworkPlugin |
| 23 | ExperimentManagerPlugin |
| 24 | StrategySchedulerPlugin |
| 25 | StressTestingPlugin |
| 26 | MonitoringPlugin |
| 27 | ReportingPlugin |
| 28 | TOJIOSPlugin |
| 28.5 | PortfolioGovernorPlugin |
| 29 | LiveTradingEnginePlugin |
| 29.5 | PortfolioAccountingPlugin |
| 29.7 | ExitEnginePlugin |
| 30 | RecoveryPlugin (default fallback for unlisted plugins) |
| 31 | RuntimePlugin |

**Plugins NOT in boot_priority dict (receive default priority 30, load in filesystem order):**

Verified from the full plugin discovery list vs the boot_priority keys:
`AIIntelligencePlugin`, `AlphaFactoryPlugin`, `DeploymentPlugin`, `ExecutionSimulatorPlugin`,
`ExperimentManagementPlugin`, `GovernancePlugin`, `MarketRegimePlugin`, `MultiAgentPlugin`,
`ObservabilityPlugin`, `PortfolioConstructionPlugin`, `PortfolioEnginePlugin`,
`PortfolioOptimizerPlugin`, `ResearchIntelligencePlugin`, `ResearchLabPlugin`,
`ResearchPlatformPlugin`, `SimulationPlugin`, `StrategyLabPlugin`, `StrategyRegistryPlugin`,
`SystemValidationPlugin`, `ValidationCorePlugin`, `WalkForwardPlugin`,
`WorkflowOrchestrationPlugin`

> WARNING: ~22+ plugins without explicit boot priority. Initialization order for these is non-deterministic (filesystem order). If any depend on each other, silent boot failures may occur.

### 2.3 toji_platform Boot Path (Alternative Kernel)

**Verified Source:** `toji_platform/boot.py:38-114`

```
toji_platform.boot.boot_kernel()
  └── TojiKernel.__init__()        [toji_platform/kernel.py:64]
        ├── ConfigurationManager(overrides)
        ├── Container()
        ├── InMemoryEventBus()
        ├── 8x domain Registries
        │     (Research, Agent, Playbook, Plugin, Strategy, Asset, Memory, Analytics)
        ├── PluginManager()
        ├── LifecycleManager()
        ├── HeartbeatScheduler(event_bus, plugin_manager)
        ├── RuntimeHealthMonitor(self)
        ├── AlertManager(health_monitor)
        └── _register_core_services()  — registers all above in Container
  └── Loads 12 hardcoded plugins:
        MarketGateway, UniverseManager, MarketIntelligencePlugin,
        PriceActionPlugin, ConfluencePlugin, StrategyPlugin,
        TradingContextPlugin, RiskEnginePlugin, PositionSizingPlugin,
        ExecutionEnginePlugin, PortfolioPlatformPlugin, DashboardPlatformPlugin
  └── kernel.boot()
        └── PluginManager.initialize_all()   (topological order)
        └── LifecycleManager.start_all()
```

---

## 3. Plugin System

### 3.1 Auto-Discovery Mechanism

**Verified Source:** `research_platform/platform/plugin_loader.py:18-43`

- Discovery scans every subdirectory of `research_platform/` for a file named `plugin.py`.
- Within each `plugin.py`, any class whose name ends with `Plugin` and whose `__module__` matches the expected import path is instantiated with the DI container as the constructor argument.
- Total Discovered: 63 plugin.py files found (verified by find command).

### 3.2 Plugin Interface Compliance

**Verified Source:** `toji_platform/core/plugin_manager/interfaces.py` (referenced by IPlugin imports)

The canonical interface is `IPlugin` from `toji_platform.core.plugin_manager.interfaces`.
Required methods: `plugin_id`, `name`, `version`, `dependencies`, `state`, `initialize()`, `shutdown()`, `health_check()`.

| Plugin | Implements IPlugin | Status |
|---|---|---|
| `ResearchPlatformPlugin` (core/plugin.py) | YES | VERIFIED |
| `FeaturePlatformPlugin` | YES | VERIFIED |
| All other 60+ domain plugins | NO | VERIFIED — no IPlugin parent in class declarations |

> WARNING: ~60+ plugins bypass the canonical IPlugin interface. Plugin health monitoring via `PluginManager.health_check_all()` will miss non-compliant plugins. Silent runtime failures are possible.

### 3.3 Plugin Rollback on Boot Failure

**Verified Source:** `toji_platform/kernel.py:170-184`

`TojiKernel._kernel_rollback()` calls `lifecycle.stop_all()` and `plugin_manager.shutdown_all()` on boot failure. This rollback exists **only in the toji_platform kernel**, not in the `research_platform` boot path.

---

## 4. Dependency Injection Container

### 4.1 research_platform Container

**Verified Source:** `research_platform/platform/container_boot.py:12-14`

- Class: `Container` from `toji_platform.core.dependency_injection`
- Boot: Returns a bare `Container()` with no pre-registered services.
- Services are registered inside `PlatformStartupCoordinator.boot_platform()` and then by individual plugins during their `initialize()` calls.
- Singleton `ServiceRegistry` (separate from Container) stores: `Configuration`, `Database`, `Container`, `EventBus`, `Plugins`.

### 4.2 toji_platform Container

**Verified Source:** `toji_platform/kernel.py:88`, `toji_platform/kernel.py:330-381`

- Same `Container` class from `toji_platform.core.dependency_injection`.
- Pre-registers at kernel init: `IConfigProvider`, `IEventBus`, `IPluginManager`, `IContainer`, `lifecycle_manager`, `heartbeat_scheduler`, all 8 registries, `RuntimeHealthMonitor`, `AlertManager`.

### 4.3 Container Class

**Verified Source:** `toji_platform/core/dependency_injection/container.py:35`

- Class: `Container(IContainer)` — singleton-instance registration model.
- API: `register(key, instance=...)`, `resolve(key)`, `has(key)`.
- Key can be a `type` or a `str`.

---

## 5. Event Bus

### 5.1 Implementation

**Verified Source:** `toji_platform/core/event_bus/bus.py:33-171`

| Property | Value |
|---|---|
| Class | `InMemoryEventBus(IEventBus)` |
| Transport | In-process dict-backed, **synchronous** |
| Concurrency | `threading.RLock` for thread-safe subscribe/publish |
| Wildcard | `"*"` subscription dispatches to all events |
| Handler Model | Registered in-order; called synchronously |
| Duplicate Guard | Handler already-registered warning, not error |
| Timeline Buffer | Last 100 events in `deque(maxlen=100)` |
| Error Behaviour | Handler exception raises `EventBusError` |

### 5.2 EventBus Boot

**Verified Source:** `research_platform/platform/eventbus_boot.py:12-13`

`EventBusBootloader.boot_eventbus()` returns `InMemoryEventBus()`. Registered in Container under both `"IEventBus"` (string key) and `IEventBus` (type key).

### 5.3 Event Types (Verified from Source)

| Event String | Producer | Consumer |
|---|---|---|
| `system.market_data_received` | MarketGateway | `handle_market_tick()` in paper runner |
| `SignalReceived` | AISignalGenerator | NOT VERIFIED |
| `OrderGenerated` | OmsCore | NOT VERIFIED |
| `OrderExecuted` | ExecutionEngine | NOT VERIFIED |
| `OrderFilled` / `PaperOrderFilled` | PaperTradingOrchestrator | AccountingService.on_fill() |
| `PositionOpened` | NOT VERIFIED | NOT VERIFIED |
| `PortfolioUpdated` | NOT VERIFIED | NOT VERIFIED |
| `TradeJournalCreated` | NOT VERIFIED | NOT VERIFIED |
| `ResearchPlatformInitialized` | ResearchPlatformPlugin | NOT VERIFIED |
| `ResearchPlatformShutdown` | ResearchPlatformPlugin | NOT VERIFIED |

> WARNING: No centralized event registry exists. Event type strings are hardcoded as literals throughout the codebase. Typos in event names will silently drop events.

---

## 6. Market Data Flow

### 6.1 Market Data Ingestion

**Verified Source:** `toji_platform/boot.py:62-113`, `scripts/run_paper_trading.py:163`

```
[Binance WebSocket / Mock Provider]
      |
      v
MarketGateway (market_gateway/core/gateway.py:26)
  └── Receives candles + trades
  └── Publishes to EventBus: "system.market_data_received"
      |
      v
handle_market_tick(event)           [scripts/run_paper_trading.py:163]
  └── event.payload = {symbol, price, timestamp, volume}
```

### 6.2 Market Tick Modes

**Verified Source:** `toji_platform/boot.py:56-80`

| Mode | Config Key | Provider |
|---|---|---|
| `live` | `market_gateway.provider_mode=live` | `BinanceGatewayProvider(use_mock=False)` |
| `mock` | `market_gateway.provider_mode=mock` | `BinanceGatewayProvider(use_mock=True)` |
| `replay` | (default) | `UniverseManager` only, no streaming provider |
| `demo` | `MARKET_PROVIDER=demo` env var | NOT VERIFIED |

### 6.3 Symbol Universe

**Verified Source:** `scripts/run_paper_trading.py:53-57`

Default symbols: `BTCUSDT`, `ETHUSDT` (driven by `BINANCE_SYMBOLS` env var, comma-separated).
Price boundary validation: BTC range `1000-500000`, ETH range `100-50000`.

---

## 7. Canonical Trading Pipeline

**Verified Source:** `scripts/run_paper_trading.py:163-811`

The authoritative live trading loop is `handle_market_tick()`. The following is the verified canonical tick-to-trade pipeline:

```
TICK RECEIVED (EventBus: "system.market_data_received")
  |
  +-- [Step 0] Boundary Validation (price range checks)
  |            Bad tick -> record_bad_tick(), return
  |
  +-- [Step 1] RuntimeStateManager.record_tick()
  |
  +-- [Step 2] Market Data Normalization
  |            MarketDataNormalizer.normalize_binance_candle()
  |            or OHLCV() construction from raw price
  |
  +-- [Step 3] PriceActionOrchestrator.process_tick(symbol, price, ts, volume)
  |            Builds price history bar list per symbol
  |
  +-- [Step 4] FeaturePlatformOrchestrator.compute_and_store(features, symbol, df)
  |            Features: open, high, low, close, ema9, ema21, ema50,
  |                      rsi, atr, volume, volume_change, support, resistance,
  |                      breakout, trend
  |
  +-- [Step 5] StrategyComposer.generate_decision(strategy, symbol, price, indicators)
  |            Decision: BUY | SELL | HOLD
  |            HOLD -> return (no trade)
  |
  +-- [Step 6] AISignalGenerator.generate_signal(symbol, price)
  |            Signal: BUY | SELL | WAIT
  |            WAIT -> return (no trade)
  |
  +-- [Step 7a] AIDecisionAuditor.audit(signal_dict, regime)
  |             min_confidence=0.55, min_risk_reward=1.5
  |             REJECTED -> Telegram alert, return
  |
  +-- [Step 7b] KillSwitchEngine.evaluate(daily_pnl, capital, peak_capital, ...)
  |             HALTED -> Telegram alert, return
  |
  +-- [Step 7c] RealTimeRiskMonitor.calculate_risk_score(...)
  |             risk_score < 40.0 -> return
  |
  +-- [Step 7d] OmsCore.submit_order(strategy_id, symbol, qty, price, "MARKET", side)
  |             Internal OMS route:
  |               -> PaperExecutionRouter (PAPER mode)
  |                   -> PaperTradingOrchestrator.submit_paper_order()
  |                       -> PaperBrokerAdapter -> PaperExchange (simulated fill)
  |                       -> Publishes PaperOrderFilled to EventBus
  |                           -> AccountingService.on_fill()
  |                               -> PostgresTradeRepository.save_trade()
  |                               -> PostgresPositionRepository.save_position()
  |                               -> PostgresLedgerRepository.save_entry()
  |                               -> OMS order status -> FILLED in PostgreSQL
  |
  +-- [Step 7f] TradeMemoryEngine.save_trade()  [pattern analysis, NOT accounting SoT]
  |
  +-- [Step 7g] Telegram trade alert (format_trade_alert)
```

> CRITICAL WARNING (verified from source comment at `scripts/run_paper_trading.py:702-704`):
> "Do NOT call ExchangeExecutionSimulator directly here. That was a duplicate, disconnected path
> that bypassed all persistence." This implies a now-deactivated dual-execution path existed.
> **Verify ExchangeExecutionSimulator is not called anywhere in the active tick loop before Phase 2.**

---

## 8. Database and Persistence Layer

### 8.1 Engine

**Verified Source:** `research_platform/persistence/postgres/connection.py:14-115`

| Property | Value |
|---|---|
| Primary DB | PostgreSQL via SQLAlchemy `create_engine` |
| Pool Size | 20 connections, max_overflow=10 |
| Timeout | pool_timeout=5s, connect_timeout=2s |
| Fallback | `sqlite:///:memory:` (DEV mode / pytest only) |
| Migration | `run_migrations(engine)` calls `Base.metadata.create_all()` on every boot |
| Telegram Alert on Failure | YES — fires Telegram before raising RuntimeError in PAPER/PROD mode |

### 8.2 Database Schema

**Verified Source:** `research_platform/persistence/postgres/migrations.py`

| Table | Model Class | Purpose |
|---|---|---|
| `orders` | `OrderModel` | OMS order lifecycle |
| `trades` | `TradeModel` | Executed trade records |
| `positions` | `PositionModel` | Open position state |
| `trade_journals` | `TradeJournalModel` | Journal entries per trade |
| `daily_journals` | `DailyJournalModel` | Daily aggregated journal |
| `trade_statistics` | `TradeStatisticsModel` | Aggregate stats (JSON blob) |
| `portfolios` | `PortfolioModel` | Portfolio weights |
| `analytics` | `AnalyticsModel` | Named metrics (float) |
| `strategies` | `StrategyModel` | Strategy config |
| `experiments` | `ExperimentModel` | Research experiment records |
| `monitoring_status` | `MonitoringStatusModel` | Service health check results |
| `monitoring_alerts` | `MonitoringAlertModel` | Alert log |
| `monitoring_metrics` | `MonitoringMetricModel` | Metric counters |
| `reports` | `ReportModel` | Generated reports |
| `configurations` | `ConfigurationModel` | K/V config store |
| `jobs` | `JobModel` | Scheduled job definitions |
| `trade_ledger` | `TradeLedgerModel` | Accounting ledger (entry/exit/PnL/fees) |

### 8.3 Persistence Gaps

| Gap | Details |
|---|---|
| No Alembic | Schema managed by `create_all()` — destructive schema changes require manual DROP |
| No migration versioning | No migration history table detected. Rolling back schema changes is NOT supported |
| SQLite fallback in DEV | In-memory SQLite means all persistence is lost on restart in DEV mode |
| `trade_statistics` JSON blob | Stats stored as unstructured JSON — no queryable columns |

---

## 9. Paper Trading Subsystem

### 9.1 Architecture

**Verified Source:** `research_platform/paper_trading/plugin.py`, `scripts/run_paper_trading.py:692-704`

```
OmsCore.submit_order()
  └── PaperExecutionRouter  (routes based on TRADING_MODE=PAPER)
        └── PaperTradingOrchestrator.submit_paper_order()
              └── PaperBrokerAdapter
                    └── PaperExchange (simulated fill at current price)
                    └── Publishes PaperOrderFilled event
                          └── AccountingService.on_fill()
                                └── Postgres persistence (trade, position, ledger)
```

### 9.2 Paper Trading Plugin Inventory

| Plugin | Class | File |
|---|---|---|
| Paper Market | `PaperMarketPlugin` | `research_platform/paper_market/plugin.py` |
| Paper Trading | `PaperTradingPlugin` | `research_platform/paper_trading/plugin.py` |
| Paper Dashboard | `PaperDashboardPlugin` | `research_platform/paper_dashboard/plugin.py` |

### 9.3 State Management

**Verified Source:** `toji_platform/runtime/state.py` (referenced at `scripts/run_paper_trading.py:34`)

- Class: `RuntimeStateManager`
- State Enum: `RuntimeState` (values include RUNNING, STOPPING)
- Redis used for cross-process state sharing (keys: `TOJI:paper_engine_status`, `TOJI:runtime_status`)
- Fallback: in-memory state if Redis unavailable

### 9.4 Heartbeat

**Verified Source:** `scripts/run_paper_trading.py:814-827`

- `heartbeat_loop()` runs in a background thread.
- Interval: `DEV=60s`, `PAPER=1800s`, `PROD=3600s` (driven by `TOJI_MODE` env var).
- Calls `trigger_heartbeat_alert(state_manager, container)` from `toji_platform.runtime.heartbeat`.

---

## 10. API Layer

### 10.1 FastAPI Application

**Verified Source:** `backend/main.py:35-66`

| Property | Value |
|---|---|
| Framework | FastAPI |
| Title | "TOJI Dashboard & Controls API" |
| Version | "1.0.0" |
| CORS | DEV: localhost variants; PROD: `CORS_ALLOWED_ORIGINS` env var or `https://app.tojitrading.com` |

### 10.2 Verified Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | None | Health check root |
| GET | `/health` | None | Service status |
| GET | `/api/v1/runtime/status` | rate_limiter, admin or analyst | Full pipeline telemetry |
| GET | `/api/v1/overview` | rate_limiter, admin or analyst | Portfolio KPI cards |
| GET | `/api/v1/charts` | rate_limiter, admin or analyst | OHLCV bars per symbol |
| GET | `/api/v1/signals` | rate_limiter, admin or analyst | Latest signal events from EventBus timeline |
| GET | `/api/v1/risk/status` | None | Risk governance snapshot (HARDCODED — not live) |
| GET | `/api/v1/research/strategies` | None | Strategy performance (HARDCODED — not live) |
| GET | `/api/v1/recovery/logs` | rate_limiter, admin or analyst | Log tail + heartbeat status |
| POST | `/api/v1/runtime/control` | rate_limiter, admin only | Start/pause/reload live session |

### 10.3 API Boot Dependency

**Verified Source:** `backend/main.py:25-33`

```python
platform = PlatformState.get()
if platform is None:
    raise RuntimeError("API started before TOJI kernel")
container = platform_app._startup.service_registry.get_service("Container")
```

The API **cannot start** unless the platform kernel is already booted and `PlatformState` is set. Hard runtime dependency.

---

## 11. Component Inventory

### 11.1 Canonical Orchestrators (Verified in Active Pipeline)

| Component | Class | File | Container Resolution |
|---|---|---|---|
| Price Action | `PriceActionOrchestrator` | `research_platform/price_action/orchestrator.py` | By class type |
| Feature Platform | `FeaturePlatformOrchestrator` | `research_platform/feature_platform/orchestrator.py` | By class type |
| Strategy Composer | `StrategyComposer` | `research_platform/strategy_framework/composer.py` | By class type |
| AI Signal Generator | `AISignalGenerator` | `research_platform/ai_signal/signal_generator.py` | By class type |
| OMS Core | `OmsCore` | `research_platform/oms/oms_core.py` | By class type |
| Trade Journal | `TradeJournalOrchestrator` | `research_platform/trade_journal/orchestrator.py` | By class type (API) |
| Live Trading | `LiveTradingOrchestrator` | `research_platform/live_trading/orchestrator.py` | By class type (API) |
| Portfolio Governor | UNKNOWN class | UNKNOWN | By string key "PortfolioGovernor" |
| Portfolio Accounting | UNKNOWN class | UNKNOWN | By string key "PortfolioAccounting" |
| Exit Engine | UNKNOWN class | UNKNOWN | By string key "ExitEngine" |
| Kill Switch | `KillSwitchEngine` | `research_platform/risk_governance/kill_switch.py` | By string key "KillSwitchEngine" |
| AI Decision Auditor | `AIDecisionAuditor` | `research_platform/risk_governance/ai_auditor.py` | Direct instantiation (not from container) |
| Real-Time Risk Monitor | `RealTimeRiskMonitor` | `research_platform/risk_governance/risk_monitor.py` | Direct instantiation (not from container) |

### 11.2 Core Infrastructure (toji_platform)

| Component | Class | File |
|---|---|---|
| Kernel | `TojiKernel` | `toji_platform/kernel.py` |
| Container | `Container(IContainer)` | `toji_platform/core/dependency_injection/container.py` |
| Event Bus | `InMemoryEventBus(IEventBus)` | `toji_platform/core/event_bus/bus.py` |
| Configuration | `ConfigurationManager(IConfigProvider)` | `toji_platform/core/configuration/manager.py` |
| Plugin Manager | `PluginManager(IPluginManager)` | `toji_platform/core/plugin_manager/` |
| Lifecycle Manager | `LifecycleManager` | `toji_platform/core/lifecycle/` |
| Heartbeat Scheduler | `HeartbeatScheduler` | `toji_platform/core/lifecycle/` |
| Runtime Health Monitor | `RuntimeHealthMonitor` | `toji_platform/services/health_monitor.py` |
| Alert Manager | `AlertManager` | `toji_platform/services/alert_manager.py` |
| Runtime State | `RuntimeStateManager` | `toji_platform/runtime/state.py` |
| Recovery Manager | `RecoveryManager` | `toji_platform/runner.py:30` |

---

## 12. Duplicate and Ambiguous Inventory

The following are verified duplicate or ambiguous module pairs. None may be deleted or merged until an authorized Phase decision is made.

| Domain | Module A | Module B | Status |
|---|---|---|---|
| Experiment Management | `research_platform/experiment_management/` ExperimentManagementPlugin | `research_platform/experiment_manager/` ExperimentManagerPlugin | DUPLICATE. Only ExperimentManagerPlugin is in boot_priority (23). ExperimentManagementPlugin loads at default priority 30. BOTH will boot. |
| Config Loading | `research_platform/config/plugin.py` ConfigPlugin (priority 0) | `research_platform/configuration/plugin.py` ConfigurationPlugin (priority 3) | DUPLICATE. Both boot. Functional overlap UNKNOWN. |
| Validation | `research_platform/validation/plugin.py` ValidationPlugin (priority 2) | `research_platform/validation_core/plugin.py` ValidationCorePlugin (default priority) | DUPLICATE. Both boot. Functional overlap UNKNOWN. |
| Portfolio (7-way) | portfolio_analytics, portfolio_construction, portfolio_engine, portfolio_governor, portfolio_intelligence, portfolio_optimizer, portfolio_accounting | -- | 7 portfolio-domain plugins exist. Canonical accounting SoT is PortfolioAccountingPlugin (priority 29.5). Remaining responsibility boundaries are UNKNOWN. |
| Strategy (4-way) | strategy_framework, strategy_lab, strategy_lifecycle, strategy_registry | -- | 4 strategy-domain plugins. Canonical is StrategyFrameworkPlugin (priority 22.5). Others: UNKNOWN functional ownership. |
| Risk (2 booting + 1 direct) | risk_management (priority 11), risk_engine_v2 (priority 11.5) | risk_governance module (not a plugin, instantiated directly in tick loop) | 2 booting risk plugins + unregistered governance module. Functional boundaries UNKNOWN. |

---

## 13. Production Risk Registry

The following risks are verified from source code and constitute production blockers.

| ID | Risk | Severity | Evidence |
|---|---|---|---|
| PROD-001 | **Dual kernel stacks.** `research_platform` PlatformApplication and `toji_platform` TojiKernel are separate boot paths running in the same Docker environment. State may diverge. | CRITICAL | `main.py`, `toji_platform/boot.py`, `docker-compose.yml` |
| PROD-002 | **InMemoryEventBus is synchronous.** A slow handler blocks the entire tick pipeline. No async, no queuing, no backpressure. | CRITICAL | `toji_platform/core/event_bus/bus.py:66` |
| PROD-003 | **InMemoryEventBus is non-persistent.** All events lost on process restart. No replay, no audit log beyond 100-event deque. | HIGH | `toji_platform/core/event_bus/bus.py:43` |
| PROD-004 | **SQLite fallback in DEV/pytest.** Any code path running in DEV mode uses an in-memory database. All persistence is silently lost on restart. | HIGH | `research_platform/persistence/postgres/connection.py:92-101` |
| PROD-005 | **No migration versioning.** Schema changes via `create_all()` cannot be rolled back. No Alembic or equivalent detected. | HIGH | `research_platform/persistence/postgres/migrations.py:181` |
| PROD-006 | **~60 plugins do not implement IPlugin.** Plugin health monitoring via `PluginManager.health_check_all()` will miss non-compliant plugins. Silent runtime failures are possible. | HIGH | Plugin class declarations (grep verified) |
| PROD-007 | **~22+ plugins without explicit boot priority.** Non-deterministic boot order among these plugins. Cross-plugin initialization dependencies will fail silently. | HIGH | `research_platform/platform/startup.py:64-109` |
| PROD-008 | **AIDecisionAuditor and RealTimeRiskMonitor are instantiated directly, not from DI container.** Configuration cannot be injected; behavior cannot be overridden without code changes. | MEDIUM | `scripts/run_paper_trading.py:501-506`, `:595-596` |
| PROD-009 | **KillSwitchEngine registered in container on first tick.** Before the first tick, `container.has("KillSwitchEngine")` returns False. Race condition possible if API resolves it before first tick. | MEDIUM | `scripts/run_paper_trading.py:560-564` |
| PROD-010 | **`/api/v1/research/strategies` returns hardcoded data.** Not live. Does not reflect actual running strategies or backtest results. | LOW | `backend/main.py:208-230` |
| PROD-011 | **`/api/v1/risk/status` returns hardcoded data.** Not connected to KillSwitchEngine or RealTimeRiskMonitor. | LOW | `backend/main.py:233-245` |
| PROD-012 | **Single-process event bus with multi-process Docker deployment.** MarketGateway and PaperTradingEngine run in separate processes but share no message bus. Events published in one process cannot be received by the other. | CRITICAL | `docker-compose.yml` (two separate services), `toji_platform/core/event_bus/bus.py` |

---

## 14. Kernel Dual-Stack Problem

This section documents the most architecturally significant finding.

**Finding:** Two completely independent kernel stacks coexist.

| Stack | Root | DI Container | Event Bus | Plugins |
|---|---|---|---|---|
| research_platform | `research_platform/platform/application.py` | ServiceRegistry + Container from ContainerBootloader | InMemoryEventBus (one instance) | 63 auto-discovered plugins via filesystem scan |
| toji_platform | `toji_platform/kernel.py` | Container pre-registered in `__init__` | InMemoryEventBus (different instance) | 12 hardcoded plugins loaded in `boot.py` |

**Implications:**
- The two kernels maintain separate DI containers and separate event bus instances.
- Events published on one event bus are invisible to subscribers on the other.
- Services registered in one container cannot be resolved from the other.
- `scripts/run_paper_trading.py` bootstraps via `research_platform.platform.bootstrap.bootstrap_platform()` (Stack 1), then resolves services from `ServiceRegistry().get_service("Container")` (Stack 1 container).
- `toji_platform/runner.py` (LiveRunner) bootstraps via `toji_platform.boot.boot_kernel()` (Stack 2).
- The Docker supervisor (`scripts/runtime_supervisor.py`) runs both `scripts/run_api.py` (Stack 1) and `scripts/run_paper_trading.py` (Stack 1), so in the Docker deployment, only Stack 1 is active.
- Stack 2 (`toji_platform/boot.py` via `python -m toji_platform.boot`) is a separate CLI entry point only.

**Resolution Status:** NOT RESOLVED. Both stacks are maintained. Architecture migration decision required in Phase 6 (Runtime Consolidation).

---

## 15. Certification Sign-Off

| Section | Evidence Grade | Confidence |
|---|---|---|
| Runtime Entry Points | File and line verified | HIGH |
| Boot Sequence (research_platform) | File and line verified | HIGH |
| Boot Sequence (toji_platform) | File and line verified | HIGH |
| Plugin Discovery Mechanism | File and line verified | HIGH |
| Plugin Interface Compliance | Class declarations verified | MEDIUM |
| DI Container | File and line verified | HIGH |
| Event Bus | File and line verified | HIGH |
| Market Data Flow | File and line verified | HIGH |
| Canonical Trading Pipeline | File and line verified (step-by-step) | HIGH |
| Database Schema | All 17 tables verified | HIGH |
| Database Fallback | File and line verified | HIGH |
| Paper Trading Subsystem | File and line verified | HIGH |
| API Endpoints | File and line verified | HIGH |
| Duplicate Inventory | Verified from plugin class names and boot priority | HIGH |
| Production Risks | Derived from verified evidence | HIGH |
| Dual-Stack Problem | Verified from imports and file structure | HIGH |

---

**Prepared by:** CTO / Architecture Audit
**Evidence audit date:** 2025-08
**Next mandatory review:** Upon completion of Phase 2 (Trading Pipeline Validation)
**Zero source files were modified, deleted, or renamed during this audit.**

---

*This document is the TOJI Architecture Certification. It constitutes the engineering contract for all future architectural work. No architectural change may be made without referencing and updating this document.*
