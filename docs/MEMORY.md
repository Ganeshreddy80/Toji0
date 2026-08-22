# MEMORY.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Draft  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [Memory Architecture](#memory-architecture)
- [Memory Types](#memory-types)
- [Storage Backend](#storage-backend)
- [Embedding Pipeline](#embedding-pipeline)
- [Retrieval Strategies](#retrieval-strategies)
- [Memory Lifecycle](#memory-lifecycle)
- [API Design](#api-design)
- [Performance Requirements](#performance-requirements)

---

## Purpose

This document defines the **memory system architecture** for Toji. The memory system provides persistent, searchable, and contextual knowledge storage for agents, research sessions, and analytical workflows.

---

## Memory Architecture

```
┌──────────────────────────────────────────┐
│             Memory Interface             │
├──────────────┬───────────────────────────┤
│  Short-Term  │       Long-Term           │
│  (Session)   │   (Persistent)            │
├──────────────┼───────────────────────────┤
│   Redis      │  PostgreSQL + Vector DB   │
├──────────────┴───────────────────────────┤
│          Embedding Pipeline              │
│      (Chunking → Encoding → Storage)     │
└──────────────────────────────────────────┘
```

---

## Memory Types

### Short-Term Memory
- **Scope:** Single session or conversation
- **Storage:** Redis with TTL
- **Retention:** Session duration + configurable buffer
- **Use Case:** Conversation context, working state

### Long-Term Memory
- **Scope:** Cross-session, persistent
- **Storage:** PostgreSQL + Vector Store
- **Retention:** Indefinite with archival policies
- **Use Case:** Knowledge base, research findings, learned patterns

### Episodic Memory
- **Scope:** Event-based, timestamped
- **Storage:** PostgreSQL with time-series indexing
- **Retention:** Configurable per event type
- **Use Case:** Audit trails, decision logs, interaction history

### Semantic Memory
- **Scope:** Concept-based, graph-structured
- **Storage:** Vector Store + Knowledge Graph
- **Retention:** Indefinite
- **Use Case:** Entity relationships, domain knowledge, concept maps

---

## Storage Backend

<!-- TODO: Implement in Sprint 2 -->

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Session Store | Redis | Fast read/write for active sessions |
| Relational Store | PostgreSQL | Structured memory metadata |
| Vector Store | pgvector / Qdrant | Embedding similarity search |
| Graph Store | *TBD* | Knowledge graph relationships |

---

## Embedding Pipeline

<!-- TODO: Implement in Sprint 2 -->

```
Input Text → Chunking → Preprocessing → Encoding → Vector Storage
                                            ↓
                                      Metadata Indexing
```

### Pipeline Stages
1. **Chunking** — Split content into semantic chunks
2. **Preprocessing** — Clean, normalize, extract metadata
3. **Encoding** — Generate embeddings via model API
4. **Storage** — Persist vectors with metadata
5. **Indexing** — Build retrieval indexes

---

## Retrieval Strategies

<!-- TODO: Implement in Sprint 2 -->

| Strategy | Method | Use Case |
|----------|--------|----------|
| **Similarity** | Cosine similarity on embeddings | Finding related content |
| **Recency** | Time-weighted scoring | Recent conversation context |
| **Relevance** | Hybrid (similarity + recency + importance) | Agent memory retrieval |
| **Keyword** | Full-text search | Exact term matching |

---

## Memory Lifecycle

```
Create → Store → Index → Retrieve → Update → Archive → Delete
```

- **Create:** New memory entries from conversations, analyses, or imports
- **Store:** Persist to appropriate backend
- **Index:** Build search indexes (vector + full-text)
- **Retrieve:** Query by similarity, recency, or keyword
- **Update:** Modify or enrich existing entries
- **Archive:** Move old entries to cold storage
- **Delete:** Permanent removal with audit log

---

## API Design

<!-- TODO: Define endpoints in Sprint 2 -->

```
POST   /api/v1/memory/store        — Store new memory
GET    /api/v1/memory/retrieve     — Retrieve by query
GET    /api/v1/memory/{id}         — Get specific memory
PUT    /api/v1/memory/{id}         — Update memory
DELETE /api/v1/memory/{id}         — Delete memory
POST   /api/v1/memory/search       — Semantic search
GET    /api/v1/memory/session/{id}  — Get session memories
```

---

## Performance Requirements

| Metric | Target |
|--------|--------|
| Store latency | <50ms |
| Retrieval latency | <100ms |
| Search latency (top-10) | <200ms |
| Concurrent sessions | 100+ |
| Storage capacity | 10M+ entries |
