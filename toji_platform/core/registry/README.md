# Registry System

> **Module:** `platform.core.registry`

## Purpose

Typed service registries for the Toji kernel. Every domain concept (agents, strategies, assets, plugins, etc.) is managed through a registry that supports `register()`, `unregister()`, `get()`, `discover()`, `list_all()`, and `validate()`.

## Interfaces

| Interface | Description |
|-----------|-------------|
| `IRegistry[T]` | Generic ABC with full CRUD + discovery |
| `BaseRegistry[T]` | Reusable implementation with validation hooks |

## Typed Registries

| Registry | Domain |
|----------|--------|
| `ResearchModuleRegistry` | Research analysis modules |
| `AgentRegistry` | AI agents |
| `PlaybookRegistry` | Operational playbooks |
| `PluginRegistry` | Loaded plugins |
| `StrategyRegistry` | Strategies |
| `AssetRegistry` | Tradable/researchable assets (asset-agnostic) |
| `MemoryProviderRegistry` | Memory/knowledge providers |
| `AnalyticsProviderRegistry` | Analytics pipeline providers |

## Design Decisions

- **Generic base class** — one implementation powers all registries.
- **Asset-agnostic** — `AssetRegistry` stores assets by string key, never hardcoded to any specific asset.
- **Validation hooks** — subclasses override `_validate_item()` for domain rules.
- **Attribute-match discovery** — `discover(**criteria)` filters by matching item attributes.

## Usage

```python
from platform.core.registry import AssetRegistry

registry = AssetRegistry()
registry.register("AAPL", asset_obj)
registry.has("AAPL")  # True
registry.list_all()    # {"AAPL": asset_obj}
```
