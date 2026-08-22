# API.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Draft  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [API Design Principles](#api-design-principles)
- [Base Configuration](#base-configuration)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
- [Error Handling](#error-handling)
- [Pagination](#pagination)
- [Rate Limiting](#rate-limiting)
- [Versioning Strategy](#versioning-strategy)
- [WebSocket API](#websocket-api)

---

## Purpose

This document defines the **API specifications and contracts** for the Toji platform. All public-facing APIs must conform to the standards described here.

---

## API Design Principles

1. **RESTful** — Resources mapped to URIs with standard HTTP methods
2. **JSON-First** — All request/response bodies in JSON format
3. **Consistent** — Uniform patterns across all endpoints
4. **Documented** — OpenAPI 3.1 spec generated from code
5. **Versioned** — URL-based versioning (`/api/v1/...`)
6. **Validated** — Input validation via Pydantic models
7. **Paginated** — All list endpoints support cursor-based pagination

---

## Base Configuration

```
Base URL:     http://localhost:8000/api/v1
Content-Type: application/json
Accept:       application/json
```

---

## Authentication

<!-- TODO: Implement in Sprint 1 -->

| Method | Use Case | Header |
|--------|----------|--------|
| JWT Bearer | User sessions | `Authorization: Bearer <token>` |
| API Key | Service-to-service | `X-API-Key: <key>` |

### Auth Endpoints

```
POST /api/v1/auth/login       — Authenticate and receive JWT
POST /api/v1/auth/refresh     — Refresh JWT token
POST /api/v1/auth/logout      — Invalidate session
```

---

## Endpoints

### Health

```
GET /api/v1/health            — Service health check
GET /api/v1/health/ready      — Readiness probe
GET /api/v1/health/live       — Liveness probe
```

### Users

<!-- TODO: Implement in Sprint 1 -->

```
GET    /api/v1/users          — List users
POST   /api/v1/users          — Create user
GET    /api/v1/users/{id}     — Get user by ID
PUT    /api/v1/users/{id}     — Update user
DELETE /api/v1/users/{id}     — Delete user
```

### Agents

<!-- TODO: Implement in Sprint 3 -->

```
GET    /api/v1/agents         — List agents
POST   /api/v1/agents         — Create agent
GET    /api/v1/agents/{id}    — Get agent details
PUT    /api/v1/agents/{id}    — Update agent
DELETE /api/v1/agents/{id}    — Delete agent
POST   /api/v1/agents/{id}/run    — Execute agent
GET    /api/v1/agents/{id}/status — Agent status
```

### Memory

<!-- TODO: Implement in Sprint 2 -->

```
POST   /api/v1/memory/store        — Store memory
GET    /api/v1/memory/retrieve      — Retrieve memories
POST   /api/v1/memory/search        — Semantic search
GET    /api/v1/memory/{id}          — Get specific memory
PUT    /api/v1/memory/{id}          — Update memory
DELETE /api/v1/memory/{id}          — Delete memory
```

### Analytics

<!-- TODO: Implement in Sprint 4 -->

```
POST   /api/v1/analytics/run       — Execute analysis
GET    /api/v1/analytics/results    — List results
GET    /api/v1/analytics/{id}       — Get result details
```

---

## Error Handling

### Standard Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error description",
    "details": [],
    "request_id": "uuid-v4"
  }
}
```

### HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET, PUT |
| 201 | Created | Successful POST |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Validation error |
| 401 | Unauthorized | Missing or invalid auth |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Duplicate resource |
| 422 | Unprocessable | Semantic validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Internal error |

---

## Pagination

### Cursor-Based Pagination

```json
{
  "data": [...],
  "pagination": {
    "cursor": "eyJpZCI6MTAwfQ==",
    "has_more": true,
    "limit": 20
  }
}
```

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | null | Pagination cursor |
| `limit` | integer | 20 | Items per page (max 100) |
| `sort` | string | "created_at" | Sort field |
| `order` | string | "desc" | Sort order (asc/desc) |

---

## Rate Limiting

<!-- TODO: Configure in Sprint 1 -->

| Tier | Requests/Minute | Burst |
|------|----------------|-------|
| Free | 60 | 10 |
| Standard | 300 | 50 |
| Premium | 1000 | 100 |

### Rate Limit Headers

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1719331200
```

---

## Versioning Strategy

- URL-based versioning: `/api/v1/`, `/api/v2/`
- Breaking changes require new version
- Old versions supported for minimum 6 months
- Deprecation headers on sunset versions

---

## WebSocket API

<!-- TODO: Implement in Sprint 5 -->

```
ws://localhost:8000/ws/v1/events     — Real-time event stream
ws://localhost:8000/ws/v1/agents/{id} — Agent live output
```
