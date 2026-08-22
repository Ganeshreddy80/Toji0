# ARCHITECTURE.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Active  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [Architecture Overview](#architecture-overview)
- [System Layers](#system-layers)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Communication Patterns](#communication-patterns)
- [Infrastructure](#infrastructure)
- [Security Architecture](#security-architecture)
- [Scalability Strategy](#scalability-strategy)
- [Architecture Decision Records](#architecture-decision-records)

---

## Purpose

This document defines the **technical architecture** of the Toji platform, including system layers, component interactions, data flow, and infrastructure design. All engineering decisions should be consistent with the architecture described here.

---

## Architecture Overview

Toji follows a **layered modular architecture** with clear separation of concerns. Each layer communicates through well-defined interfaces, enabling independent development, testing, and deployment.

```
┌──────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                      │
│                   Frontend (Next.js / React)                 │
├──────────────────────────────────────────────────────────────┤
│                        API GATEWAY                           │
│                   FastAPI / REST + WebSocket                 │
├──────────┬───────────┬───────────┬───────────┬───────────────┤
│  Agents  │ Analytics │  Research │  Memory   │   Workflows   │
│  Engine  │  Engine   │  Engine   │  Engine   │   Engine      │
├──────────┴───────────┴───────────┴───────────┴───────────────┤
│                        KERNEL LAYER                          │
│            (platform/ core runtime & event bus)              │
├──────────────────────────────────────────────────────────────┤
│                      MCP TOOL LAYER                          │
│              Model Context Protocol Integrations             │
├──────────────────────────────────────────────────────────────┤
│                      DATA / STORAGE LAYER                    │
│           PostgreSQL • Redis • Vector Store • S3             │
└──────────────────────────────────────────────────────────────┘
```

---

## System Layers

### Presentation Layer
- **Technology:** Next.js / React
- **Responsibility:** User interface, dashboards, research workspace
- **Communication:** REST API + WebSocket for real-time updates

### API Gateway
- **Technology:** FastAPI
- **Responsibility:** Request routing, authentication, rate limiting, validation
- **Protocols:** REST (HTTP/JSON), WebSocket, Server-Sent Events

### Engine Layer
- **Components:** Agents, Analytics, Research, Memory, Workflows
- **Responsibility:** Core business logic and domain operations
- **Pattern:** Each engine is a standalone Python package with defined interfaces

### Kernel Layer
- **Package:** `platform/`
- **Responsibility:** Core runtime bootstrapping, logging, configuration, dependency injection, lifecycle management, registries, and the central Event Bus.
- **Pattern:** Core service container (`TojiKernel`) with modular, loose-coupled subsystems.

### Tool Layer
- **Technology:** Model Context Protocol (MCP)
- **Responsibility:** External tool integration and function calling
- **Pattern:** Tool registry with capability discovery

### Data Layer
- **Technology:** PostgreSQL, Redis, Vector Store
- **Responsibility:** Persistent storage, caching, embedding retrieval
- **Pattern:** Repository pattern with abstracted data access

---

## Component Architecture

### Kernel (`platform/`)
- Central DI container (`Container`) registering core subsystems and plugins.
- Thread-safe central event broker (`InMemoryEventBus`) for publish-subscribe messaging.
- Standardized lifecycle interfaces (`ILifecycle`, `LifecycleManager`) to guarantee startup and shutdown sequence safety.
- Domain registries (Assets, Research, Agents, Playbooks, etc.) derived from a validation-enabled generic registry (`BaseRegistry[T]`).
- Environment-aware structured logging (`StructuredLogger`) and dynamic configuration providers (`ConfigurationManager`).

### Backend (`backend/`)
<!-- TODO: Define in Sprint 1 -->
- FastAPI application factory
- Router modules per domain
- Dependency injection container
- Middleware stack (auth, logging, CORS)

### Agents (`agents/`)
<!-- TODO: Define in Sprint 3 -->
- Base agent interface
- Tool binding and execution
- State management
- Multi-agent coordination

### Memory (`memory/`)
<!-- TODO: Define in Sprint 2 -->
- Short-term conversation memory
- Long-term knowledge persistence
- Embedding pipeline
- Retrieval strategies (similarity, recency, relevance)

### Analytics (`analytics/`)
<!-- TODO: Define in Sprint 4 -->
- Pipeline definition and execution
- Data transformation modules
- Result aggregation
- Visualization adapters

---

## Data Flow

<!-- TODO: Add detailed data flow diagrams in Sprint 1 -->

```
User Request → API Gateway → Router → Engine → Data Layer
                                ↓
                          MCP Tool Layer (if external tool needed)
                                ↓
                          Response → API Gateway → User
```

---

## Communication Patterns

| Pattern | Use Case | Technology |
|---------|----------|------------|
| Request/Response | Standard API calls | REST (HTTP) |
| Pub/Sub | Event broadcasting | Redis Pub/Sub |
| Streaming | Real-time updates | WebSocket / SSE |
| Queue | Background tasks | Redis Queue / Celery |

---

## Infrastructure

### Container Architecture
- Each service runs in its own Docker container
- Docker Compose for local development orchestration
- Kubernetes-ready for production deployment

### Storage Strategy
| Store | Purpose | Persistence |
|-------|---------|-------------|
| PostgreSQL | Relational data | Persistent (volume-mounted) |
| Redis | Cache, sessions, queues | Ephemeral + AOF |
| Vector Store | Embeddings | Persistent |
| S3/MinIO | File storage | Persistent |

---

## Security Architecture

<!-- TODO: Detail in SECURITY.md -->
- JWT-based authentication
- Role-based access control (RBAC)
- API key management for service-to-service
- Encryption at rest and in transit
- Audit logging on all sensitive operations

---

## Scalability Strategy

<!-- TODO: Define scaling thresholds in Sprint 5 -->
- Horizontal scaling via container orchestration
- Database read replicas for query-heavy workloads
- Redis cluster for cache distribution
- Async task processing for compute-intensive operations

---

## Architecture Decision Records

| ADR | Decision | Date | Status |
|-----|----------|------|--------|
| ADR-001 | Use FastAPI for backend API | 2026-06-25 | Accepted |
| ADR-002 | Use PostgreSQL as primary database | 2026-06-25 | Accepted |
| ADR-003 | Use MCP for tool integration protocol | 2026-06-25 | Accepted |
| ADR-004 | Use Docker Compose for local development | 2026-06-25 | Accepted |
| ADR-005 | Design and implement Toji OS Kernel (`platform/`) | 2026-06-25 | Accepted |

<!-- TODO: Add new ADRs as architectural decisions are made -->
