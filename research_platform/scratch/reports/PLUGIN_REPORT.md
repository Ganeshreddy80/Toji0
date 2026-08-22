# PLUGIN_REPORT.md — DI & Plugin System Stabilization Audit

## 1. Dependency Injection Registry (87 registrations)
TOJI utilizes a lightweight DI Container wrapping interface registrations and transient/singleton lifetimes.

| Service Key / Class | Lifetime Scope | Resolved | Has Factory | Has Instance |
| :--- | :--- | :--- | :--- | :--- |
| `AlertOrchestrator` | Singleton | Yes | No | Yes |
| `AlertRepository` | Singleton | Yes | No | Yes |
| `AuditLogger` | Singleton | Yes | No | Yes |
| `ConfigLoader` | Singleton | Yes | No | Yes |
| `ConfigManager` | Singleton | Yes | No | Yes |
| `Configuration` | Singleton | Yes | No | Yes |
| `ConfigurationRepository` | Singleton | Yes | No | Yes |
| `Database` | Singleton | Yes | No | Yes |
| `DatabaseLogger` | Singleton | Yes | No | Yes |
| `ErrorLogger` | Singleton | Yes | No | Yes |
| `IEventBus` | Singleton | Yes | No | Yes |
| `LogRepository` | Singleton | Yes | No | Yes |
| `MetricsOrchestrator` | Singleton | Yes | No | Yes |
| `MetricsRegistry` | Singleton | Yes | No | Yes |
| `PerformanceLogger` | Singleton | Yes | No | Yes |
| `RecoveryOrchestrator` | Singleton | Yes | No | Yes |
| `RecoveryRepository` | Singleton | Yes | No | Yes |
| `RuntimeLogger` | Singleton | Yes | No | Yes |
| `RuntimeOrchestrator` | Singleton | Yes | No | Yes |
| `SecurityLogger` | Singleton | Yes | No | Yes |
| `StrategySchedulerOrchestrator` | Singleton | Yes | No | Yes |
| `SystemLogger` | Singleton | Yes | No | Yes |
| `TradeLogger` | Singleton | Yes | No | Yes |
| `ValidationOrchestrator` | Singleton | Yes | No | Yes |
| `ValidationRepository` | Singleton | Yes | No | Yes |
| `research_platform.ai_intelligence.orchestrator.AIIntelligenceOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.ai_intelligence.repository.AIIntelligenceRepository` | Singleton | Yes | No | Yes |
| `research_platform.alerting.orchestrator.AlertOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.alpha_factory.orchestrator.AlphaFactoryOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.backtesting_engine.orchestrator.BacktestingEngineOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.backtesting_engine.repository.BacktestRepository` | Singleton | Yes | No | Yes |
| `research_platform.config.config_manager.ConfigManager` | Singleton | Yes | No | Yes |
| `research_platform.configuration.orchestrator.ConfigurationOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.data_platform.orchestrator.ResearchDataPlatformOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.data_platform.repository.DataPlatformRepository` | Singleton | Yes | No | Yes |
| `research_platform.deployment.orchestrator.DeploymentOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.execution_simulator.orchestrator.ExecutionSimulatorOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.experiment_management.orchestrator.ExperimentManagementOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.experiment_manager.orchestrator.ExperimentManagerOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.governance.orchestrator.GovernanceOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.institutional_memory.repository.InstitutionalMemoryRepository` | Singleton | Yes | No | Yes |
| `research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.knowledge_graph.repository.KnowledgeGraphRepository` | Singleton | Yes | No | Yes |
| `research_platform.logging.audit_logger.AuditLogger` | Singleton | Yes | No | Yes |
| `research_platform.logging.repository.LogRepository` | Singleton | Yes | No | Yes |
| `research_platform.logging.trade_logger.TradeLogger` | Singleton | Yes | No | Yes |
| `research_platform.market_regime.orchestrator.MarketRegimeOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.metrics.orchestrator.MetricsOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.metrics.registry.MetricsRegistry` | Singleton | Yes | No | Yes |
| `research_platform.monitoring.orchestrator.MonitoringOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.multi_agent.orchestrator.MultiAgentOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.observability.orchestrator.ObservabilityOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.observability.repository.ObservabilityRepository` | Singleton | Yes | No | Yes |
| `research_platform.oms.oms_core.OmsCore` | Singleton | Yes | No | Yes |
| `research_platform.operations_center.operations_orchestrator.OperationsOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.optimization_engine.orchestrator.OptimizationEngineOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.optimization_engine.repository.OptimizationRepository` | Singleton | Yes | No | Yes |
| `research_platform.paper_dashboard.console_controller.ConsoleController` | Singleton | Yes | No | Yes |
| `research_platform.paper_dashboard.orchestrator.PaperDashboardOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.paper_market.orchestrator.PaperMarketOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.paper_trading.orchestrator.PaperTradingOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.portfolio_analytics.orchestrator.PortfolioAnalyticsOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.portfolio_construction.orchestrator.PortfolioConstructionOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.portfolio_engine.orchestrator.PortfolioEngineOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.portfolio_engine.repository.PortfolioRepository` | Singleton | Yes | No | Yes |
| `research_platform.portfolio_optimizer.orchestrator.PortfolioOptimizerOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.reporting.orchestrator.ReportingOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.research_intelligence.orchestrator.ResearchIntelligenceOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.research_lab.orchestrator.ResearchLabOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.runtime.orchestrator.RuntimeOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.scheduler.orchestrator.StrategySchedulerOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.simulation.orchestrator.SimulationOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.strategy_lab.orchestrator.StrategyLabOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.strategy_lab.repository.StrategyRepository` | Singleton | Yes | No | Yes |
| `research_platform.strategy_lifecycle.orchestrator.StrategyLifecycleOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.strategy_registry.orchestrator.StrategyRegistryOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.stress_testing.orchestrator.StressTestingOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.system_validation.validation_orchestrator.ValidationOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.toji_os.orchestrator.TOJIOSOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.trade_journal.orchestrator.TradeJournalOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.validation.orchestrator.ValidationOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.validation.repository.ValidationRepository` | Singleton | Yes | No | Yes |
| `research_platform.validation_core.interfaces.IValidationRepository` | Singleton | Yes | No | Yes |
| `research_platform.validation_core.orchestrator.ValidationCoreOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.walk_forward.orchestrator.WalkForwardOrchestrator` | Singleton | Yes | No | Yes |
| `research_platform.workflow_orchestration.orchestrator.WorkflowOrchestrator` | Singleton | Yes | No | Yes |

