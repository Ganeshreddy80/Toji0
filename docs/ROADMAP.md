# ROADMAP.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Active  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [Release Strategy](#release-strategy)
- [Sprint 0 — Foundation](#sprint-0--foundation)
- [Sprint 1 — Core Backend](#sprint-1--core-backend)
- [Sprint 2 — Memory System](#sprint-2--memory-system)
- [Sprint 3 — Agent Framework](#sprint-3--agent-framework)
- [Sprint 4 — Analytics Engine](#sprint-4--analytics-engine)
- [Sprint 5 — Frontend](#sprint-5--frontend)
- [Future Sprints](#future-sprints)
- [Risk Register](#risk-register)

---

## Purpose

This document outlines the **development roadmap** for the Toji platform, organized by sprint with clear deliverables, dependencies, and acceptance criteria.

---

## Release Strategy

| Version | Sprint | Type | Description |
|---------|--------|------|-------------|
| 0.1.0-alpha | Sprint 0 | Foundation | Project skeleton and documentation |
| 0.2.0-alpha | Sprint 1 | Backend | Core API and database |
| 0.3.0-alpha | Sprint 2 | Memory | Memory system and vector store |
| 0.4.0-beta | Sprint 3 | Agents | Agent framework and MCP |
| 0.5.0-beta | Sprint 4 | Analytics | Analysis pipelines |
| 0.6.0-beta | Sprint 5 | Frontend | Web dashboard |
| 1.0.0 | Sprint 6+ | Release | Production release |

---

## Sprint 0 — Foundation

**Status:** ✅ In Progress  
**Duration:** 1 week  
**Goal:** Establish production-grade project skeleton

### Deliverables
- [x] Repository structure with all directories
- [x] Documentation scaffold (15 documents)
- [x] Development tooling (linting, formatting, pre-commit)
- [x] Docker scaffold with compose file
- [x] GitHub templates (issues, PRs)
- [x] Professional README
- [ ] CI/CD pipeline (GitHub Actions)

---

## Sprint 1 — Core Backend

**Status:** 🔲 Planned  
**Duration:** 2 weeks  
**Goal:** Build the FastAPI backend foundation

### Deliverables
- [ ] FastAPI application factory and project structure
- [ ] Database models with SQLAlchemy/Alembic
- [ ] Authentication (JWT) and authorization (RBAC)
- [ ] Configuration management (Pydantic Settings)
- [ ] Health check and readiness endpoints
- [ ] Structured logging with correlation IDs
- [ ] OpenAPI documentation
- [ ] Unit and integration test suite

### Dependencies
- Sprint 0 complete

---

## Sprint 2 — Memory System

**Status:** 🔲 Planned  
**Duration:** 2 weeks  
**Goal:** Implement persistent memory and knowledge retrieval

### Deliverables
- [ ] Memory schema and data models
- [ ] Vector store integration (pgvector or Qdrant)
- [ ] Embedding pipeline
- [ ] Conversation persistence layer
- [ ] Knowledge retrieval API (similarity, recency, relevance)
- [ ] Memory management CLI tools
- [ ] Test suite with embedding mocks

### Dependencies
- Sprint 1 complete (database layer)

---

## Sprint 3 — Agent Framework

**Status:** 🔲 Planned  
**Duration:** 2 weeks  
**Goal:** Build the agent orchestration framework

### Deliverables
- [ ] Agent base classes and interfaces
- [ ] Tool registry with MCP protocol support
- [ ] Agent lifecycle management (create, run, pause, terminate)
- [ ] Prompt template engine
- [ ] Multi-agent coordination primitives
- [ ] Agent monitoring and observability
- [ ] Test suite with agent mocks

### Dependencies
- Sprint 2 complete (memory system)

---

## Sprint 4 — Analytics Engine

**Status:** 🔲 Planned  
**Duration:** 2 weeks  
**Goal:** Build the data analysis pipeline framework

### Deliverables
- [ ] Pipeline definition DSL
- [ ] Data ingestion connectors
- [ ] Analysis module interfaces
- [ ] Result storage and versioning
- [ ] Reporting engine
- [ ] Experiment tracking
- [ ] Test suite with sample pipelines

### Dependencies
- Sprint 1 complete (backend API)

---

## Sprint 5 — Frontend

**Status:** 🔲 Planned  
**Duration:** 3 weeks  
**Goal:** Build the research dashboard web application

### Deliverables
- [ ] Next.js application scaffold
- [ ] Dashboard layout and navigation
- [ ] Research workspace UI
- [ ] Agent monitoring interface
- [ ] Data visualization components
- [ ] Real-time WebSocket integration
- [ ] Responsive design
- [ ] E2E test suite

### Dependencies
- Sprint 1 complete (backend API)
- Sprint 3 complete (agent framework)

---

## Future Sprints

| Sprint | Focus | Description |
|--------|-------|-------------|
| Sprint 6 | Integration | End-to-end system integration and hardening |
| Sprint 7 | Performance | Optimization, caching, and load testing |
| Sprint 8 | Security | Security audit, penetration testing, compliance |
| Sprint 9 | Documentation | User guides, API docs, tutorials |
| Sprint 10 | Release | Production release preparation and deployment |

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Scope creep in agent framework | High | Medium | Strict sprint boundaries, MVP-first approach |
| Database schema changes late | High | Low | Design review in Sprint 1, migration tooling |
| Frontend complexity underestimated | Medium | Medium | Component library, design system first |
| Integration failures between engines | High | Medium | Contract testing, interface-first design |
| Team velocity lower than planned | Medium | Medium | Buffer sprints, prioritize critical path |
