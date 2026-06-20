# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repository implements a **Claude MCP server that integrates with Jira**, enabling natural language ticket management from the CLI and Claude Code. Target environment: Zurich corporate network with `jira.zurich.com` (Jira Server/Data Center).

Architecture and implementation decisions are documented in `arch/` (in Spanish).

## Architecture

Three-layer design — CLI and MCP server never call Claude or Jira directly:

```
[CLI (Typer)]     ──HTTP──►
                            [Service Layer (FastAPI)] → [Claude API (LiteLLM proxy)]
[MCP Server SSE]  ──HTTP──►                           → [Jira REST API v2 — jira.zurich.com]
```

**Key constraints for Zurich environment:**
- Jira is Server/Data Center, not Cloud → REST API v2, PAT Bearer auth, plain-text descriptions
- Claude API goes through the internal LiteLLM proxy (see parent repo `CLAUDE.md` for env vars)
- Corporate firewall requires `REQUESTS_CA_BUNDLE` pointing to `certs/` for Jira calls
- No external services (Atlassian MCP cloud, N8N, Zapier) — all traffic stays inside the network

## Setup

```bash
conda env create -f environment.yml
conda activate claude-mcp-jira
cp .env.example .env  # fill in JIRA_PAT, MCP_API_KEY and uncomment REQUESTS_CA_BUNDLE
```

## Running

```bash
# Full stack (service layer + MCP server)
docker compose up

# Dev mode (no Docker)
uvicorn service.main:app --reload          # service on :8000
python -m jira_mcp.server                  # MCP on :8001

# CLI commands
python cli/main.py create "bug login en producción prioridad alta"
python cli/main.py update PROJ-123 "cambiar prioridad a crítica"
python cli/main.py summarize PROJ-123
python cli/main.py list "mis bugs abiertos de esta semana"
```

## Connect Claude Code to MCP

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "jira": {
      "type": "sse",
      "url": "http://localhost:8001/sse",
      "headers": { "X-API-Key": "<MCP_API_KEY>" }
    }
  }
}
```

For internal deployment replace `localhost:8001` with `mcp-jira.internal:8001`.

## Service layer — endpoints

| Method | Path | Descripción |
|---|---|---|
| `POST` | `/issues` | Crear ticket desde texto libre |
| `PATCH` | `/issues/{key}` | Actualizar ticket desde texto libre |
| `GET` | `/issues/{key}/summary` | Resumen Claude del ticket |
| `POST` | `/issues/search` | Búsqueda NL → JQL controlado (MAX 50) |
| `GET` | `/health` | Health check |

## MCP server — tools

| Tool | Rol mínimo | Descripción |
|---|---|---|
| `create_jira_issue` | dev | Crea ticket desde texto |
| `update_jira_issue` | lead | Actualiza ticket desde texto |
| `get_jira_issue` | dev | Resumen de ticket |
| `search_jira_issues` | dev | Búsqueda NL (máx. 50) |

## Security layers

| Capa | Dónde | Qué hace |
|---|---|---|
| Sanitización | service layer | Elimina tokens, IPs RFC1918, hostnames internos, stack traces |
| Audit log | service layer | JSON-lines con `request_id` UUID por operación |
| JQL builder | service layer | Claude → struct → JQL seguro, MAX_RESULTS=50 |
| Rate limit (NL) | service layer | 30 req/60s por usuario |
| API key + IP allowlist | MCP server | Autenticación + restricción de red |
| RBAC | MCP server | Roles dev/lead/system por API key |
| Rate limit (MCP) | MCP server | 10 calls/60s por API key |
| Pre-validación | MCP server | Rechaza inputs vacíos o >2000 chars |
| Output normalizado | MCP server | LLM solo recibe `{key,status}` o `{key,summary}` |

## Jira Auth (Server/DC)

Generate a PAT at `jira.zurich.com` → Profile → Personal Access Tokens. Set as `JIRA_PAT` in `.env`.

## Corporate certificates

`certs/` contains the Zurich root CA files. Set `REQUESTS_CA_BUNDLE` in `.env`:

- `certs/zurichseguros-rootca-until-2031_03_20.crt` — standard internal services (jira.zurich.com)
- `certs/zurich-ssl-ca.pem` — Zurich SSL inspection CA (ssldecrypt.latam.zurich.com) — required for api-zurich.data-fact.com
- `certs/cacert-workflow-uat.pem` — UAT workflow endpoints
- `certs/localCA.crt` — local dev CA

## Documentation

| Documento | Ubicación |
|---|---|
| Arquitectura general | `arch/design/architecture-overview.md` |
| Plan de implementación | `arch/design/implementation-plan.md` |
| Informe técnico MCP | `arch/reports/mcp-technical-report.md` |
| MCP server config | `jira_mcp/README.md` |
| Evaluaciones externas | `arch/evaluations/` |

## Implementation phases

| Fase | Estado | Descripción |
|---|---|---|
| 1 — Prototipo CLI | ✅ Completa | `cli/main.py` — comando `create` directo |
| 2 — Service Layer | ✅ Completa | FastAPI + sanitización + audit log + timeouts |
| 3 — Comandos completos | ✅ Completa | `update`, `summarize`, `list` + JQL controlado + rate limiter |
| 4 — MCP Server | ✅ Completa | SSE Docker + auth API key + RBAC + rate limit + output normalizado |
| 5 — Observabilidad | Opcional | Prometheus + OpenTelemetry + caching |
