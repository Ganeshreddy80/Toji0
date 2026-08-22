# MASTER_CONTEXT.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Active  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [Project Identity](#project-identity)
- [System Overview](#system-overview)
- [Core Components](#core-components)
- [Technology Decisions](#technology-decisions)
- [Conventions](#conventions)
- [Cross-References](#cross-references)

---

## Purpose

This document serves as the **single source of truth** for the Toji project. Every contributor, agent, and automated system should reference this document to understand the project's identity, architecture, and operating principles.

The Master Context is the canonical reference that all other documentation extends.

---

## Project Identity

| Field | Value |
|-------|-------|
| **Name** | Toji |
| **Type** | Quantitative Research Platform |
| **Language** | Python 3.11+ |
| **License** | MIT |
| **Repository** | `toji` |

---

## System Overview

Toji is a modular quantitative research platform composed of the following subsystems:

- **Backend** — FastAPI-based API layer and core services
- **Frontend** — React/Next.js web dashboard
- **Agents** — AI agent framework with tool integration
- **Analytics** — Data analysis and pipeline engine
- **Research** — Experiment management and reproducibility
- **Memory** — Persistent knowledge and conversation memory
- **MCP** — Model Context Protocol server and tool definitions
- **Workflows** — DAG-based workflow orchestration

---

## Core Components

### Backend
- REST API endpoints
- Authentication and authorization
- Database models and migrations
- Background task processing

### Agents
- Agent base classes and interfaces
- Tool registry
- Agent lifecycle management
- Multi-agent orchestration

### Memory
- Conversation persistence
- Embedding-based retrieval
- Knowledge graph
- Session management

### Analytics
- Data ingestion pipelines
- Analysis modules
- Reporting engine
- Visualization layer

---

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API Framework | FastAPI | Async, auto-docs, type-safe |
| Database | PostgreSQL | Mature, extensible, pgvector support |
| Cache | Redis | Fast, pub/sub capable |
| Containerization | Docker | Industry standard, reproducible |
| Testing | pytest | Extensible, fixture-based |
| Linting | ruff | Fast, comprehensive |

---

## Conventions

- All configuration via environment variables or YAML/TOML files
- All public APIs documented with OpenAPI specs
- All modules type-hinted with mypy strict mode
- All commits follow Conventional Commits
- All branches follow GitFlow naming

---

## Cross-References

| Document | Purpose |
|----------|---------|
| [PROJECT_VISION.md](PROJECT_VISION.md) | Strategic vision and mission |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture |
| [ROADMAP.md](ROADMAP.md) | Development timeline |
| [DATABASE.md](DATABASE.md) | Data models and schema |
| [MEMORY.md](MEMORY.md) | Memory system design |
| [AGENTS.md](AGENTS.md) | Agent specifications |
| [MCP.md](MCP.md) | MCP integration |
| [API.md](API.md) | API contracts |
| [SECURITY.md](SECURITY.md) | Security policies |
| [TESTING.md](TESTING.md) | Testing strategy |
| [CODING_STANDARD.md](CODING_STANDARD.md) | Code standards |
| [TASK_BOARD.md](TASK_BOARD.md) | Sprint tracking |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [NON_NEGOTIABLE_RULES.md](NON_NEGOTIABLE_RULES.md) | Inviolable rules |
