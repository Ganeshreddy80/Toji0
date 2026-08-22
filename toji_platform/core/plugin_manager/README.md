# Plugin Manager

> **Module:** `platform.core.plugin_manager`

## Purpose

Framework for extending the Toji platform with plugins. Plugins declare dependencies and are initialised in topological order via Kahn's algorithm.

## Interfaces

| Interface | Description |
|-----------|-------------|
| `IPlugin` | Lifecycle contract: `plugin_id`, `name`, `version`, `dependencies`, `initialize()`, `shutdown()`, `health_check()` |
| `IPluginManager` | Manager: `load()`, `unload()`, `get()`, `list_plugins()`, `initialize_all()`, `shutdown_all()` |

## Future Plugins (framework only)

Crypto · Stocks · Forex · News · Sentiment · Binance · TradingView · Telegram · Open Cowork · MCP

## Usage

```python
from platform.core.plugin_manager import PluginManager

manager = PluginManager()
manager.load(my_plugin)
manager.initialize_all()  # respects dependency order
manager.shutdown_all()     # reverse order
```