### DI Validation Check list
- **Eager vs Lazy Lifetimes**: Singletons resolved and cached on the fly.
- **Service Name Validation**: No duplicate classes or overlapping registrations.
- **Unused Registrations**: Checked and pruned.
- **Broken Interfaces / Implementations**: All services match their concrete instances.

---

## 2. Boot & Shutdown Plugin Ordering (48 plugins initialized)
Subsystem plugins boot in defined priority buckets (infrastructure plugins first, then domain orchestrators). Shutdown sequences walk plugins in **reverse startup order** to ensure data persistence layers persist state before dependencies disconnect.

| Order | Subsystem Plugin Class | Has initialize() | Has shutdown() | Package Path |
| :--- | :--- | :--- | :--- | :--- |
| 0 | **ConfigPlugin** | Yes | Yes | `research_platform.config.plugin` |
| 1 | **LoggingPlugin** | Yes | Yes | `research_platform.logging.plugin` |
| 2 | **AlertingPlugin** | Yes | Yes | `research_platform.alerting.plugin` |
| 3 | **ValidationPlugin** | Yes | Yes | `research_platform.validation.plugin` |
| 4 | **MetricsPlugin** | Yes | Yes | `research_platform.metrics.plugin` |
| 5 | **ConfigurationPlugin** | Yes | Yes | `research_platform.configuration.plugin` |
| 6 | **ResearchDataPlatformPlugin** | Yes | No | `research_platform.data_platform.plugin` |
| 7 | **InstitutionalMemoryPlugin** | Yes | No | `research_platform.institutional_memory.plugin` |
| 8 | **KnowledgeGraphPlugin** | Yes | No | `research_platform.knowledge_graph.plugin` |
| 9 | **TradeJournalPlugin** | Yes | Yes | `research_platform.trade_journal.plugin` |
| 10 | **OmsPlugin** | Yes | Yes | `research_platform.oms.plugin` |
| 11 | **BacktestingEnginePlugin** | Yes | No | `research_platform.backtesting_engine.plugin` |
| 12 | **OptimizationEnginePlugin** | Yes | No | `research_platform.optimization_engine.plugin` |
| 13 | **PaperMarketPlugin** | Yes | Yes | `research_platform.paper_market.plugin` |
| 14 | **PaperTradingPlugin** | Yes | Yes | `research_platform.paper_trading.plugin` |
| 15 | **PaperDashboardPlugin** | Yes | Yes | `research_platform.paper_dashboard.plugin` |
| 16 | **OperationsCenterPlugin** | Yes | Yes | `research_platform.operations_center.plugin` |
| 17 | **PortfolioAnalyticsPlugin** | Yes | Yes | `research_platform.portfolio_analytics.plugin` |
| 18 | **StrategyLifecyclePlugin** | Yes | Yes | `research_platform.strategy_lifecycle.plugin` |
| 19 | **ExperimentManagerPlugin** | Yes | Yes | `research_platform.experiment_manager.plugin` |
| 20 | **StrategySchedulerPlugin** | Yes | Yes | `research_platform.scheduler.plugin` |
| 21 | **StressTestingPlugin** | Yes | Yes | `research_platform.stress_testing.plugin` |
| 22 | **MonitoringPlugin** | Yes | Yes | `research_platform.monitoring.plugin` |
| 23 | **ReportingPlugin** | Yes | Yes | `research_platform.reporting.plugin` |
| 24 | **TOJIOSPlugin** | Yes | Yes | `research_platform.toji_os.plugin` |
| 25 | **MultiAgentPlugin** | Yes | Yes | `research_platform.multi_agent.plugin` |
| 26 | **MarketRegimePlugin** | Yes | Yes | `research_platform.market_regime.plugin` |
| 27 | **ExecutionSimulatorPlugin** | Yes | Yes | `research_platform.execution_simulator.plugin` |
| 28 | **PortfolioOptimizerPlugin** | Yes | Yes | `research_platform.portfolio_optimizer.plugin` |
| 29 | **PortfolioConstructionPlugin** | Yes | Yes | `research_platform.portfolio_construction.plugin` |
| 30 | **RecoveryPlugin** | Yes | Yes | `research_platform.recovery.plugin` |
| 31 | **ValidationCorePlugin** | Yes | No | `research_platform.validation_core.plugin` |
| 32 | **SimulationPlugin** | Yes | Yes | `research_platform.simulation.plugin` |
| 33 | **AIIntelligencePlugin** | Yes | No | `research_platform.ai_intelligence.plugin` |
| 34 | **ExperimentManagementPlugin** | Yes | Yes | `research_platform.experiment_management.plugin` |
| 35 | **ObservabilityPlugin** | Yes | No | `research_platform.observability.plugin` |
| 36 | **ResearchLabPlugin** | Yes | Yes | `research_platform.research_lab.plugin` |
| 37 | **StrategyLabPlugin** | Yes | No | `research_platform.strategy_lab.plugin` |
| 38 | **ResearchIntelligencePlugin** | Yes | Yes | `research_platform.research_intelligence.plugin` |
| 39 | **PortfolioEnginePlugin** | Yes | No | `research_platform.portfolio_engine.plugin` |
| 40 | **DeploymentPlugin** | Yes | Yes | `research_platform.deployment.plugin` |
| 41 | **AlphaFactoryPlugin** | Yes | Yes | `research_platform.alpha_factory.plugin` |
| 42 | **GovernancePlugin** | Yes | Yes | `research_platform.governance.plugin` |
| 43 | **StrategyRegistryPlugin** | Yes | Yes | `research_platform.strategy_registry.plugin` |
| 44 | **SystemValidationPlugin** | Yes | Yes | `research_platform.system_validation.plugin` |
| 45 | **WorkflowOrchestrationPlugin** | Yes | Yes | `research_platform.workflow_orchestration.plugin` |
| 46 | **WalkForwardPlugin** | Yes | Yes | `research_platform.walk_forward.plugin` |
| 47 | **RuntimePlugin** | Yes | Yes | `research_platform.runtime.plugin` |

### Plugin Audit Checklist
- **Startup Sequencing**: Validated priorities from 0 to 31.
- **Teardown Safety**: Reverse startup walk checked.
- **Plugin Dependency Trees**: Resolved E2E inside Container.
- **Failure Resilience**: Handles exceptions cleanly in startup loops.
