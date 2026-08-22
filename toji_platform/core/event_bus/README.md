# Event Bus

> **Module:** `platform.core.event_bus`

## Purpose

Central publish/subscribe system for the Toji kernel. All inter-module communication flows through the event bus — no direct coupling between modules.

## Interfaces

| Interface | Description |
|-----------|-------------|
| `IEvent` | Immutable event with `event_id`, `event_type`, `timestamp`, `source`, `payload` |
| `IEventHandler` | Class-based handler with `handle(event)` |
| `IEventBus` | Bus with `publish()`, `subscribe()`, `unsubscribe()`, `has_subscribers()`, `clear()` |

## Implementation

`InMemoryEventBus` — dict-backed, synchronous, single-process bus with wildcard (`"*"`) support.

## System Events

| Event | Fired When |
|-------|-----------|
| `AssetSelected` | An asset is chosen for analysis |
| `MarketDataUpdated` | New market data arrives |
| `ResearchCompleted` | A research module finishes |
| `RiskCalculated` | Risk assessment completes |
| `MemoryUpdated` | Knowledge store changes |
| `StrategyCreated` | A new strategy is defined |
| `BacktestCompleted` | A backtest finishes |
| `DecisionGenerated` | An agent produces a decision |
| `TradeRecorded` | A trade is persisted |
| `LearningCompleted` | A learning cycle finishes |

## Usage

```python
from platform.core.event_bus import InMemoryEventBus, AssetSelected

bus = InMemoryEventBus()
bus.subscribe("system.asset_selected", lambda e: print(e.payload))
bus.publish(AssetSelected(source="user", payload={"symbol": "AAPL"}))
```
