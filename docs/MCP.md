# MCP.md

> **Version:** 0.1.0  
> **Last Updated:** 2026-06-25  
> **Status:** Draft  
> **Owner:** Toji Core Team  

---

## Table of Contents

- [Purpose](#purpose)
- [MCP Overview](#mcp-overview)
- [Architecture](#architecture)
- [Server Configuration](#server-configuration)
- [Tool Definitions](#tool-definitions)
- [Resource Definitions](#resource-definitions)
- [Prompt Definitions](#prompt-definitions)
- [Transport Layer](#transport-layer)
- [Security](#security)
- [Development Guide](#development-guide)

---

## Purpose

This document defines the **Model Context Protocol (MCP) integration** for the Toji platform. MCP provides the standardized protocol layer through which agents discover and interact with tools, resources, and prompts.

---

## MCP Overview

MCP is the **tool integration protocol** for Toji. It enables:

- **Tool Discovery** — Agents discover available tools and their capabilities
- **Structured Invocation** — Type-safe tool calls with validated inputs/outputs
- **Resource Access** — Standardized access to data and file resources
- **Prompt Templates** — Reusable prompt definitions with parameter binding

---

## Architecture

```
┌─────────────────────────────────┐
│          Agent Runtime          │
├─────────────────────────────────┤
│          MCP Client             │
├─────────────────────────────────┤
│     Transport (stdio / SSE)     │
├─────────────────────────────────┤
│          MCP Server             │
├──────────┬──────────┬───────────┤
│  Tools   │ Resources│  Prompts  │
└──────────┴──────────┴───────────┘
```

---

## Server Configuration

<!-- TODO: Implement in Sprint 3 -->

```json
{
  "mcpServers": {
    "toji-tools": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "env": {
        "TOJI_ENV": "development"
      }
    }
  }
}
```

---

## Tool Definitions

<!-- TODO: Define tools in Sprint 3 -->

| Tool | Description | Input | Output |
|------|-------------|-------|--------|
| *TBD* | *TBD* | *TBD* | *TBD* |

### Tool Registration Pattern

```python
# Placeholder: Implement in Sprint 3
@mcp_server.tool()
async def tool_name(param: str) -> str:
    """Tool description."""
    pass
```

---

## Resource Definitions

<!-- TODO: Define resources in Sprint 3 -->

| Resource | URI Pattern | Description |
|----------|------------|-------------|
| *TBD* | *TBD* | *TBD* |

---

## Prompt Definitions

<!-- TODO: Define prompts in Sprint 3 -->

| Prompt | Description | Parameters |
|--------|-------------|------------|
| *TBD* | *TBD* | *TBD* |

---

## Transport Layer

| Transport | Use Case | Configuration |
|-----------|----------|---------------|
| **stdio** | Local development, subprocess tools | Default |
| **SSE** | Remote services, HTTP-based tools | Production |

---

## Security

- Tool execution sandboxed with limited permissions
- Input validation on all tool parameters
- Output sanitization before returning to agents
- Rate limiting per tool per agent
- Audit logging on all tool invocations

---

## Development Guide

### Adding a New Tool

1. Define tool function in `mcp/tools/`
2. Register with MCP server
3. Add input/output schemas
4. Write unit tests
5. Document in this file

### Testing Tools

```bash
# Placeholder: Implement in Sprint 3
make test-mcp
```
