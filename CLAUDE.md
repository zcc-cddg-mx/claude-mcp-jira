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
# Full stack (service layer + MCP server) — puertos 18000/18001 (igual que dev)
docker compose up

# Dev mode (no Docker) — puertos 18000/18001 (8000 ocupado por Portainer)
bash scripts/dev.sh both       # service :18000 + MCP :18001
bash scripts/dev.sh stop       # detener todo
bash scripts/dev.sh restart    # reinicio limpio
bash scripts/dev.sh status     # ver estado

# Tests
bash scripts/test-dev.sh       # e2e service layer: 8 tests (CLI → FastAPI → Jira)
bash scripts/test-mcp.sh       # e2e MCP server: 10 tests (tools + auth + RBAC)
pytest tests/                  # tests unitarios: 52 tests (sanitizer, jql, auth, rbac)

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
      "url": "http://localhost:18001/sse",
      "headers": { "X-API-Key": "<MCP_API_KEY>" }
    }
  }
}
```

Both dev and Docker expose port 18001 on the host (Docker maps 18001→8001 inside container). For internal deployment replace `localhost:18001` with `mcp-jira.internal:18001`.

## Service layer — endpoints

| Method | Path | Descripción |
|---|---|---|
| `POST` | `/issues` | Crear ticket desde texto libre |
| `PATCH` | `/issues/{key}` | Actualizar ticket desde texto libre |
| `GET` | `/issues/{key}/summary` | Resumen Claude del ticket |
| `POST` | `/issues/search` | Búsqueda NL → JQL controlado (MAX 50) |
| `POST` | `/issues/{key}/transition` | Cambiar estado (texto libre → Claude → transición Jira) |
| `POST` | `/issues/{key}/worklog` | Registrar horas trabajadas (texto libre → Claude → worklog) |
| `POST` | `/issues/{key}/comments` | Añadir comentario (texto libre → Claude → comentario Jira) |
| `POST` | `/issues/{key}/assign` | Asignar ticket (texto libre → Claude → assignee Jira) |
| `POST` | `/issues/{key}/priority` | Cambiar prioridad (texto libre → Claude → priority Jira) |
| `POST` | `/issues/{key}/labels` | Gestionar labels (SET/ADD/REMOVE desde texto libre) |
| `POST` | `/issues/{key}/clone` | Clonar ticket (hereda campos; overrides opcionales vía texto) |
| `POST` | `/issues/{key}/link` | Relacionar tickets (texto libre → Claude → issueLink Jira; tipos dinámicos) |
| `GET` | `/issue-link-types` | Lista tipos de link reales de Jira (cache TTL 1h) |
| `POST` | `/issues/{key}/actions` | Acciones de largo plazo (add_watcher, etc.) — 501 |
| `GET` | `/health` | Health check |

## MCP server — tools

| Tool | Rol mínimo | Descripción |
|---|---|---|
| `create_jira_issue` | dev | Crea ticket desde texto |
| `update_jira_issue` | lead | Actualiza ticket desde texto |
| `get_jira_issue` | dev | Resumen de ticket |
| `search_jira_issues` | dev | Búsqueda NL (máx. 50) |
| `add_comment_jira_issue` | dev | Añade comentario a un ticket |
| `link_jira_issues` | dev | Relaciona dos tickets (depends on, blocks, relates, etc.) |
| `assign_jira_issue` | lead | Asigna un ticket a un usuario |
| `set_priority_jira_issue` | lead | Cambia la prioridad de un ticket |

## Security layers

| Capa | Dónde | Qué hace |
|---|---|---|
| Sanitización | service layer | Elimina tokens, IPs RFC1918, hostnames internos, stack traces |
| Audit log | service layer + MCP | JSON-lines con `request_id` UUID; rotación 10 MB × 5 backups |
| JQL builder | service layer | Claude → struct → JQL seguro (`_jql_escape` en todos los campos), MAX_RESULTS=50 |
| Sanitización HTTP errors | service layer | `sanitize(str(e))` en todos los `HTTPException.detail` |
| Rate limit (NL) | service layer | 30 req/60s por usuario (`shared/rate_limiter.py`) |
| API key + IP allowlist | MCP server | Autenticación + restricción de red |
| RBAC | MCP server | Roles dev/lead/system por API key |
| Rate limit (MCP) | MCP server | 10 calls/60s por API key (`shared/rate_limiter.py`) |
| Pre-validación | MCP server | Rechaza inputs vacíos o >2000 chars |
| Output normalizado | MCP server | LLM solo recibe `{key,status}` o `{key,summary}` |
| SSE timeout | MCP server | `asyncio.wait_for` con `MCP_SSE_TIMEOUT=300s` |
| Tests unitarios | `tests/` | 52 tests: sanitizer, jql_builder, auth, rbac |

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
| Proyectos Jira (restricciones, TICKET_LANG) | `docs/jira-projects.md` |
| Campos requeridos por proyecto | `docs/jira-fields.md` |
| Permisos efectivos del usuario | `docs/jira-roles.md` |
| Tipos de link Jira | `docs/jira-link-types.md` |
| Workflows por proyecto | `docs/jira-workflows.md` |
| Evaluaciones externas | `arch/evaluations/` |

## Implementation phases

| Fase | Estado | Descripción |
|---|---|---|
| 1 — Prototipo CLI | ✅ Completa | `cli/main.py` — comando `create` directo |
| 2 — Service Layer | ✅ Completa | FastAPI + sanitización + audit log + timeouts |
| 3 — Comandos completos | ✅ Completa | `update`, `summarize`, `list` + JQL controlado + rate limiter |
| 4 — MCP Server | ✅ Completa | SSE Docker + auth API key + RBAC + rate limit + output normalizado |
| 4.1 — Ajustes e2e + TICKET_LANG | ✅ Completa | Campos ZNRX, priority IDs, prompts ES, idioma configurable |
| 4.2 — Deuda técnica | ✅ Completa | JQL injection fix, audit MCP, rate limiter compartido, 52 unit tests |
| 4.3 — Transiciones y Log Work | ✅ Completa | `POST /issues/{key}/transition` + `POST /issues/{key}/worklog` |
| 4.4 — Mejoras API | ✅ Completa | comments, assign, priority, labels, clone; Swagger prod off |
| 4.5 — Link dinámico | ✅ Completa | `POST /issues/{key}/link` + `GET /issue-link-types`; tipos reales de Jira, cache TTL 1h |
| 5 — Soporte SAZ | Futura | Tickets SAZ vinculados a ZNRX — bloqueantes resueltos |
| 6 — Observabilidad | Opcional | Prometheus + OpenTelemetry + caching |

## Test tickets (limpieza)

Los tickets de prueba llevan siempre el prefijo `[MCP Claude Jira Test]`.
JQL para localizar y limpiar: `project = ZNRX AND summary ~ "[MCP Claude Jira Test]" ORDER BY created DESC`
