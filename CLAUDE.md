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
[MCP Server]      ──HTTP──►                           → [Jira REST API v2 — jira.zurich.com]
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
cp .env.example .env  # fill in JIRA_PAT and uncomment REQUESTS_CA_BUNDLE
```

## Running

```bash
# Via service layer
docker compose up

# Dev mode (no Docker)
uvicorn service.main:app --reload

# CLI commands
python cli/main.py create "bug login en producción prioridad alta"
python cli/main.py update PROJ-123 "cambiar prioridad a crítica"
python cli/main.py summarize PROJ-123
python cli/main.py list "mis bugs abiertos de esta semana"
```

## Service layer — endpoints

| Method | Path | Descripción |
|---|---|---|
| `POST` | `/issues` | Crear ticket desde texto libre |
| `PATCH` | `/issues/{key}` | Actualizar ticket desde texto libre |
| `GET` | `/issues/{key}/summary` | Resumen Claude del ticket |
| `POST` | `/issues/search` | Búsqueda NL → JQL controlado (MAX 50) |
| `GET` | `/health` | Health check |

## Service layer — security

- `service/clients/sanitizer.py` — strips tokens, RFC 1918 IPs, internal hostnames, stack traces before sending to Claude
- `service/audit.py` — JSON-lines audit log with `request_id` UUID per operation (`audit.log`)
- `service/clients/jql_builder.py` — Claude → struct → safe JQL, MAX_RESULTS=50 always enforced
- `service/clients/rate_limiter.py` — sliding window per user (`RATE_LIMIT_MAX_CALLS=30`, `RATE_LIMIT_WINDOW=60`)
- `service/clients/jira_client.py` — PAT Bearer auth, corporate cert, `JIRA_TIMEOUT` (default 10s)

## Jira Auth (Server/DC)

Generate a PAT at `jira.zurich.com` → Profile → Personal Access Tokens. Set it as `JIRA_PAT` in `.env`. The client sends `Authorization: Bearer <PAT>` on every request.

## Corporate certificates

`certs/` contains the Zurich root CA files. Set `REQUESTS_CA_BUNDLE` in `.env`:

- `certs/zurichseguros-rootca-until-2031_03_20.crt` — standard internal services
- `certs/cacert-workflow-uat.pem` — UAT workflow endpoints
- `certs/localCA.crt` — local dev CA

## Documentation

| Documento | Ubicación |
|---|---|
| Arquitectura general | `arch/design/architecture-overview.md` |
| Plan de implementación | `arch/design/implementation-plan.md` |
| Informe técnico MCP | `arch/reports/mcp-technical-report.md` |
| Evaluaciones externas | `arch/evaluations/` |

## Implementation phases

| Fase | Estado | Descripción |
|---|---|---|
| 1 — Prototipo CLI | ✅ Completa | `cli/main.py` — comando `create` directo |
| 2 — Service Layer | ✅ Completa | FastAPI + sanitización + audit log + timeouts |
| 3 — Comandos completos | ✅ Completa | `update`, `summarize`, `list` + JQL controlado + rate limiter |
| 4 — MCP Server | Pendiente | Servicio Docker con auth API key + RBAC + pre-validación + output normalizado |
| 5 — Observabilidad | Opcional | Prometheus + OpenTelemetry + caching |
