# Dependency Injection Container

> **Module:** `platform.core.dependency_injection`

## Purpose

Lightweight DI container supporting eager singletons, lazy singletons, and transient factories.

## Registration Modes

| Mode | When | How |
|------|------|-----|
| Eager singleton | Instance known at registration | `container.register(IService, instance=svc)` |
| Lazy singleton | Build on first resolve | `container.register(IService, factory=lambda: Svc())` |
| Transient | New instance per resolve | `container.register(IService, factory=fn, singleton=False)` |

## Usage

```python
from platform.core.dependency_injection import Container

c = Container()
c.register("config", instance=config_obj)
c.register("db", factory=create_db_pool)
c.resolve("config")  # returns config_obj
c.resolve("db")       # calls create_db_pool() once, caches result
```
