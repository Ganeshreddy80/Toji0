# SECURITY.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Draft  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [Security Principles](#security-principles)
- [Authentication](#authentication)
- [Authorization](#authorization)
- [Secret Management](#secret-management)
- [Data Protection](#data-protection)
- [Network Security](#network-security)
- [Audit and Logging](#audit-and-logging)
- [Vulnerability Management](#vulnerability-management)
- [Incident Response](#incident-response)
- [Compliance](#compliance)

---

## Purpose

This document defines the **security policies, threat model, and protection mechanisms** for the Toji platform. Security is a first-class concern — not an afterthought.

---

## Security Principles

1. **Zero Trust** — Verify every request, trust nothing by default
2. **Least Privilege** — Grant minimum required permissions
3. **Defense in Depth** — Multiple layers of security controls
4. **Secure by Default** — Safe configuration out of the box
5. **Fail Secure** — On error, deny access rather than allow

---

## Authentication

<!-- TODO: Implement in Sprint 1 -->

### User Authentication
| Method | Use Case |
|--------|----------|
| JWT Bearer Token | Web application sessions |
| API Key | Service-to-service communication |
| OAuth 2.0 | Third-party integrations |

### Token Configuration
| Parameter | Value |
|-----------|-------|
| Access token TTL | 15 minutes |
| Refresh token TTL | 7 days |
| Algorithm | RS256 |
| Key rotation | 90 days |

---

## Authorization

<!-- TODO: Implement in Sprint 1 -->

### Role-Based Access Control (RBAC)

| Role | Permissions |
|------|-------------|
| `admin` | Full system access |
| `researcher` | Read/write research data, run agents |
| `analyst` | Read/write analytics, run pipelines |
| `viewer` | Read-only access |
| `service` | Service-to-service API access |

---

## Secret Management

### Rules
- **Never** commit secrets to version control
- **Never** hardcode secrets in source code
- **Never** log secrets or tokens
- **Always** use environment variables or secret manager
- **Always** rotate secrets on schedule

### Secret Storage
| Environment | Method |
|-------------|--------|
| Development | `.env` file (git-ignored) |
| Staging | Environment variables via CI/CD |
| Production | Cloud secret manager (AWS SSM / GCP Secret Manager) |

---

## Data Protection

### Encryption
| Layer | Method |
|-------|--------|
| In Transit | TLS 1.3 |
| At Rest | AES-256 |
| Database | Column-level encryption for PII |
| Backups | Encrypted with separate key |

### Data Classification
| Level | Description | Examples |
|-------|-------------|----------|
| Public | No restriction | Documentation, public APIs |
| Internal | Organization access | Research data, analytics |
| Confidential | Restricted access | User data, credentials |
| Critical | Highest protection | Encryption keys, secrets |

---

## Network Security

<!-- TODO: Configure in Sprint 1 -->

- All services behind reverse proxy
- CORS configured per environment
- Rate limiting on all endpoints
- IP allowlisting for admin endpoints
- No direct database access from public network

---

## Audit and Logging

### Logged Events
| Event | Log Level | Retention |
|-------|-----------|-----------|
| Authentication attempts | INFO | 90 days |
| Authorization failures | WARN | 180 days |
| Data access | INFO | 90 days |
| Configuration changes | INFO | 365 days |
| Security incidents | CRITICAL | Indefinite |

---

## Vulnerability Management

- Dependency scanning via `pip-audit` and Dependabot
- Container scanning for Docker images
- SAST (Static Application Security Testing) in CI
- Regular penetration testing (quarterly)
- Responsible disclosure policy

---

## Incident Response

<!-- TODO: Define in Sprint 8 -->

### Severity Levels
| Level | Description | Response Time |
|-------|-------------|---------------|
| P0 — Critical | Data breach, system compromise | Immediate |
| P1 — High | Service outage, auth bypass | 1 hour |
| P2 — Medium | Vulnerability discovered | 24 hours |
| P3 — Low | Minor security improvement | Sprint backlog |

---

## Compliance

<!-- TODO: Assess requirements in Sprint 8 -->

| Standard | Status | Notes |
|----------|--------|-------|
| OWASP Top 10 | Planned | Assess in Sprint 8 |
| SOC 2 | Future | Evaluate requirement |
| GDPR | Planned | Data handling policies |
