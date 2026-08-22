# Lifecycle Manager

> **Module:** `platform.core.lifecycle`

## Purpose

Ordered startup and shutdown of kernel components with aggregated health checks.

## Behaviour

- **Startup**: components started in registration order.
- **Shutdown**: components stopped in reverse order (LIFO).
- **Health**: runs `check_health()` on all components implementing `IHealthCheck`.
- **Error handling**: shutdown collects all errors rather than failing on the first.

## Usage

```python
from platform.core.lifecycle import LifecycleManager

lm = LifecycleManager()
lm.register(my_component)
lm.start_all()
lm.health_check()
lm.stop_all()
```
