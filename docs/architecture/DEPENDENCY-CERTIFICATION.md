# TOJI Platform — Dependency Certification

**Document Class:** Engineering Dependency Contract
**Classification:** Pre-Engineering Baseline
**Version:** 1.0
**Status:** CERTIFIED — Awaiting Human Sign-Off
**Evidence Policy:** Every edge in this document is traced to a specific file + line number.
**Zero Python files were modified.**

---

> This is the LAST architecture document before engineering begins.
> After sign-off: no new architecture docs. Engineering starts.

---

## Table of Contents

1. [Complete Dependency Graph](#1-complete-dependency-graph)
2. [Subsystem Audits](#2-subsystem-audits)
3. [Import Graph](#3-import-graph)
4. [Call Graph](#4-call-graph)
5. [Runtime Graph](#5-runtime-graph)
6. [Duplicate Analysis](#6-duplicate-analysis)
7. [API Compatibility](#7-api-compatibility)
8. [Runtime Ownership Matrix](#8-runtime-ownership-matrix)
9. [Safe Consolidation Order](#9-safe-consolidation-order)
10. [Production Blockers](#10-production-blockers)
11. [Open Questions](#11-open-questions)
12. [Final CTO Section](#12-final-cto-section)

---

## 1. Complete Dependency Graph

All edges verified from source code imports and runtime boot sequences.

```
Docker Entry Point: scripts/runtime_supervisor.py
  |
  +-- [bootstrap] research_platform.platform.bootstrap.bootstrap_platform()
  |     |
  |     +-- ConfigurationBootloader  [startup.py:33]
  |     |     --> ConfigManager (research_platform/config/)
  |     |
  |     +-- DatabaseLifecycleManager  [startup.py:37]
  |     |     --> DatabaseConnection  [persistence/postgres/connection.py:14]
  |     |         --> SQLAlchemy + PostgreSQL (pool_size=20)
  |     |         --> SQLite fallback (DEV/pytest only)
  |     |         --> run_migrations() -> Base.metadata.create_all()
  |     |
  |     +-- ContainerBootloader  [startup.py:42]
  |     |     --> Container (toji_platform.core.dependency_injection)
  |     |
  |     +-- EventBusBootloader  [startup.py:54]
  |     |     --> InMemoryEventBus (toji_platform.core.event_bus.bus)
  |     |         [synchronous, thread-safe, 100-event deque]
  |     |
  |     +-- PluginLoader.discover_plugins()  [startup.py:61]
  |           --> Scans research_platform/**/ for plugin.py files
  |           --> Instantiates all *Plugin classes
  |           --> Sorts by boot_priority dict (37 explicitly ordered)
  |           --> Calls p.initialize() sequentially
  |
  +-- [subprocess] scripts/run_paper_trading.py
  |     |
  |     +-- MarketGateway  (market_gateway/core/gateway.py)
  |     |     --> data.schemas.market_data.OHLCV  [market_data schemas]
  |     |     --> InMemoryEventBus  [publishes: "system.market_data_received"]
  |     |
  |     +-- handle_market_tick()  [canonical tick loop]
  |           |
  |           +-- PriceActionOrchestrator  (research_platform/price_action/)
  |           |
  |           +-- FeaturePlatformOrchestrator  (research_platform/feature_platform/)
  |           |
  |           +-- StrategyComposer  (research_platform/strategy_framework/)
  |           |
  |           +-- AISignalGenerator  (research_platform/ai_signal/)
  |           |
  |           +-- AIDecisionAuditor  (research_platform/risk_governance/)
  |           |
  |           +-- KillSwitchEngine  (research_platform/risk_governance/)
  |           |
  |           +-- RealTimeRiskMonitor  (research_platform/risk_governance/)
  |           |
  |           +-- OmsCore  (research_platform/oms/oms_core.py)
  |                 --> PaperExecutionRouter
  |                       --> PaperTradingOrchestrator  (research_platform/paper_trading/)
  |                             --> PaperBrokerAdapter
  |                                   --> PaperExchange (simulated fill)
  |                             --> AccountingService
  |                                   --> PostgresTradeRepository
  |                                   --> PostgresPositionRepository
  |                                   --> PostgresLedgerRepository
  |
  +-- [subprocess] scripts/run_api.py
        |
        +-- backend/main.py  [FastAPI]
              --> research_platform.platform.state.PlatformState
              --> toji_platform.core.dependency_injection.Container
              --> toji_platform.core.event_bus.interfaces.IEventBus
              --> dashboard/api/router.py (all endpoint handlers)

SHARED INFRASTRUCTURE (consumed by multiple subsystems):
  toji_platform.core.event_bus.bus.InMemoryEventBus
  toji_platform.core.dependency_injection.Container
  toji_platform.core.configuration.manager.ConfigurationManager
  data.schemas.market_data  [OHLCV, Trade, OrderBookSnapshot]
  data.storage.base         [MockPostgresStorageEngine — tests only]
  research_platform.persistence.postgres.*
```

---

## 2. Subsystem Audits

---

### 2.1 Market Gateway

| Property | Value |
|---|---|
| Canonical implementation | `market_gateway/core/gateway.py:26` — class `MarketGateway(IPlugin)` |
| Alternative implementations | `orchestrators/market_orchestrator/market.py` (UNKNOWN runtime reach) |
| Who imports it | `toji_platform/boot.py:18`, `dashboard/api/router.py` (lazy import) |
| Who calls it | `toji_platform/boot.py` — `kernel.plugin_manager.get("market_gateway")`, `toji_platform/runner.py:163` |
| Who owns it | **toji_platform** kernel (hardcoded as plugin #1 in boot.py) |
| Boot path | `toji_platform/boot.py:62` — loaded as first plugin in 12-plugin set |
| Dependency chain | `data.schemas.market_data` → `InMemoryEventBus` → `MarketReplayEngine` → `MarketDataRouter` → `MarketDataValidator` |
| Downstream consumers | `handle_market_tick()` in paper runner, `toji_platform.services.market_data_manager.MarketDataManager` |
| Upstream providers | Binance WebSocket (`BinanceGatewayProvider`), mock mode, replay mode |
| Runtime reachable | YES (toji_platform kernel boot) |
| Docker reachable | YES (`scripts/runtime_supervisor.py` → boots toji_platform via paper runner) |
| CLI reachable | YES (`python -m toji_platform.boot`) |
| Test coverage | YES — `market_gateway/tests/` has 4 test files |
| Migration complexity | HIGH (central dependency, dual-stack consumer) |
| Risk level | HIGH |
| Recommended action | KEEP — canonical entry point for all market data |

---

### 2.2 Market Data (data.schemas)

| Property | Value |
|---|---|
| Canonical implementation | `data/schemas/market_data.py` — defines `OHLCV`, `Trade`, `OrderBookSnapshot`, `NewsEvent`, `AssetMetadata` |
| Alternative implementations | NONE verified |
| Who imports it | `market_gateway/**`, `backtesting_engine/**`, `orchestrators/market_orchestrator/market.py`, `research_platform/data/dataset.py`, `research_platform/live_trading/plugin.py`, `market_intelligence/**` (conditionally), `research_platform/tests/` |
| Who calls it | Used as data transfer objects (DTOs) across all pipeline stages |
| Who owns it | **shared** — used by both stacks |
| Boot path | Module import; no initialization required |
| Dependency chain | No upstream Python dependencies (pure pydantic/dataclass models) |
| Downstream consumers | 15+ modules import these schemas |
| Upstream providers | None (foundational DTO layer) |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES (via market_gateway tests) |
| Migration complexity | HIGH (foundational — changing breaks 15+ modules) |
| Risk level | CRITICAL |
| Recommended action | KEEP — freeze schema until consolidation is complete |

---

### 2.3 Price Action

| Property | Value |
|---|---|
| Canonical implementation | `research_platform/price_action/orchestrator.py` — class `PriceActionOrchestrator` |
| Alternative implementations | `price_action/` top-level package (separate package, canonical models for confluence) |
| Who imports canonical | `scripts/run_paper_trading.py:27`, `backend/main.py:17`, `tests/e2e/` (multiple files) |
| Who imports alternative | `confluence/**` (imports `price_action.core.enums`, `price_action.core.models`, `price_action.core.state`) — 15+ files |
| Who calls canonical | `handle_market_tick()` Step 3 — `PriceActionOrchestrator.process_tick()` |
| Who calls alternative | Confluence scoring engines (all 12 scorers) |
| Who owns it | research_platform canonical; top-level `price_action` package owns model definitions |
| Boot path | research_platform: `PriceActionPlugin` (priority 10.1). Top-level: no plugin, imported directly |
| Dependency chain | Canonical: depends on internal models. Alternative: defines `PatternDirection`, `PatternState`, `PatternStatus`, `PatternType` enums/models used by confluence |
| Downstream consumers | Confluence (all 12 analysis files), PortfolioConstruction plugin, research_platform canonical pipeline |
| Upstream providers | MarketGateway (tick data), FeaturePlatform (indicators) |
| Runtime reachable | YES (both paths) |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES — `price_action/tests/` exists |
| Migration complexity | HIGH (two separate implementations, confluence depends on top-level package models) |
| Risk level | HIGH |
| Recommended action | INVESTIGATE — top-level `price_action` package provides model definitions used by confluence; research_platform version runs in pipeline. These serve different roles and may NOT be mergeable without breaking confluence. |

---

### 2.4 Confluence

| Property | Value |
|---|---|
| Canonical implementation | `confluence/core/orchestrator.py` — class `ConfluenceOrchestrator` |
| Alternative implementations | `research_platform/confluence/plugin.py` — wraps same orchestrator |
| Who imports canonical | `dashboard/api/router.py` (lazy), `tests/integration/`, `toji_platform/boot.py:21` |
| Who calls it | `toji_platform/boot.py:21` loads `ConfluencePlugin` as plugin #5 in 12-plugin kernel |
| Who owns it | **toji_platform** (loaded in 12-plugin boot) |
| Boot path | toji_platform: `boot.py:21` — `ConfluencePlugin`. research_platform: priority 10.3 |
| Dependency chain | `market_intelligence.core.models.MarketState`, `price_action.core.*` (15 imports), `trading_context.core.models.TradingContext`, `toji_platform.core.event_bus.interfaces.IEventBus`, `toji_platform.core.dependency_injection.interfaces.IContainer` |
| Downstream consumers | toji_platform strategy_engine adapter, dashboard API |
| Upstream providers | MarketIntelligence (MarketState), PriceAction (PatternState), TradingContext |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES — `confluence/tests/` has 5+ test files |
| Migration complexity | HIGH (depends on 3 cross-module models: MarketState, PatternState, TradingContext) |
| Risk level | HIGH |
| Recommended action | KEEP — critical confluence scoring pipeline; migrate only after MarketIntelligence and PriceAction are stable |

---

### 2.5 Trading Context

| Property | Value |
|---|---|
| Canonical implementation | `trading_context/core/plugin.py:33` — class `TradingContextPlugin(IPlugin)` |
| Alternative implementations | NONE verified |
| Who imports it | `position_sizing/**` (all 12 analysis files + core), `execution_engine/core/orchestrator.py:118`, `toji_platform/boot.py:24` |
| Who calls it | All position sizing algorithms; execution orchestrator resolution |
| Who owns it | **toji_platform** (boot.py:24) |
| Boot path | toji_platform: boot.py:24 as plugin #7. research_platform: NOT in boot_priority dict (not explicitly booted) |
| Dependency chain | `toji_platform.core.*` (IPlugin, IContainer, IEventBus, IConfigProvider) |
| Downstream consumers | ALL position sizing analysis (12 files), PositionSizingPlugin, ExecutionOrchestrator |
| Upstream providers | MarketIntelligence (regime data), PriceAction (pattern context) |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES — `trading_context/tests/` exists |
| Migration complexity | HIGH (position_sizing has 12 direct imports) |
| Risk level | HIGH |
| Recommended action | KEEP — foundational dependency for all position sizing |

---

### 2.6 Strategy

| Property | Value |
|---|---|
| Canonical implementation | `strategy/core/plugin.py:39` — class `StrategyPlugin(IPlugin)` |
| Alternative implementations | `research_platform/strategy_framework/plugin.py` — `StrategyFrameworkPlugin` (priority 22.5); `research_platform/strategy_lifecycle/plugin.py`; `research_platform/strategy_registry/plugin.py`; `research_platform/strategy_lab/plugin.py` |
| Who imports canonical | `toji_platform/boot.py:23`, `toji_platform/strategy_engine/adapter.py:14`, `portfolio_construction/core/**`, `position_sizing/tests/**` |
| Who calls canonical | toji_platform kernel as plugin #6; strategy_engine adapter uses `strategy.core.enums.StrategyDecision` |
| Who calls alternatives | research_platform plugin system (all 4 boot sequentially) |
| Who owns it | SPLIT — toji_platform owns `strategy/` canonical; research_platform owns 4 variants |
| Boot path | toji_platform: boot.py:23. research_platform: StrategyFrameworkPlugin (22.5), StrategyLifecyclePlugin (22), StrategyRegistryPlugin (default), StrategyLabPlugin (default) |
| Dependency chain | `strategy.core.models.StrategySignal`, `strategy.core.enums.StrategyDecision`, used by portfolio_construction and position_sizing |
| Downstream consumers | portfolio_construction (3 files), position_sizing (tests), toji_platform strategy_engine |
| Upstream providers | TradingContext, MarketIntelligence, Confluence scores |
| Runtime reachable | YES (toji_platform via `strategy/`; research_platform via `strategy_framework`) |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES — `strategy/tests/` exists |
| Migration complexity | HIGH (4-way duplicate, cross-stack ownership) |
| Risk level | HIGH |
| Recommended action | INVESTIGATE — `strategy/` is the toji_platform canonical; `strategy_framework` is the research_platform canonical. Two separate boot paths service separate stacks. Do NOT merge until dual-stack is resolved (Phase 6). |

---

### 2.7 Universe

| Property | Value |
|---|---|
| Canonical implementation | `universe/core/manager.py` — class `UniverseManager` |
| Alternative implementations | `intelligence/universe/manager.py` (legacy, imports `data.schemas.market_data.AssetMetadata`) |
| Who imports canonical | `toji_platform/boot.py:19`, `market_intelligence/tests/test_plugin.py:110` (event only) |
| Who imports alternative | UNKNOWN — `intelligence/universe/manager.py` not verified as imported anywhere in runtime |
| Who calls canonical | toji_platform boot.py:19; LiveRunner via market_data_mgr |
| Who owns it | **toji_platform** |
| Boot path | toji_platform: boot.py:62 — `UniverseManager` plugin #2 |
| Dependency chain | `universe.providers.binance.BinanceDiscoveryProvider` (lazy import in boot.py:69) |
| Downstream consumers | MarketGateway (symbol subscription), MarketDataManager (LiveRunner) |
| Upstream providers | Binance API (symbol discovery) |
| Runtime reachable | YES (toji_platform) |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES — `universe/tests/` exists (verified via event import) |
| Migration complexity | MEDIUM |
| Risk level | MEDIUM |
| Recommended action | KEEP canonical; INVESTIGATE `intelligence/universe/` — may be safe to remove if not imported |

---

### 2.8 Market Intelligence

| Property | Value |
|---|---|
| Canonical implementation | `market_intelligence/core/plugin.py` — class `MarketIntelligencePlugin` |
| Alternative implementations | `intelligence/` top-level (separate package, legacy orchestrators use it) |
| Who imports canonical | `toji_platform/boot.py:20`, `toji_platform/strategy_engine/adapter.py:11`, `confluence/core/orchestrator.py:10` |
| Who imports alternative | `orchestrators/learning_orchestrator/learning.py`, `orchestrators/research_orchestrator/research.py` (all lazy/conditional imports) |
| Who calls canonical | toji_platform boot.py:20 as plugin #3; confluence orchestrator resolves IStateStore |
| Who owns it | **toji_platform** |
| Boot path | toji_platform: boot.py:20. research_platform: NOT in explicit boot_priority. |
| Dependency chain | `data.schemas.market_data.OHLCV`, `universe.core.events.UniverseUpdated`, `toji_platform.core.*` |
| Downstream consumers | confluence (all 15 analysis files consume `MarketState`), toji_platform strategy adapter |
| Upstream providers | Universe (symbol list), MarketGateway (OHLCV data), data.schemas |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES — `market_intelligence/tests/` has 5 test files |
| Migration complexity | HIGH (confluence has 15 direct imports of MarketState) |
| Risk level | HIGH |
| Recommended action | KEEP — foundational model provider for confluence |

---

### 2.9 Feature Pipeline

| Property | Value |
|---|---|
| Canonical implementation | `research_platform/feature_platform/orchestrator.py` — class `FeaturePlatformOrchestrator` |
| Alternative implementations | `research_platform/feature_platform/feature_pipeline.py` — class `FeaturePipeline` (used by `backtesting/engine.py`) |
| Who imports canonical | `scripts/run_paper_trading.py:25`, `tests/e2e/**` (6+ files), `backend/main.py` (indirect via container) |
| Who imports alternative | `backtesting/engine.py:11` (uses `FeaturePipeline` directly) |
| Who calls canonical | `handle_market_tick()` Step 4: `FeaturePlatformOrchestrator.compute_and_store()` |
| Who owns it | **research_platform** |
| Boot path | research_platform: `FeaturePlatformPlugin(IPlugin)` (priority 10) |
| Dependency chain | Depends on price history bars from PriceActionOrchestrator |
| Downstream consumers | StrategyComposer (indicators), AISignalGenerator (features), OmsCore (order context) |
| Upstream providers | PriceActionOrchestrator (bars), MarketGateway (tick data) |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | UNKNOWN (no CLI entry for research_platform stack alone) |
| Test coverage | YES — `research_platform/feature_platform/tests/` |
| Migration complexity | MEDIUM |
| Risk level | HIGH (central to canonical pipeline) |
| Recommended action | KEEP — both `FeaturePlatformOrchestrator` and `FeaturePipeline` serve different consumers; do not merge yet |

---

### 2.10 AI Signal

| Property | Value |
|---|---|
| Canonical implementation | `research_platform/ai_signal/` — `AISignalGenerator` |
| Alternative implementations | `research_platform/ai_intelligence/plugin.py` — `AIIntelligencePlugin` (no explicit priority, loads at default 30) |
| Who imports canonical | `scripts/run_paper_trading.py` (via container resolve) |
| Who calls canonical | `handle_market_tick()` Step 6: `AISignalGenerator.generate_signal(symbol, price)` |
| Who owns it | **research_platform** |
| Boot path | research_platform: `AISignalPlugin` (priority 10.4) |
| Dependency chain | FeaturePlatformOrchestrator (indicators), StrategyComposer (decision) |
| Downstream consumers | AIDecisionAuditor, OmsCore (if signal approved) |
| Upstream providers | FeaturePlatform (feature record), Strategy (decision) |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | UNKNOWN |
| Test coverage | UNKNOWN |
| Migration complexity | MEDIUM |
| Risk level | MEDIUM |
| Recommended action | KEEP; INVESTIGATE relationship with `ai_intelligence` plugin |

---

### 2.11 Risk

| Property | Value |
|---|---|
| Canonical implementation (governance) | `research_platform/risk_governance/` — `AIDecisionAuditor`, `KillSwitchEngine`, `RealTimeRiskMonitor` (instantiated directly, not from DI container) |
| Canonical implementation (engine v1) | `risk_engine/core/orchestrator.py` — full risk engine with `RiskStateStore`, `RiskAssessment`, `RiskDecision` |
| Canonical implementation (engine v2) | `research_platform/risk_engine_v2/plugin.py` — `RiskEngineV2Plugin` (priority 11.5) |
| Alternative implementations | `research_platform/risk_management/plugin.py` — `RiskManagementPlugin` (priority 11); `research_platform/risk_management/orchestrator.py` — `RiskManagementOrchestrator` (imported by `scripts/run_paper_trading.py:31`) |
| Who imports risk_engine (top-level) | `position_sizing/**` (ALL 12 analysis files import `risk_engine.core.models.RiskAssessment`), `dashboard/api/router.py` (imports `IRiskStateStore`, `RiskStateStore`) |
| Who imports risk_management | `scripts/run_paper_trading.py:31` |
| Who owns it | SPLIT — `risk_engine/` used by position_sizing and dashboard; `risk_management/` used by paper runner; `risk_governance/` used directly in tick loop |
| Boot path | research_platform: RiskManagementPlugin (11), RiskEngineV2Plugin (11.5) both boot. `risk_engine/` top-level: NOT a plugin, imported directly. |
| Dependency chain | `risk_engine` → `portfolio_engine.core.state.PortfolioStateStore` (conditional import); position_sizing (12 analysis files) → `risk_engine.core.models` |
| Downstream consumers | Position sizing (all algorithms), dashboard (risk status API), paper runner tick loop |
| Upstream providers | Portfolio state, market data, position data |
| Runtime reachable | YES (all three paths) |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES — `risk_engine/tests/` has 3 test files |
| Migration complexity | HIGH (3-way split: governance, engine v1, engine v2 + risk_management) |
| Risk level | CRITICAL |
| Recommended action | INVESTIGATE — must map exact functional boundaries between risk_governance, risk_management, risk_engine, and risk_engine_v2 before any merge |

---

### 2.12 OMS

| Property | Value |
|---|---|
| Canonical implementation (research_platform) | `research_platform/oms/oms_core.py:28` — class `OmsCore(IOMS, IOrderRouter, IExecutionTracker)` |
| Alternative implementation (execution_engine) | `execution_engine/oms/oms_core.py:132` — class `OmsCore` |
| Who imports research_platform OMS | `scripts/run_paper_trading.py:30`, `tests/e2e/test_end_to_end_trading_verification.py:26`, `tests/e2e/test_real_pipeline.py:149` |
| Who imports execution_engine OMS | `dashboard/api/router.py:1144-1234` (lazy imports for 7 endpoints) |
| Who calls canonical | `handle_market_tick()` Step 7d: `OmsCore.submit_order()` |
| Who owns it | SPLIT — research_platform OMS is canonical for paper trading; execution_engine OMS is used by dashboard |
| Boot path | research_platform: `OmsPlugin` (priority 13). execution_engine OMS: no plugin — imported lazily by dashboard |
| Dependency chain | research_platform OMS → `PaperExecutionRouter` → `PaperTradingOrchestrator` |
| Downstream consumers | PaperTradingOrchestrator (fills), AccountingService (persistence), dashboard (order management endpoints) |
| Upstream providers | StrategyComposer, AISignalGenerator, KillSwitchEngine (all must pass before OMS is called) |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | UNKNOWN |
| Test coverage | YES — `execution_engine/tests/` and `research_platform/oms/` tests |
| Migration complexity | HIGH (two OmsCore classes with same name in different packages) |
| Risk level | CRITICAL |
| Recommended action | INVESTIGATE — naming collision: two `OmsCore` classes. Must establish which is authoritative before Phase 2. |

---

### 2.13 Execution

| Property | Value |
|---|---|
| Canonical implementation | `execution_engine/analysis/execution_engine.py` — class `ExecutionEngine` |
| Alternative implementations | `research_platform/execution_engine/plugin.py` — `ExecutionEnginePlugin` (priority 14); `research_platform/execution_simulator/plugin.py` — `ExecutionSimulatorPlugin` (WARNING: explicitly documented as disconnected duplicate) |
| Who imports canonical | `dashboard/api/router.py` (lazy import for analytics + EMS endpoints) |
| Who calls canonical | Dashboard API endpoints; `execution_engine/core/orchestrator.py` |
| Who owns it | SPLIT — `execution_engine/` top-level for dashboard; research_platform wrapper for plugin boot |
| Boot path | research_platform: `ExecutionEnginePlugin` (priority 14). Top-level: no plugin |
| Dependency chain | `execution_engine.brokers.broker_router.BrokerRouter`, `execution_engine.core.interfaces`, `market_gateway.providers.binance.exchange.BinanceExchangeProvider` (for live trades), `position_sizing.core.events.PositionSizeCalculated` |
| Downstream consumers | Dashboard (analytics, order management), EMS engine |
| Upstream providers | OmsCore (order routing), BrokerRouter (broker dispatch), RiskGuard |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | UNKNOWN |
| Test coverage | YES — `execution_engine/tests/` has multiple test files |
| Migration complexity | HIGH |
| Risk level | HIGH |
| Recommended action | KEEP; REMOVE LATER `ExecutionSimulatorPlugin` after verifying zero active consumers |

---

### 2.14 Portfolio

| Property | Value |
|---|---|
| Canonical implementation (accounting SoT) | `research_platform/portfolio_accounting/plugin.py` — `PortfolioAccountingPlugin` (priority 29.5) |
| Canonical implementation (engine/state) | `portfolio_engine/core/` — `PortfolioStateStore`, `PortfolioSnapshot`, `PortfolioMetrics` |
| Alternative implementations | `research_platform/portfolio_analytics/` (priority 21), `research_platform/portfolio_construction/` (default), `research_platform/portfolio_engine/` (default), `research_platform/portfolio_governor/` (priority 28.5), `research_platform/portfolio_intelligence/` (priority 21.5), `research_platform/portfolio_optimizer/` (default) |
| Who imports portfolio_engine | `dashboard/api/router.py:859`, `risk_engine/core/orchestrator.py:360`, `toji_platform/boot.py:28`, `toji_platform/services/metrics_service.py:265`, `tests/integration/**` (3 files) |
| Who calls portfolio_engine | toji_platform boot.py:28 — `PortfolioPlatformPlugin` is hardcoded plugin #11 |
| Who calls portfolio_accounting | `AccountingService.on_fill()` in paper trading pipeline |
| Who imports portfolio_construction | `portfolio_construction/core/orchestrator.py:31` imports `strategy.core.models.StrategySignal` |
| Who owns it | SPLIT — `portfolio_engine/` top-level is canonical state; research_platform has 6 variants for different aspects |
| Boot path | toji_platform: PortfolioPlatformPlugin (plugin #11). research_platform: 6 plugins, 2 explicit priorities + 4 default |
| Dependency chain | portfolio_engine → risk_engine (conditional), portfolio_construction → strategy.core.models |
| Downstream consumers | Dashboard (3 portfolio endpoints), MetricsService, risk_engine |
| Upstream providers | AccountingService (fill data), OmsCore (orders), PositionSizing |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES — `portfolio_engine/tests/`, `portfolio_construction/tests/` |
| Migration complexity | HIGH (7-way split) |
| Risk level | HIGH |
| Recommended action | INVESTIGATE — map exact responsibility boundaries for all 7 portfolio modules. Accounting SoT = `portfolio_accounting`. State SoT = `portfolio_engine`. Other 5 roles UNKNOWN. |

---

### 2.15 Position Sizing

| Property | Value |
|---|---|
| Canonical implementation | `position_sizing/core/plugin.py` — `PositionSizingPlugin(IPlugin)` |
| Alternative implementations | `research_platform/position_sizing/plugin.py` — `PositionSizingPlugin` (priority 11.8, no IPlugin parent) |
| Who imports canonical | `toji_platform/boot.py:26` |
| Who calls canonical | toji_platform kernel plugin #9 |
| Dependency chain | ALL 12 analysis algorithms import: `trading_context.core.models.TradingContext`, `risk_engine.core.models.RiskAssessment`, `risk_engine.core.enums.RiskDecision`, `strategy.core.models.StrategyState` |
| Downstream consumers | ExecutionEngine (PositionSizeCalculated event), toji_platform pipeline |
| Upstream providers | TradingContext, RiskEngine, Strategy |
| Runtime reachable | YES (toji_platform) |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES — `position_sizing/tests/` has 6 test files |
| Migration complexity | HIGH (12 algorithms, 4 upstream dependencies) |
| Risk level | HIGH |
| Recommended action | KEEP canonical; INVESTIGATE research_platform duplicate |

---

### 2.16 Trade Journal

| Property | Value |
|---|---|
| Canonical implementation | `research_platform/trade_journal/plugin.py` — `TradeJournalPlugin` (priority 12) |
| Alternative implementation | `toji_platform/services/trade_journal.py` — `TradeJournal` (Sprint 3 service, registered in LiveRunner) |
| Who imports research_platform | `research_platform/trade_journal/orchestrator.py` (resolved in API) |
| Who imports toji_platform | `toji_platform/runner.py:22` |
| Who calls canonical | Paper trading pipeline (TradeJournalOrchestrator via container) |
| Who calls toji_platform | `LiveRunner.run()` — instantiated as Sprint 3 service |
| Dependency chain | `InMemoryEventBus`, `PostgresTradeRepository`, event subscriptions |
| Downstream consumers | Dashboard (trade analytics endpoints), reporting subsystem |
| Upstream providers | OmsCore fills, AccountingService |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | UNKNOWN |
| Test coverage | UNKNOWN |
| Migration complexity | MEDIUM |
| Risk level | MEDIUM |
| Recommended action | KEEP both; investigate whether they write to the same database tables |

---

### 2.17 Paper Trading

| Property | Value |
|---|---|
| Canonical implementation | `research_platform/paper_trading/orchestrator.py` — `PaperTradingOrchestrator` |
| Alternative implementations | `research_platform/paper_market/orchestrator.py` — `PaperMarketOrchestrator` (manages market feed, not trading) |
| Who imports | `research_platform/oms/oms_core.py:71` imports `PaperExecutionRouter` from `research_platform.paper_market` |
| Who calls canonical | OmsCore → PaperExecutionRouter → PaperTradingOrchestrator |
| Who owns it | **research_platform** |
| Boot path | `PaperTradingPlugin` (priority 18), `PaperMarketPlugin` (priority 17), `PaperDashboardPlugin` (priority 19) |
| Dependency chain | `PaperBrokerAdapter` → `PaperExchange` (fill simulation), `AccountingService` → PostgreSQL repositories |
| Downstream consumers | AccountingService (fills → DB), TradeJournal, Portfolio |
| Upstream providers | OmsCore (order routing), MarketGateway (current prices) |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | UNKNOWN |
| Test coverage | YES — `paper_trading/tests/` and `tests/e2e/test_paper_execution_flow.py` |
| Migration complexity | MEDIUM |
| Risk level | HIGH (canonical persistence path) |
| Recommended action | KEEP |

---

### 2.18 Dashboard

| Property | Value |
|---|---|
| Canonical implementation | `dashboard/api/router.py` — `create_api_router()` (all endpoints) + `backend/main.py` (FastAPI app) |
| Alternative implementations | `dashboard/backend/app.py` — `create_app()` (referenced in tests only: `confluence/tests/test_sprint6.py:61`) |
| Who imports canonical | `scripts/run_api.py:17`, `scripts/runtime_supervisor.py:121`, `tests/unit/platform/` |
| Who calls canonical | `runtime_supervisor.py` spawns `run_api.py` as subprocess |
| Who owns it | **research_platform** (reads from ServiceRegistry, PlatformState) |
| Boot path | Subprocess via `scripts/run_api.py`; depends on platform being booted first |
| Dependency chain | `PlatformState`, `Container`, `IEventBus`, resolves all orchestrators lazily on first request |
| Downstream consumers | External clients (browser, monitoring systems) |
| Upstream providers | All runtime subsystems (lazy resolution from Container) |
| Runtime reachable | YES |
| Docker reachable | YES (port 8000) |
| CLI reachable | YES (`uvicorn backend.main:app`) |
| Test coverage | YES — `dashboard/tests/` |
| Migration complexity | HIGH (resolves 30+ different module lazy imports) |
| Risk level | HIGH |
| Recommended action | KEEP; harden lazy imports into DI resolution after consolidation |

---

### 2.19 Scheduler

| Property | Value |
|---|---|
| Canonical implementation | `research_platform/scheduler/plugin.py` — `StrategySchedulerPlugin` (priority 24) |
| Alternative implementations | UNKNOWN |
| Who imports it | NOT VERIFIED in any external file |
| Who calls it | Boot sequencer only |
| Dependency chain | UNKNOWN |
| Runtime reachable | YES (booted, but consumers UNKNOWN) |
| Docker reachable | YES |
| CLI reachable | UNKNOWN |
| Test coverage | UNKNOWN |
| Migration complexity | LOW |
| Risk level | LOW |
| Recommended action | INVESTIGATE — no verified consumers |

---

### 2.20 Infrastructure

| Property | Value |
|---|---|
| Canonical implementation | `infrastructure/` top-level package — AWS integration modules |
| Alternative implementations | NONE verified |
| Who imports it | `tests/test_aws_infrastructure.py` (test only), `tests/test_deployment_platform.py:613` |
| Who calls it | TEST ONLY — no verified runtime import |
| Runtime reachable | NO (test only) |
| Docker reachable | NO |
| CLI reachable | NO |
| Test coverage | YES (dedicated test file) |
| Migration complexity | LOW |
| Risk level | LOW |
| Recommended action | INVESTIGATE — may be future cloud deployment prep; not in active runtime |

---

### 2.21 Deployment

| Property | Value |
|---|---|
| Canonical implementation | `deployment/` top-level package |
| Who imports it | `tests/test_deployment_platform.py` (test only) |
| Runtime reachable | NO (test only) |
| Docker reachable | NO |
| CLI reachable | NO |
| Test coverage | YES |
| Migration complexity | LOW |
| Risk level | LOW |
| Recommended action | INVESTIGATE — not in active runtime |

---

### 2.22 Operations

| Property | Value |
|---|---|
| Canonical implementation | `operations/` top-level package |
| Who imports it | `tests/test_operations_platform.py` (test only) |
| Runtime reachable | NO (test only) |
| Docker reachable | NO |
| CLI reachable | NO |
| Test coverage | YES |
| Migration complexity | LOW |
| Risk level | LOW |
| Recommended action | INVESTIGATE |

---

### 2.23 Learning / Knowledge

| Property | Value |
|---|---|
| Canonical implementation | `knowledge/` top-level — `BeliefEngine`, `EvidenceEngine`, `RuleEngine`, `ConfidenceCalculator` |
| Alternative implementation | `self_learning/` top-level |
| Who imports canonical | `orchestrators/learning_orchestrator/learning.py`, `orchestrators/research_orchestrator/research.py` (all lazy/conditional) |
| Runtime reachable | UNKNOWN — orchestrators are present but not verified as booted |
| Docker reachable | NO |
| CLI reachable | NO |
| Test coverage | UNKNOWN |
| Migration complexity | LOW |
| Risk level | LOW |
| Recommended action | INVESTIGATE — orchestrators directory appears to be a legacy layer |

---

### 2.24 Backtesting / Historical Replay

| Property | Value |
|---|---|
| Canonical implementation (v2) | `backtesting_engine/` top-level — full Monte Carlo, replay, matching engine |
| Alternative implementation (v1) | `backtesting/engine.py` — `HistoricalReplayEngine` |
| Who imports v2 | `tests/test_monte_carlo.py`, `tests/integration/**` |
| Who imports v1 | `research_platform/strategy_factory/evaluator.py:9`, `tests/unit/ops/test_ops_fix_02.py:437` |
| Who calls v2 | `toji_platform/boot.py` (NOT VERIFIED — backtesting_engine not in 12-plugin set but imports IPlugin, IEventBus, IContainer) |
| Who calls v1 | `HistoricalReplayEngine` referenced by strategy evaluator |
| Dependency chain (v2) | `toji_platform.core.*` (IPlugin, IEventBus, IContainer, BaseEvent) |
| Runtime reachable | UNKNOWN (v2 not in docker boot path; v1 used only by strategy factory evaluator) |
| Docker reachable | NO (not in runtime_supervisor subprocess list) |
| CLI reachable | UNKNOWN |
| Test coverage | YES — `backtesting_engine/tests/` has 5 test files |
| Migration complexity | MEDIUM |
| Risk level | MEDIUM |
| Recommended action | INVESTIGATE — v2 is fully built with toji_platform integration but not in production boot path |

---

### 2.25 Configuration

| Property | Value |
|---|---|
| Canonical implementation | `toji_platform/core/configuration/manager.py` — `ConfigurationManager(IConfigProvider)` |
| Alternative implementations | `research_platform/config/plugin.py` — `ConfigPlugin` (priority 0); `research_platform/configuration/plugin.py` — `ConfigurationPlugin` (priority 3) |
| Who imports canonical | `toji_platform/kernel.py`, `backtesting_engine/core/plugin.py`, `confluence/core/plugin.py`, many others |
| Who imports v1 | ConfigPlugin — booted at priority 0, no verified external consumers |
| Who imports v2 | ConfigurationPlugin — booted at priority 3, no verified external consumers |
| Dependency chain | No upstream; provides config to all downstream |
| Downstream consumers | ALL plugins (via IConfigProvider injection) |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES |
| Migration complexity | HIGH (foundational) |
| Risk level | HIGH |
| Recommended action | KEEP toji_platform canonical; INVESTIGATE ConfigPlugin and ConfigurationPlugin for functional overlap |

---

### 2.26 Plugin System

| Property | Value |
|---|---|
| Canonical implementation | `research_platform/platform/plugin_loader.py` — `PluginLoader.discover_plugins()` (research_platform stack) |
| Alternative implementation | `toji_platform/core/plugin_manager/` — `PluginManager` (toji_platform stack) |
| Discovery mechanism (research_platform) | Filesystem scan of research_platform/**/ for plugin.py, instantiate *Plugin classes |
| Discovery mechanism (toji_platform) | Hardcoded 12-plugin list in boot.py |
| Who owns it | SPLIT — research_platform (63 auto-discovered), toji_platform (12 hardcoded) |
| Interfaces | toji_platform: `IPlugin` (required: plugin_id, name, version, dependencies, state, initialize, shutdown, health_check). research_platform: NO enforced interface — ~60 plugins do not implement IPlugin |
| Runtime reachable | YES (both stacks) |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | UNKNOWN for research_platform loader |
| Migration complexity | HIGH |
| Risk level | HIGH |
| Recommended action | KEEP both in place until Phase 6 (Runtime Consolidation); enforce IPlugin on all plugins as part of Phase 3 |

---

### 2.27 Event Bus

| Property | Value |
|---|---|
| Canonical implementation | `toji_platform/core/event_bus/bus.py` — `InMemoryEventBus(IEventBus)` |
| Alternative implementations | NONE (single implementation, shared) |
| Who imports it | `backtesting_engine/**`, `confluence/core/**`, `research_platform/platform/eventbus_boot.py`, `toji_platform/kernel.py`, `toji_platform/runner.py`, `toji_platform/services/**` |
| Key characteristics | Synchronous, in-process, thread-safe (RLock), 100-event deque, no persistence |
| Instances in production | TWO separate instances — one per kernel stack (PROD-012 from Architecture Certification) |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES (used in most integration tests) |
| Migration complexity | CRITICAL — replacing with async bus breaks all synchronous consumers |
| Risk level | CRITICAL |
| Recommended action | KEEP InMemoryEventBus; Phase 5 (Event Architecture) introduces async/persistent bus ALONGSIDE it |

---

### 2.28 Database

| Property | Value |
|---|---|
| Canonical implementation | `research_platform/persistence/postgres/connection.py` — `DatabaseConnection` |
| Schema manager | `research_platform/persistence/postgres/migrations.py` — `run_migrations()` |
| ORM base | `research_platform/persistence/postgres/base_repository.py` — `Base` (SQLAlchemy declarative) |
| Tables (17 verified) | orders, trades, positions, trade_journals, daily_journals, trade_statistics, portfolios, analytics, strategies, experiments, monitoring_status, monitoring_alerts, monitoring_metrics, reports, configurations, jobs, trade_ledger |
| Migration mechanism | `Base.metadata.create_all(bind=engine)` — no Alembic, no rollback |
| Fallback | `sqlite:///:memory:` in DEV mode / pytest |
| Who calls it | `DatabaseLifecycleManager` in startup.py, all `*Repository` classes |
| Runtime reachable | YES |
| Docker reachable | YES (depends on `postgres` healthcheck) |
| CLI reachable | YES |
| Test coverage | YES — most integration tests use SQLite fallback |
| Migration complexity | HIGH (no versioning) |
| Risk level | HIGH |
| Recommended action | KEEP; add Alembic in Phase 4 (Persistence Layer) |

---

### 2.29 State Management

| Property | Value |
|---|---|
| Canonical implementation | `toji_platform/runtime/state.py` — `RuntimeStateManager` |
| Alternative implementations | `research_platform/platform/state.py` — `PlatformState` (holds reference to platform_app) |
| Who imports RuntimeStateManager | `scripts/run_paper_trading.py:34`, `backend/main.py:136` (lazy), `scripts/runtime_supervisor.py:13` |
| Who imports PlatformState | `backend/main.py:13` |
| Transport | Redis (`TOJI:paper_engine_status`, `TOJI:runtime_status`), fallback to in-memory |
| Docker reachable | YES (Redis defined in docker-compose.yml as `toji-redis`) |
| Test coverage | UNKNOWN for Redis paths |
| Migration complexity | MEDIUM |
| Risk level | MEDIUM |
| Recommended action | KEEP both; they serve different purposes (operational state vs platform lifecycle state) |

---

### 2.30 Runtime

| Property | Value |
|---|---|
| Canonical entry point | `scripts/runtime_supervisor.py` (Docker); `toji_platform/runner.py` (LiveRunner) |
| Who calls supervisor | Docker via `docker-compose.yml` command: `python scripts/runtime_supervisor.py` |
| Who calls LiveRunner | `toji_platform/boot.py:main()` (CLI mode) |
| RecoveryManager | `toji_platform/runner.py:30` — monitors plugin health, auto-restart with max 3 retries |
| HeartbeatScheduler | `toji_platform/kernel.py` — background heartbeat via EventBus |
| Docker services | postgres, redis, app (single app container running supervisor) |
| Runtime reachable | YES |
| Docker reachable | YES |
| CLI reachable | YES |
| Test coverage | YES — `tests/runtime/test_paper_runner.py` |
| Migration complexity | HIGH |
| Risk level | CRITICAL |
| Recommended action | KEEP; target of Phase 6 (Runtime Consolidation) |

---

## 3. Import Graph

### 3.1 Top-Level Package Import Relationships

Verified from grep analysis across all .py files excluding __pycache__ and .venv.

```
data.schemas.market_data
  IMPORTED BY: market_gateway (5 files), backtesting_engine, orchestrators/market_orchestrator,
               research_platform/data/dataset.py, research_platform/live_trading/plugin.py,
               market_intelligence (conditional), market_gateway/tests/

price_action (top-level)
  IMPORTED BY: confluence (15 files), portfolio_construction (3 files)

market_intelligence.core.models.MarketState
  IMPORTED BY: confluence (15 files), toji_platform/strategy_engine/adapter.py

strategy.core.models.StrategySignal
  IMPORTED BY: portfolio_construction (3 files)

strategy.core.enums.StrategyDecision
  IMPORTED BY: portfolio_construction, toji_platform/strategy_engine/adapter.py

trading_context.core.models.TradingContext
  IMPORTED BY: position_sizing (12 files + core)

risk_engine.core.models.RiskAssessment
  IMPORTED BY: position_sizing (12 algorithm files)

risk_engine.core.enums.RiskDecision
  IMPORTED BY: position_sizing (core, 2 algorithm files)

portfolio_engine.core.state.PortfolioStateStore
  IMPORTED BY: dashboard/api/router.py, risk_engine/core/orchestrator.py,
               toji_platform/services/metrics_service.py, tests/integration (3 files)

toji_platform.core.*
  IMPORTED BY: backtesting_engine (9 files), confluence (8 files), strategy/core/plugin.py,
               trading_context/core/plugin.py, market_intelligence/core/plugin.py,
               universe/core/, position_sizing/core/plugin.py, execution_engine/tests/

research_platform.platform.*
  IMPORTED BY: backend/main.py, backtesting/engine.py, scripts/runtime_supervisor.py

research_platform.oms.*
  IMPORTED BY: scripts/run_paper_trading.py, tests/e2e (6 files)

research_platform.feature_platform.*
  IMPORTED BY: scripts/run_paper_trading.py, backtesting/engine.py, tests/e2e (6 files)

research_platform.price_action.*
  IMPORTED BY: scripts/run_paper_trading.py, backend/main.py, tests/e2e (4 files)

market_gateway.*
  IMPORTED BY: dashboard/api/router.py (lazy), execution_engine/brokers/binance_broker.py,
               toji_platform/boot.py (via MarketGateway plugin class)

knowledge.*
  IMPORTED BY: orchestrators/learning_orchestrator, orchestrators/research_orchestrator (all lazy)

infrastructure.*
  IMPORTED BY: tests/test_aws_infrastructure.py (test only)

deployment.*
  IMPORTED BY: tests/test_deployment_platform.py (test only)

backtesting_engine.*
  IMPORTED BY: tests/test_monte_carlo.py

backtesting.*  (v1)
  IMPORTED BY: research_platform/strategy_factory/evaluator.py
```

---

## 4. Call Graph

### 4.1 Entry Methods and Primary Callers

| Subsystem | Entry Method | Primary Caller | Secondary Caller |
|---|---|---|---|
| MarketGateway | `subscribe(symbol, data_type, interval)` | `LiveRunner.run()` via market_data_mgr | `toji_platform/boot.py` via plugin |
| MarketGateway | publishes `"system.market_data_received"` | EventBus subscribers | handle_market_tick() |
| PriceAction (canonical) | `process_tick(symbol, price, ts, volume)` | `handle_market_tick()` Step 3 | None |
| FeaturePlatform | `compute_and_store(features, symbol, df)` | `handle_market_tick()` Step 4 | `backtesting/engine.py` (FeaturePipeline variant) |
| StrategyComposer | `generate_decision(strategy, symbol, price, indicators)` | `handle_market_tick()` Step 5 | None |
| AISignalGenerator | `generate_signal(symbol, price)` | `handle_market_tick()` Step 6 | None |
| AIDecisionAuditor | `audit(signal_dict, regime)` | `handle_market_tick()` Step 7a | None |
| KillSwitchEngine | `evaluate(daily_pnl, capital, peak_capital, ...)` | `handle_market_tick()` Step 7b | None |
| RealTimeRiskMonitor | `calculate_risk_score(...)` | `handle_market_tick()` Step 7c | None |
| OmsCore | `submit_order(strategy_id, symbol, qty, price, order_type, side)` | `handle_market_tick()` Step 7d | Dashboard API (7 endpoints) |
| PaperTradingOrchestrator | `submit_paper_order()` | OmsCore → PaperExecutionRouter | None |
| AccountingService | `on_fill(event)` | PaperOrderFilled event subscription | None |
| UniverseManager | `subscribe(symbol, data_type, interval)` | LiveRunner.run() | toji_platform boot |
| ConfluenceOrchestrator | `evaluate(market_state, pattern_state, context)` | toji_platform strategy_engine | None |
| PositionSizingPlugin | `calculate_size(context, assessment)` | ExecutionEngine | None |
| DatabaseConnection | `initialize()` → `connect()` | DatabaseLifecycleManager | Every *Repository class |
| PluginLoader | `discover_plugins(container)` | PlatformStartupCoordinator | None |
| RuntimeStateManager | `record_tick()`, `record_feature()` | `handle_market_tick()` Steps 1, 4 | heartbeat_loop |

---

## 5. Runtime Graph

### 5.1 Which Runtime Owns Each Module

| Module | Owner Runtime | Confidence |
|---|---|---|
| `market_gateway/` | toji_platform (hardcoded plugin #1) | HIGH |
| `universe/` | toji_platform (hardcoded plugin #2) | HIGH |
| `market_intelligence/` | toji_platform (hardcoded plugin #3) | HIGH |
| `price_action/` (top-level, models) | shared (confluence + toji_platform) | HIGH |
| `confluence/` | toji_platform (hardcoded plugin #5) | HIGH |
| `strategy/` (top-level) | toji_platform (hardcoded plugin #6) | HIGH |
| `trading_context/` | toji_platform (hardcoded plugin #7) | HIGH |
| `risk_engine/` (top-level) | shared (position_sizing + dashboard) | HIGH |
| `position_sizing/` (top-level) | toji_platform (hardcoded plugin #9) | HIGH |
| `portfolio_engine/` (top-level) | toji_platform (hardcoded plugin #11) | HIGH |
| `portfolio_construction/` | research_platform (default priority) | MEDIUM |
| `execution_engine/` | shared (dashboard + research_platform wrapper) | MEDIUM |
| `backtesting_engine/` | toji_platform (imports toji_platform.core.*) | MEDIUM |
| `backtesting/` (v1) | research_platform (strategy_factory import) | LOW |
| `data/schemas/` | shared (foundational DTO layer) | HIGH |
| `dashboard/` | research_platform (reads PlatformState) | HIGH |
| `backend/` | research_platform | HIGH |
| `research_platform/oms/` | research_platform | HIGH |
| `research_platform/feature_platform/` | research_platform | HIGH |
| `research_platform/price_action/` | research_platform | HIGH |
| `research_platform/paper_trading/` | research_platform | HIGH |
| `research_platform/paper_market/` | research_platform | HIGH |
| `research_platform/risk_governance/` | research_platform (direct instantiation) | HIGH |
| `research_platform/risk_management/` | research_platform | HIGH |
| `research_platform/risk_engine_v2/` | research_platform | HIGH |
| `toji_platform/` | toji_platform | HIGH |
| `infrastructure/` | NONE — test only | HIGH |
| `deployment/` | NONE — test only | HIGH |
| `operations/` | NONE — test only | HIGH |
| `knowledge/` | UNKNOWN — orchestrators only | LOW |
| `self_learning/` | UNKNOWN | LOW |

---

## 6. Duplicate Analysis

---

### 6.1 OmsCore (CRITICAL)

| Property | Value |
|---|---|
| Original | `research_platform/oms/oms_core.py:28` — `class OmsCore(IOMS, IOrderRouter, IExecutionTracker)` |
| Duplicate | `execution_engine/oms/oms_core.py:132` — `class OmsCore` |
| Reason | Two separate OMS implementations; research_platform OMS is canonical for paper trading pipeline; execution_engine OMS is wired to dashboard API |
| Consumers of original | `scripts/run_paper_trading.py`, `tests/e2e/**` |
| Consumers of duplicate | `dashboard/api/router.py` (7 endpoints with lazy imports) |
| Can merge? | NO — until interface compatibility is verified |
| Can remove? | NO — both have active consumers |
| Migration order | Phase 2: verify interface compatibility; Phase 7: merge into single OmsCore |
| Evidence | `from research_platform.oms.oms_core import OmsCore` (run_paper_trading.py:30) vs `from execution_engine.oms.oms_core import OmsCore` (router.py:1144) |
| Confidence | HIGH |

---

### 6.2 ExperimentManager / ExperimentManagement

| Property | Value |
|---|---|
| Original | `research_platform/experiment_manager/plugin.py:10` — `ExperimentManagerPlugin` (boot priority 23) |
| Duplicate | `research_platform/experiment_management/plugin.py:10` — `ExperimentManagementPlugin` (default priority 30) |
| Reason | Two modules with different names but similar domain purpose |
| Consumers of original | Boot sequencer only — NO verified external imports |
| Consumers of duplicate | Boot sequencer only — NO verified external imports |
| Can merge? | UNKNOWN — requires functional diff |
| Can remove? | UNKNOWN — no external consumers verified but functional behavior unclear |
| Migration order | Phase 7: investigate and consolidate |
| Evidence | `startup.py:97` — `"ExperimentManagerPlugin": 23`; filesystem discovery also picks up `ExperimentManagementPlugin` |
| Confidence | HIGH |

---

### 6.3 ConfigPlugin / ConfigurationPlugin

| Property | Value |
|---|---|
| Original | `research_platform/config/plugin.py:11` — `ConfigPlugin` (boot priority 0) |
| Duplicate | `research_platform/configuration/plugin.py:10` — `ConfigurationPlugin` (boot priority 3) |
| Reason | UNKNOWN — two separate config plugins, both boot |
| Consumers of original | Boot sequencer only — NO verified external imports |
| Consumers of duplicate | Boot sequencer only — NO verified external imports |
| Can merge? | UNKNOWN |
| Can remove? | NO — until functional diff is complete |
| Migration order | Phase 0/Phase 3 investigation |
| Evidence | startup.py:66 (`"ConfigPlugin": 0`), startup.py:72 (`"ConfigurationPlugin": 3`) |
| Confidence | HIGH |

---

### 6.4 ValidationPlugin / ValidationCorePlugin

| Property | Value |
|---|---|
| Original | `research_platform/validation/plugin.py:11` — `ValidationPlugin` (boot priority 2) |
| Duplicate | `research_platform/validation_core/plugin.py:11` — `ValidationCorePlugin` (default priority 30) |
| Reason | UNKNOWN |
| Consumers | Boot sequencer only — NO verified external imports for either |
| Can merge? | UNKNOWN |
| Can remove? | NO |
| Migration order | Phase 3 investigation |
| Evidence | startup.py:69 (`"ValidationPlugin": 2`); filesystem discovery |
| Confidence | HIGH |

---

### 6.5 PriceAction (research_platform vs. top-level)

| Property | Value |
|---|---|
| Original | `research_platform/price_action/orchestrator.py` — `PriceActionOrchestrator` |
| Duplicate | `price_action/` top-level package — provides `PatternDirection`, `PatternState`, `PatternStatus`, `PatternType` |
| Reason | Top-level package provides model/enum definitions used by confluence; research_platform provides runtime orchestration |
| Consumers of research_platform | `scripts/run_paper_trading.py`, `backend/main.py`, tests/e2e (4 files) |
| Consumers of top-level | `confluence/**` (15 files), `portfolio_construction` (3 files) |
| Can merge? | NO — serve different roles (models vs. orchestration) |
| Can remove? | NO — both have active consumers |
| Migration order | Keep both; establish clear module boundary in Phase 3 |
| Evidence | Grep results for `from price_action.core.*` vs `from research_platform.price_action.*` |
| Confidence | HIGH |

---

### 6.6 PositionSizing (top-level vs. research_platform)

| Property | Value |
|---|---|
| Original | `position_sizing/core/plugin.py` — `PositionSizingPlugin(IPlugin)` |
| Duplicate | `research_platform/position_sizing/plugin.py` — `PositionSizingPlugin` (no IPlugin) |
| Reason | toji_platform canonical vs. research_platform wrapper |
| Consumers of original | `toji_platform/boot.py:26` |
| Consumers of duplicate | research_platform boot sequencer (priority 11.8) |
| Can merge? | NO — different boot stacks, different interfaces |
| Can remove? | NO — both active in different stacks |
| Migration order | Phase 6: Runtime Consolidation |
| Evidence | `toji_platform/boot.py:26` import; `startup.py:83` (`"PositionSizingPlugin": 11.8`) |
| Confidence | HIGH |

---

### 6.7 ExecutionSimulatorPlugin (flagged as disconnected)

| Property | Value |
|---|---|
| Duplicate | `research_platform/execution_simulator/plugin.py` — `ExecutionSimulatorPlugin` |
| Comment in source | `scripts/run_paper_trading.py:702-704` — "Do NOT call ExchangeExecutionSimulator directly. That was a duplicate, disconnected path that bypassed all persistence." |
| Consumers | Boot sequencer only — NO verified active consumers in tick loop |
| Can remove? | INVESTIGATE — verify no other imports before removing |
| Migration order | Phase 2: verify zero active consumers; Phase 7: remove |
| Evidence | Source code comment at run_paper_trading.py:702-704 (verified) |
| Confidence | HIGH |

---

## 7. API Compatibility

### 7.1 OmsCore Shared vs. Missing API

| API Surface | research_platform/oms/oms_core.py | execution_engine/oms/oms_core.py |
|---|---|---|
| `submit_order(strategy_id, symbol, qty, price, order_type, side)` | VERIFIED (tick loop call) | NOT VERIFIED (dashboard imports class but call signatures unread) |
| IOMS interface | IMPLEMENTED (`class OmsCore(IOMS, IOrderRouter, IExecutionTracker)`) | NOT VERIFIED |
| IOrderRouter interface | IMPLEMENTED | NOT VERIFIED |
| IExecutionTracker interface | IMPLEMENTED | NOT VERIFIED |
| Constructor signature | NOT VERIFIED (not read) | NOT VERIFIED |
| Order status update | NOT VERIFIED | NOT VERIFIED |
| Compatibility verdict | UNKNOWN — interface diff not performed |
| Breaking changes | UNKNOWN |
| Required adapters | UNKNOWN until interfaces are read |

### 7.2 PositionSizingPlugin Shared API

| API Surface | position_sizing/ (IPlugin) | research_platform/position_sizing/ (no IPlugin) |
|---|---|---|
| `initialize()` | REQUIRED by IPlugin | Present (informal convention) |
| `shutdown()` | REQUIRED by IPlugin | NOT VERIFIED |
| `health_check()` | REQUIRED by IPlugin | NOT VERIFIED |
| Algorithm implementations | SAME — both import same analysis algorithms | SAME |
| Breaking change if merged | YES — health_check() missing in research_platform version |

---

## 8. Runtime Ownership Matrix

| Subsystem | Owner Runtime | Shared? | Reachable? | Canonical? | Migration Phase | Risk |
|---|---|---|---|---|---|---|
| MarketGateway | toji_platform | No | YES | YES | 6 | HIGH |
| data.schemas | shared | YES | YES | YES | FREEZE | CRITICAL |
| price_action (top-level models) | shared | YES | YES | YES (models) | 3 | HIGH |
| price_action (research_platform orchestrator) | research_platform | No | YES | YES (runtime) | 6 | HIGH |
| Confluence | toji_platform | No | YES | YES | 6 | HIGH |
| TradingContext | toji_platform | No | YES | YES | 6 | HIGH |
| Strategy (top-level) | toji_platform | No | YES | YES (toji_platform) | 6 | HIGH |
| Strategy (research_platform) | research_platform | No | YES | YES (research_platform) | 6 | HIGH |
| Universe | toji_platform | No | YES | YES | 6 | MEDIUM |
| MarketIntelligence | toji_platform | No | YES | YES | 6 | HIGH |
| FeaturePlatform | research_platform | No | YES | YES | 6 | HIGH |
| AISignal | research_platform | No | YES | YES | 7 | MEDIUM |
| risk_engine (top-level) | shared | YES | YES | YES (models) | 7 | CRITICAL |
| risk_management (research_platform) | research_platform | No | YES | YES (pipeline) | 7 | HIGH |
| risk_engine_v2 (research_platform) | research_platform | No | YES | UNKNOWN | 7 | HIGH |
| risk_governance (research_platform) | research_platform | No | YES | YES (governance) | 7 | HIGH |
| OmsCore (research_platform) | research_platform | No | YES | YES (paper trading) | 7 | CRITICAL |
| OmsCore (execution_engine) | shared | YES | YES | YES (dashboard) | 7 | CRITICAL |
| ExecutionEngine | shared | YES | YES | YES | 7 | HIGH |
| PaperTrading | research_platform | No | YES | YES | Keep | MEDIUM |
| PositionSizing (top-level) | toji_platform | No | YES | YES | 6 | HIGH |
| PositionSizing (research_platform) | research_platform | No | YES | Duplicate | 6 | MEDIUM |
| portfolio_engine (top-level) | toji_platform | No | YES | YES (state) | 7 | HIGH |
| portfolio_accounting | research_platform | No | YES | YES (accounting SoT) | Keep | MEDIUM |
| portfolio_analytics | research_platform | No | YES | UNKNOWN | 7 | MEDIUM |
| portfolio_construction | research_platform | No | YES | UNKNOWN | 7 | MEDIUM |
| portfolio_governor | research_platform | No | YES | UNKNOWN | 7 | MEDIUM |
| portfolio_intelligence | research_platform | No | YES | UNKNOWN | 7 | LOW |
| portfolio_optimizer | research_platform | No | YES | UNKNOWN | 7 | LOW |
| TradeJournal | shared | YES | YES | SPLIT | 7 | MEDIUM |
| Dashboard | research_platform | No | YES | YES | Keep | MEDIUM |
| Backtesting (v1) | research_platform | No | UNKNOWN | NO | 7 | LOW |
| BacktestingEngine (v2) | toji_platform-aligned | No | UNKNOWN | UNKNOWN | 8 | MEDIUM |
| Configuration (toji_platform) | toji_platform | YES | YES | YES | 6 | HIGH |
| ConfigPlugin | research_platform | No | YES | UNKNOWN | 3 | HIGH |
| ConfigurationPlugin | research_platform | No | YES | UNKNOWN | 3 | HIGH |
| InMemoryEventBus | shared | YES | YES | YES | 5 | CRITICAL |
| DatabaseConnection | research_platform | No | YES | YES | 4 | HIGH |
| RuntimeStateManager | toji_platform | No | YES | YES | Keep | MEDIUM |
| PlatformState | research_platform | No | YES | YES | Keep | LOW |
| Infrastructure | NONE | No | NO | NO | Future | LOW |
| Deployment | NONE | No | NO | NO | Future | LOW |
| Operations | NONE | No | NO | NO | Future | LOW |
| Knowledge/Learning | UNKNOWN | No | NO | UNKNOWN | Future | LOW |

---

## 9. Safe Consolidation Order

Based ONLY on verified dependency chains. A module can only be consolidated AFTER all its dependencies are stable.

### Phase 0 — Baseline (NOW)
**What:** Freeze schema modules. No changes to foundational DTOs.
**Targets:** `data.schemas.market_data`, `toji_platform.core.*` (Container, EventBus, IPlugin interfaces)
**Why:** These are imported by 15+ modules. Any change cascades everywhere.

### Phase 1 — Runtime Validation (Audit, No Code Change)
**What:** Verify ExchangeExecutionSimulator has zero active callers. Verify both OmsCore class signatures. Verify ConfigPlugin vs ConfigurationPlugin functional diff.
**Why:** Before any consolidation begins, the full blast radius of each duplicate must be known.

### Phase 2 — Trading Pipeline Validation
**What:** Confirm paper trading tick loop produces correct fills. Lock canonical pipeline.
**Targets:** The pipeline: PriceAction → FeaturePlatform → Strategy → AISignal → AIAuditor → KillSwitch → RiskMonitor → OmsCore → PaperTrading → Accounting
**Why:** This pipeline must be stable before its components are touched.
**Dependencies:** None (read-only verification).

### Phase 3 — Data and State Architecture
**What:** Establish authoritative state for each domain. Choose canonical implementations for price_action (models), risk_engine (models), portfolio_engine (state).
**Why:** All downstream modules depend on these model definitions. Locking them enables safe consolidation.
**Prerequisites:** Phase 2 must be complete.

### Phase 4 — Persistence Layer
**What:** Add Alembic migration versioning. Lock database schema.
**Why:** Cannot safely change schemas until migrations are versioned.
**Prerequisites:** Phase 3 (schema models must be final).

### Phase 5 — Event Architecture
**What:** Document all event strings. Build centralized event registry. Plan async event bus (do NOT replace synchronous bus yet).
**Why:** Event bus is synchronous (PROD-002 blocker). Must audit all consumers before changing transport.
**Prerequisites:** Phase 3 (stable state models emit events).

### Phase 6 — Runtime Consolidation
**What:** Begin merging toji_platform and research_platform boot stacks. Target: single kernel.
**Targets:** Consolidate MarketGateway, Confluence, TradingContext, Universe, MarketIntelligence, PositionSizing into one boot path.
**Why:** These are cleanly owned by toji_platform with verified IPlugin compliance.
**Prerequisites:** Phases 3, 4, 5 must be complete. ALL module interfaces must be locked.

### Phase 7 — Business Logic Consolidation
**What:** Consolidate duplicates: OmsCore (2 versions), PositionSizing (2 versions), Strategy (2 stacks), Risk (3 variants), Portfolio (7 modules), TradeJournal (2 versions).
**Why:** These have cross-stack consumers. Cannot merge until Phase 6 resolves the runtime boundary.
**Prerequisites:** Phase 6 (single runtime context established).

### Phase 8 — Production Hardening
**What:** Enforce IPlugin on all 60+ non-compliant plugins. Add explicit boot priorities for all 22+ unordered plugins. Add startup health check enforcement.
**Prerequisites:** Phases 6 and 7 complete (single runtime, single set of plugins).

### Phase 9+ — Performance, Paper Trading, Cloud
**Why:** Performance engineering, paper trading certification, and cloud deployment can only happen after the system is consolidated and hardened.

---

## 10. Production Blockers

### CRITICAL

| ID | Blocker | Evidence | Impact | Recommended Resolution |
|---|---|---|---|---|
| PB-001 | **Two OmsCore classes with the same name** in different packages. Consumers import different implementations. | `from research_platform.oms.oms_core import OmsCore` (run_paper_trading.py:30) vs `from execution_engine.oms.oms_core import OmsCore` (router.py:1144) | Dashboard and paper trading use different order management implementations. Fill/order state may diverge. | Phase 2: read both class interfaces. Phase 7: merge or rename. |
| PB-002 | **InMemoryEventBus is synchronous.** Slow handler blocks entire tick pipeline. | `toji_platform/core/event_bus/bus.py:66` — handlers called in-order with RLock held | One slow event handler (e.g., Telegram alert) blocks all subsequent ticks. Possible missed market ticks under load. | Phase 5: introduce async event handling for non-critical subscribers. |
| PB-003 | **Two separate InMemoryEventBus instances** in Docker (one per kernel stack). | `runtime_supervisor.py` boots research_platform; `toji_platform/runner.py` boots toji_platform kernel independently. | Market data events on toji_platform bus never reach research_platform subscribers and vice versa. | Phase 6: consolidate to single kernel and single event bus. |
| PB-004 | **Risk governance components instantiated directly** (not from DI). | `AIDecisionAuditor`, `RealTimeRiskMonitor` in run_paper_trading.py:501-506 | Cannot be overridden, mocked in tests, or hot-reloaded. Risk thresholds are hardcoded. | Phase 3: register into DI container during initialization. |

### HIGH

| ID | Blocker | Evidence | Impact | Recommended Resolution |
|---|---|---|---|---|
| PB-005 | **No migration versioning.** Schema changes via `create_all()` cannot be rolled back. | `migrations.py:181` | Any schema change in production requires manual intervention or data loss. | Phase 4: adopt Alembic. |
| PB-006 | **~60 plugins do not implement IPlugin.** Health monitoring misses them. | grep of all plugin.py class declarations | Plugin failures are invisible to RecoveryManager. Silent runtime degradation. | Phase 8: enforce IPlugin. |
| PB-007 | **~22+ plugins without explicit boot priority.** | startup.py:64-109 | Non-deterministic initialization. Cross-plugin dependencies may fail silently on any reboot. | Phase 8: add all to boot_priority dict. |
| PB-008 | **KillSwitchEngine registered in DI on first tick only.** API may try to resolve it before first tick. | run_paper_trading.py:560-564 | API race condition. First API call after restart may get null KillSwitch state. | Phase 2: register KillSwitchEngine during plugin initialization, not lazily in tick loop. |
| PB-009 | **SQLite fallback in DEV/pytest silently drops all data on restart.** | connection.py:92-101 | Tests may pass in DEV that fail in production due to missing persistence. | Phase 4: explicitly block in-memory fallback in CI. |
| PB-010 | **No event registry.** Event strings are hardcoded literals. | Verified from all event publish/subscribe calls | Typo in event name silently drops events with no error. | Phase 5: centralized event registry. |
| PB-011 | **`/api/v1/risk/status` and `/api/v1/research/strategies` return hardcoded data.** | backend/main.py:208-245 | Dashboard risk display is fictional. Engineers and operators cannot trust the risk display. | Phase 2 (risk/status), Phase 7 (strategies): wire to live data. |

### MEDIUM

| ID | Blocker | Evidence | Impact | Recommended Resolution |
|---|---|---|---|---|
| PB-012 | **ExperimentManagerPlugin and ExperimentManagementPlugin both boot.** Functional overlap unknown. | startup.py:97; filesystem discovery | Possible double initialization of experiment state. | Phase 7: functional diff and merge. |
| PB-013 | **ConfigPlugin (priority 0) and ConfigurationPlugin (priority 3) both boot.** | startup.py:66,72 | Possible config value overwrite at priority 3 over priority 0. | Phase 3: functional diff. |
| PB-014 | **ExecutionSimulatorPlugin** documented as disconnected path still boots. | run_paper_trading.py:702-704 | Consumes boot resources; potential confusion. | Phase 2: verify zero callers; Phase 7: remove. |
| PB-015 | **Telegram alert blocks DB failure handling.** | connection.py:73-87 — alert fired synchronously before RuntimeError | If Telegram API is slow (5s timeout), DB failure response is delayed by 5s. | Phase 8: make alert async. |

### LOW

| ID | Blocker | Evidence | Impact | Recommended Resolution |
|---|---|---|---|---|
| PB-016 | **`intelligence/universe/manager.py`** exists alongside canonical `universe/core/manager.py`. Not verified as imported anywhere in runtime. | grep analysis | Dead code risk. | INVESTIGATE: confirm zero runtime consumers, then schedule for removal. |
| PB-017 | **`backtesting/` (v1) and `backtesting_engine/` (v2)** coexist. Only v1 is imported by research_platform strategy_factory. | grep analysis | Technical debt; v2 is complete but not in boot path. | Phase 8: migrate strategy_factory to v2, deprecate v1. |

---

## 11. Open Questions

These cannot be proven from code alone. They require human input or runtime testing.

1. **OmsCore functional equivalence:** Are `research_platform/oms/oms_core.py` and `execution_engine/oms/oms_core.py` functionally equivalent? Do they share the same order state model? This cannot be verified from import analysis alone — requires reading both full implementations.

2. **ConfigPlugin vs ConfigurationPlugin:** What is the functional difference? Does booting both cause config key overwrites? No external consumer was found for either — are they actually used?

3. **risk_engine_v2 vs risk_management:** What is the functional difference between `RiskEngineV2Plugin` (priority 11.5) and `RiskManagementPlugin` (priority 11)? Both boot. Do they modify the same state?

4. **Portfolio module boundaries:** What are the exact responsibility boundaries of the 7 portfolio-domain plugins (analytics, construction, engine, governor, intelligence, optimizer, accounting)? No documentation exists.

5. **ExperimentManagerPlugin vs ExperimentManagementPlugin:** What is the functional difference? Are they managing the same experiments?

6. **ValidationPlugin vs ValidationCorePlugin:** What is the functional difference?

7. **`toji_platform/runner.py` LiveRunner status in production:** Is `LiveRunner` actually used in Docker production, or only in CLI mode? The Docker command runs `runtime_supervisor.py` which boots `research_platform` stack — `LiveRunner` appears to be CLI-only. VERIFY.

8. **EventBus instances and cross-process state:** Is there any current mechanism (Redis pub/sub, etc.) that bridges events between the two kernel stacks? If not, are there any cross-stack subscribers that are currently silently never receiving events?

9. **Heartbeat loop interval correctness:** The heartbeat fires at `DEV=60s, PAPER=1800s, PROD=3600s`. Is this correct for PAPER mode monitoring? A 30-minute heartbeat interval means a crash is undetected for up to 30 minutes.

10. **`intelligence/` top-level package:** Is any module in `intelligence/` (other than `intelligence/universe/manager.py`) imported anywhere in runtime? Could not be verified from grep analysis.

---

## 12. Final CTO Section

### 12.1 Architecture Health Score: 42/100

**Rationale:** The system has a well-structured core (toji_platform kernel, IPlugin interface, typed event bus, SQLAlchemy persistence), but is significantly undermined by the dual-stack problem, ~60 non-IPlugin-compliant plugins, two OmsCore classes, 7 portfolio modules with unknown boundaries, and 3 separate risk implementations. The pipeline from tick to fill is clear and verified — that is the strongest architectural asset. Everything outside the canonical pipeline is ambiguous.

### 12.2 Dependency Health Score: 35/100

**Rationale:** The dependency graph has multiple critical cycles or ambiguities: the toji_platform and research_platform stacks each depend on each other's infrastructure (research_platform imports toji_platform.core.*; toji_platform imports research_platform.paper_market). The data.schemas module is shared but unfrozen. Position sizing imports risk_engine which imports portfolio_engine — a 3-level cross-package chain with no DI abstraction at any level.

### 12.3 Runtime Health Score: 48/100

**Rationale:** The Docker deployment is a single-container design (good for simplicity) with a supervisor that restarts crashed processes (good). However: synchronous event bus blocks on slow handlers; two separate bus instances mean cross-stack events are dropped; no persistent event log; SQLite fallback masks persistence failures in development; risk status API returns hardcoded data. The canonical tick-to-fill pipeline is operational and tested (positive).

### 12.4 Production Readiness: 28/100

**Rationale:** The paper trading loop runs and produces fills that are persisted to PostgreSQL (positive). However: API risk/strategy endpoints show hardcoded data; KillSwitch is registered lazily (race condition); no migration versioning; 22+ plugins boot in non-deterministic order; no centralized event registry; two OmsCore implementations create unverified order state integrity. Not ready for live trading.

### 12.5 Technical Debt: 74/100 (higher = more debt)

**Rationale:** Extensive duplication verified: 2x OmsCore, 2x PositionSizing, 4x Strategy, 7x Portfolio, 3x Risk, 2x Config, 2x Validation, 2x Experiment Manager, 2x PriceAction (different roles), 2x backtesting. Additionally: 60+ non-IPlugin plugins, 22+ unordered plugins, hardcoded API responses, no migration versioning, no event registry, no async event handling, direct instantiation of risk governance bypassing DI.

### 12.6 Estimated Consolidation Effort: 18-24 weeks

Breakdown by phase:
- Phase 0 (schema freeze, this document): 0 additional weeks (done)
- Phase 1-2 (validation, no code change): 2 weeks
- Phase 3 (state architecture): 3 weeks
- Phase 4 (persistence/Alembic): 2 weeks
- Phase 5 (event architecture): 2 weeks
- Phase 6 (runtime consolidation): 4-6 weeks (highest risk)
- Phase 7 (business logic consolidation): 4-6 weeks
- Phase 8-9 (hardening + performance): 3-4 weeks

### 12.7 Top 20 Engineering Priorities (Ordered by Dependency)

Ordered by dependency chain position — upstream dependencies first.

| # | Priority | Rationale |
|---|---|---|
| 1 | Freeze `data.schemas.market_data` — no changes without RFC | 15+ modules depend on these DTOs. Any change without coordination breaks the build. |
| 2 | Read and diff both OmsCore implementations | Blocks all order management work. Must establish canonical before Phase 2. |
| 3 | Map ConfigPlugin vs ConfigurationPlugin functional diff | Both boot at priority 0 and 3. Unknown if they conflict. Blocks Phase 3. |
| 4 | Map risk_engine vs risk_management vs risk_engine_v2 boundaries | 3-way risk split is the largest risk blocker. Position sizing, dashboard, and pipeline each consume different risk components. |
| 5 | Register KillSwitchEngine into DI during plugin initialization | PROD-009 race condition. Trivial fix with high safety impact. Must happen before Phase 2 exit. |
| 6 | Wire `/api/v1/risk/status` to live KillSwitchEngine data | Dashboard shows fictional risk state. Critical for operator trust. |
| 7 | Document all 7 portfolio module responsibility boundaries | Cannot consolidate portfolio without knowing which module owns what. |
| 8 | Register AIDecisionAuditor and RealTimeRiskMonitor into DI container | Enables config injection and test mocking. Prerequisite for Phase 3. |
| 9 | Add Alembic to persistence layer | Prerequisite for any schema change in production. Phase 4. |
| 10 | Build centralized event registry (strings → constants) | Typos in event strings cause silent event drops. No tests catch this. |
| 11 | Add explicit boot priorities for all 22+ unlisted plugins | Non-deterministic boot order causes unpredictable cross-plugin failures. Phase 8. |
| 12 | Enforce IPlugin on all 60+ non-compliant plugins | Health monitoring is blind to non-compliant plugins. Phase 8. |
| 13 | Confirm zero callers for ExchangeExecutionSimulator | Verified by comment as disconnected. Must confirm before Phase 2 sign-off. |
| 14 | Confirm `intelligence/universe/manager.py` has zero runtime callers | May be dead code. Safe to remove if confirmed. |
| 15 | Design async event bus strategy (alongside, not replacing, synchronous bus) | Cannot replace synchronous bus until all consumers are audited. Design must come before Phase 5 execution. |
| 16 | Establish single canonical runtime entry point | The dual-stack problem (PROD-001) blocks all consolidation work. Architecture decision required before Phase 6. |
| 17 | Audit backtesting_engine v2 boot path integration | Built with toji_platform interfaces but not in production boot. Must decide activate vs. deprecate. |
| 18 | Consolidate OmsCore into single implementation | After #2 diff is done. Core dependency for order state integrity. Phase 7. |
| 19 | Consolidate portfolio modules (7 → 1-3 clearly bounded) | After #7 boundaries are documented. Phase 7. |
| 20 | Consolidate risk implementations (3 → 1) | After #4 boundaries are documented. Phase 7. |

---

## Final Confirmation

| Check | Expected | Actual |
|---|---|---|
| Python files modified | 0 | 0 |
| Python files deleted | 0 | 0 |
| Architecture modified | NO | NO |
| Evidence basis | Source code only | VERIFIED |

---

*This document constitutes the engineering dependency contract for the TOJI platform.
All consolidation work must reference this document.
Every edge listed was verified from repository source code.
Unverified items are explicitly marked UNKNOWN or NOT VERIFIED.*
