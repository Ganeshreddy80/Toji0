# CODING_STANDARD.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Active  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [Language Standards](#language-standards)
- [Code Style](#code-style)
- [Type Hints](#type-hints)
- [Documentation](#documentation)
- [Naming Conventions](#naming-conventions)
- [Module Structure](#module-structure)
- [Error Handling](#error-handling)
- [Logging](#logging)
- [Configuration](#configuration)
- [Tooling](#tooling)

---

## Purpose

This document defines the **code style, engineering standards, and best practices** for the Toji platform. All contributors must follow these standards.

---

## Language Standards

| Parameter | Standard |
|-----------|----------|
| Python version | 3.11+ |
| Type checking | mypy (strict mode) |
| Linting | ruff |
| Formatting | black (88 char line length) |
| Import sorting | isort (black-compatible profile) |

---

## Code Style

### General Rules
- Maximum line length: **88 characters** (black default)
- Use **f-strings** for string formatting
- Prefer **pathlib** over os.path
- Use **dataclasses** or **Pydantic models** for structured data
- Prefer **composition** over inheritance
- Avoid **global state** — use dependency injection

### Imports

```python
# Standard library
import os
from pathlib import Path

# Third-party
import fastapi
from pydantic import BaseModel

# Local
from toji.core import config
from toji.models import User
```

---

## Type Hints

### Requirements
- All public functions must have type hints
- All class attributes must be typed
- No bare `Any` types without justification comment
- Use `TypeAlias` for complex types
- Use `Protocol` for structural typing

### Examples

```python
# Good
def get_user(user_id: UUID) -> User | None:
    ...

# Bad — missing types
def get_user(user_id):
    ...
```

---

## Documentation

### Docstring Style: Google

```python
def calculate_score(
    values: list[float],
    weights: list[float] | None = None,
) -> float:
    """Calculate the weighted score from a list of values.

    Args:
        values: List of numeric values to score.
        weights: Optional weights for each value. If None,
            equal weights are applied.

    Returns:
        The calculated weighted score.

    Raises:
        ValueError: If values and weights have different lengths.

    Example:
        >>> calculate_score([1.0, 2.0, 3.0])
        2.0
    """
```

### Module Docstrings
Every module must have a module-level docstring explaining its purpose.

---

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Module | snake_case | `data_loader.py` |
| Class | PascalCase | `DataLoader` |
| Function | snake_case | `load_data()` |
| Variable | snake_case | `user_count` |
| Constant | UPPER_SNAKE | `MAX_RETRIES` |
| Private | _prefixed | `_internal_method()` |
| Type alias | PascalCase | `UserId = UUID` |
| Test | test_should_* | `test_should_return_user()` |

---

## Module Structure

```python
"""Module docstring describing purpose."""

# Standard library imports
# Third-party imports
# Local imports

# Constants
MAX_RETRIES: int = 3
DEFAULT_TIMEOUT: float = 30.0

# Type aliases
UserId = UUID


# Classes
class MyService:
    """Service description."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def public_method(self) -> Result:
        """Public method with docstring."""
        ...

    def _private_method(self) -> None:
        """Private method."""
        ...


# Module-level functions
def helper_function() -> None:
    """Helper function with docstring."""
    ...
```

---

## Error Handling

### Custom Exceptions
- Define domain-specific exceptions
- Inherit from a project base exception
- Include context in error messages

```python
class TojiError(Exception):
    """Base exception for Toji."""

class NotFoundError(TojiError):
    """Resource not found."""

class ValidationError(TojiError):
    """Input validation failed."""
```

### Rules
- Never catch bare `Exception` without re-raising
- Log errors with full context
- Use structured error responses for API errors
- Fail fast on configuration errors

---

## Logging

### Standards
- Use **structured logging** (JSON format in production)
- Include **correlation IDs** for request tracing
- Log at appropriate levels:

| Level | Usage |
|-------|-------|
| DEBUG | Detailed diagnostic info |
| INFO | Normal operations, state changes |
| WARNING | Unexpected but handled situations |
| ERROR | Failures that need attention |
| CRITICAL | System-level failures |

### Rules
- Never log sensitive data (passwords, tokens, PII)
- Always include context (user_id, request_id, etc.)
- Use parameterized logging (not f-strings in log calls)

---

## Configuration

### Rules
- All configuration via environment variables or YAML/TOML files
- Use **Pydantic Settings** for type-safe config
- Never hardcode values — use constants or config
- Validate all configuration at startup
- Fail fast on missing required configuration

---

## Tooling

### Pre-commit Hooks
```yaml
# Enforced on every commit
- ruff check (lint)
- ruff format (format)
- mypy (type check)
- detect-secrets (secret scanning)
```

### Commands
```bash
make lint       # Run all linters
make format     # Auto-format code
make typecheck  # Run mypy
make test       # Run test suite
make check      # Run all checks (lint + typecheck + test)
```
