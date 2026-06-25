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
                                                       → [code-agent-mcp (Fase 11) — git + Azure PR]
```

**Key constraints for Zurich environment:**
- Jira is Server/Data Center, not Cloud → REST API v2, PAT Bearer auth, plain-text descriptions
- Claude API goes through the internal LiteLLM proxy (see parent repo `CLAUDE.md` for env vars)
- Corporate firewall requires `REQUESTS_CA_BUNDLE` pointing to `certs/` for Jira calls
- No external services (Atlassian MCP cloud, N8N, Zapier) — all traffic stays inside the network
- `code-agent-mcp` is a separate service (`/home/idavid/dev/claude/code-agent-mcp`) — handles git ops and Azure DevOps PRs; auth via `X-Agent-Token`

## Setup

```bash
conda env create -f environment.yml
conda activate claude-mcp-jira
cp .env.example .env  # fill in JIRA_PAT, MCP_API_KEY, CODE_AGENT_TOKEN and uncomment REQUESTS_CA_BUNDLE
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
bash scripts/test-dev.sh          # e2e service layer: 8 tests (CLI → FastAPI → Jira)
bash scripts/test-mcp.sh          # e2e MCP server: 10 tests (tools + auth + RBAC)
bash scripts/test-multi.sh        # e2e multi-proyecto: 19 tests (ZNRX/AIPROJECTS/SAZ + auto-discovery)
bash scripts/test-actions.sh      # e2e endpoints de acción: 24 tests (comments, assign, priority, labels, worklog, transition, clone, link, saz)
bash scripts/test-git.sh          # e2e Git Intelligence: 26 tests (repos CRUD + sync dry_run)
bash scripts/test-code-agent.sh   # Fase 10+11 schema/dispatch: 32 tests (sin requerir code-agent-mcp corriendo)
bash scripts/test-code-agent.sh --live  # live e2e con code-agent-mcp en CODE_AGENT_URL
pytest tests/                     # tests unitarios: 96 tests (sanitizer, jql, auth, rbac, git_analyzer, git_mapper, jira_pat_routing)

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
| `POST` | `/issues` | Crear ticket desde texto libre; `project` opcional (default: `JIRA_DEFAULT_PROJECT`) |
| `PATCH` | `/issues/{key}` | Actualizar ticket desde texto libre |
| `GET` | `/issues/{key}/summary` | Resumen Claude del ticket |
| `POST` | `/issues/search` | Búsqueda NL → JQL controlado (MAX 50); `project` opcional para acotar |
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
| `POST` | `/issues/saz` | Crear ticket SAZ (DevOps/Release); `znrx_key` opcional para vincularlo |
| `POST` | `/issues/saz/deployment` | Crear SAZ de despliegue desde datos de PR (template determinista, sin Claude); campos: `task`, `repo`, `target`, `branch`, `base_branch`, `pr_id`, `pr_url`, `project_label`, `znrx_key` (opcional) |
| `GET` | `/projects` | Lista proyectos registrados en DB (seed + auto-descubiertos) |
| `GET` | `/projects/{key}` | Config de un proyecto; dispara auto-discovery desde Jira si no existe en DB |
| `GET` | `/health` | Health check |
| `POST` | `/workflows/create-feature-pr` | Crea registro de ejecución `pending`; retorna `execution_id` |
| `GET` | `/workflows/{execution_id}` | Estado actual del workflow (steps + result) |
| `GET` | `/workflows` | Lista ejecuciones (`?issue_key=`, `?status=`, `?limit=20`) |
| `PATCH` | `/workflows/{execution_id}` | Actualiza status/steps/result (llamado por MCP tool tras cada paso) |

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
| `create_saz_request` | lead | Crea ticket SAZ (DevOps/Release); `znrx_key` opcional |
| `sync_git_worklogs` | dev | Lee repo Git local, detecta sesiones de trabajo y registra worklogs en Jira |
| `register_git_repo` | dev | Registra un repo local en el registry (alias → ruta + proyecto Jira) |
| `list_git_repos` | dev | Lista repos registrados en el registry |
| `run_code_agent` | lead | Encola tarea git en code-agent-mcp: crear rama, commit, push, rama auxiliar → `task_id` |
| `get_code_agent_status` | dev | Consulta estado de tarea code-agent-mcp (queued/running/done/error) |
| `create_azure_pull_request` | lead | Idempotente: ensure aux branch + crear o retornar PR en Azure DevOps |
| `get_pull_request_status` | dev | Estado del PR + build CI en Azure DevOps |
| `run_create_feature_pr_workflow` | lead | Ejecuta workflow completo: preview → git → PR → CI → link Jira; retorna `execution_id` + steps |
| `get_workflow_status` | dev | Estado de ejecución de un workflow (steps, result, error) |

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
| Tests unitarios | `tests/` | 96 tests: sanitizer, jql_builder, auth, rbac, git_analyzer, git_mapper, jira_pat_routing |
| code-agent-mcp token | MCP server | `X-Agent-Token` en `_agent_client()` — separado del `JIRA_PAT`; valor en `CODE_AGENT_TOKEN` |

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
| Integración code-agent-mcp (Fase 11) | `arch/code-agent/integration-plan.md` |
| Workflow Orchestrator (Fase 10) | `arch/workflows/workflow-orchestrator.md` |
| Proyectos Jira (restricciones, TICKET_LANG) | `docs/jira-projects.md` |
| Campos requeridos por proyecto | `docs/jira-fields.md` |
| Permisos efectivos del usuario | `docs/jira-roles.md` |
| Tipos de link Jira | `docs/jira-link-types.md` |
| Workflows por proyecto | `docs/jira-workflows.md` |
| Evaluaciones externas | `arch/evaluations/` |
| Base de datos SQLite | `arch/bd/README.md` |
| Sub-tasks por proyecto (limitaciones API) | `docs/jira-subtasks.md` |

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
| 5 — Soporte SAZ | ✅ Completa | `POST /issues/saz` + MCP `create_saz_request` (lead); `znrx_key` opcional; `POST /issues/saz/deployment` (template determinista, título `Despliegue ambiente {ENV} - {PROYECTO} - {TASK}`) |
| 6 — Observabilidad | Futura | Prometheus + OpenTelemetry + caching — activar cuando el volumen lo justifique |
| 7 — Multi-proyecto | ✅ Completa | `project` opcional en create/search; SQLite + auto-discovery lazy desde Jira; `GET /projects` |
| Deuda técnica H1-H9 | ✅ Resuelta | test-actions.sh (24 e2e), auto-link check, rate limit GET públicos, schemas labels, validaciones SAZ/assign/worklog, PROJECT_DB_PATH |
| 8a — PAT dinámico | ✅ Completa | `X-Jira-Token` header opcional — `ContextVar` + `JiraAuthMiddleware`; `jira_token` en todos los MCP tools; `pat_source` en audit log |
| 8 — UI | Futura | Streamlit MVP → Next.js si hay adopción; login PAT → JWT → propaga como X-Jira-Token; requiere Fase 10 |
| 9.1–9.4 — Git Intelligence | ✅ Completa | Scanner subprocess, analyzer sesiones+tiempo, mapper regex+NLP, `POST /git/sync`, repo registry SQLite (`git_repos`), MCP `sync_git_worklogs`/`register_git_repo`/`list_git_repos` |
| 9.5a — Claude humanizer | ✅ Completa | Ajuste semántico de estimaciones git con Claude (debugging, alta complejidad, trabajo nocturno) |
| 9.5b — Human factors + learning layer | Futura | Señales contextuales interactivas + multiplier factors por usuario — requiere Fase 10 + UI |
| 10 — Workflow Orchestrator | ✅ Completa | `workflow_store.py` + `routes/workflows.py` + 2 MCP tools (`run_create_feature_pr_workflow`, `get_workflow_status`); 4 REST endpoints + 6-step polling engine; 32 schema tests |
| 11 — Integración code-agent-mcp | ✅ Completa | `service/clients/code_agent_client.py` + 4 MCP tools (run/status/pr/pr-status); delega git ops y Azure PR al code-agent-mcp |

## Test tickets (limpieza)

Los tickets de prueba llevan siempre el prefijo `[MCP Claude Jira Test]`.
JQL para localizar y limpiar:
- ZNRX: `project = ZNRX AND summary ~ "[MCP Claude Jira Test]" ORDER BY created DESC`
- SAZ: `project = SAZ AND summary ~ "[MCP Claude Jira Test]" ORDER BY created DESC`

Los SAZ de despliegue generados por el workflow no llevan el prefijo — eliminarlos manualmente si son de prueba.
