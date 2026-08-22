# TOJI V1 Architecture Document

This document outlines the package layout, dependencies, communication channels, and design patterns of the TOJI quantitative platform.

## Communication Channels
- **Dependency Injection**: Resolves dependencies dynamically at runtime via the `Container`.
- **Event Bus**: Asynchronous, in-memory event dispatching using Pydantic event payloads.

## System Subsystem Inventory
The platform consists of 57 core subdirectories:
- ai_intelligence
- alerting
- alpha_factory
- backtesting_engine
- config
- configuration
- data
- data_platform
- deployment
- execution_engine
- execution_simulator
- experiment_management
- experiment_manager
- feature_platform
- governance
- institutional_memory
- knowledge_graph
- live_trading
- logging
- market_regime
- metrics
- monitoring
- multi_agent
- observability
- oms
- operations_center
- optimization_engine
- paper_dashboard
- paper_market
- paper_trading
- persistence
- platform
- portfolio_analytics
- portfolio_construction
- portfolio_engine
- portfolio_optimizer
- recovery
- reporting
- research_intelligence
- research_lab
- risk_management
- runtime
- scheduler
- scratch
- simulation
- strategy_lab
- strategy_lifecycle
- strategy_registry
- stress_testing
- system_validation
- toji_os
- trade_journal
- validation
- validation_core
- walk_forward
- workflow_orchestration
- workspace

## Structural Dependencies
1. **Infrastructure Layers (Config, Logging, Alerting, Validation, Metrics)**: Bootstrapped first to provide logging and diagnostic coverage.
2. **Data & Analytics**: Market Data Managers, feature stores, and universe sizing.
3. **OMS & Trade Execution**: Position managers, Order Management Systems (OMS), and paper exchanges.
4. **Research & Experimentation**: Strategy registry, experiment manager, and scheduler engine.
