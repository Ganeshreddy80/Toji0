# DATABASE.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Draft  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [Database Strategy](#database-strategy)
- [Storage Architecture](#storage-architecture)
- [Schema Design](#schema-design)
- [Migration Strategy](#migration-strategy)
- [Indexing Strategy](#indexing-strategy)
- [Backup and Recovery](#backup-and-recovery)
- [Performance Considerations](#performance-considerations)

---

## Purpose

This document defines the **database architecture, schema design, and data management strategy** for the Toji platform. It covers all persistent storage systems including relational databases, caches, and vector stores.

---

## Database Strategy

| Store | Technology | Purpose |
|-------|-----------|---------|
| **Primary** | PostgreSQL 15+ | Relational data, transactions, ACID compliance |
| **Cache** | Redis 7+ | Session cache, pub/sub, task queues |
| **Vector** | pgvector / Qdrant | Embedding storage, similarity search |
| **Object** | S3 / MinIO | File and artifact storage |

---

## Storage Architecture

```
┌────────────────────────────────────────┐
│            Application Layer           │
├──────────┬──────────┬──────────┬───────┤
│  SQLAlchemy  │  Redis  │  Vector  │ S3  │
│  (ORM)       │  Client │  Client  │ SDK │
├──────────┴──────────┴──────────┴───────┤
│       Connection Pool / Proxy          │
├──────────┬──────────┬──────────┬───────┤
│ PostgreSQL │  Redis  │  Qdrant  │ MinIO│
└──────────┴──────────┴──────────┴───────┘
```

---

## Schema Design

### Core Tables

<!-- TODO: Define in Sprint 1 -->

#### Users
```sql
-- Placeholder: Define in Sprint 1
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Sessions
```sql
-- Placeholder: Define in Sprint 1
```

#### Agents
```sql
-- Placeholder: Define in Sprint 3
```

#### Memory
```sql
-- Placeholder: Define in Sprint 2
```

#### Analytics
```sql
-- Placeholder: Define in Sprint 4
```

---

## Migration Strategy

- **Tool:** Alembic (SQLAlchemy migrations)
- **Convention:** One migration per schema change
- **Naming:** `YYYY_MM_DD_HHMM_description.py`
- **Review:** All migrations reviewed before merge
- **Rollback:** Every migration must have a downgrade path

---

## Indexing Strategy

<!-- TODO: Define indexes per table in Sprint 1 -->

| Table | Column(s) | Index Type | Rationale |
|-------|-----------|-----------|-----------|
| *TBD* | *TBD* | *TBD* | *TBD* |

---

## Backup and Recovery

<!-- TODO: Define backup strategy in Sprint 1 -->

| Component | Strategy | Frequency | Retention |
|-----------|----------|-----------|-----------|
| PostgreSQL | pg_dump | Daily | 30 days |
| Redis | RDB + AOF | Continuous | 7 days |
| Vector Store | Snapshot | Daily | 30 days |

---

## Performance Considerations

- Connection pooling via PgBouncer or SQLAlchemy pool
- Read replicas for query-heavy workloads
- Materialized views for complex aggregations
- Partitioning for time-series data
- Query monitoring and slow query logging
