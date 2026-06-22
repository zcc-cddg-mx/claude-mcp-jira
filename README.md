# claude-mcp-jira

Integración de Claude con Jira vía MCP server interno, diseñada para entornos corporativos con red privada (Jira Server/Data Center).

## Arquitectura

```
[CLI (Typer)]     ──HTTP──►
                            [Service Layer (FastAPI)] → [Claude API — LiteLLM proxy]
[MCP Server SSE]  ──HTTP──►                           → [Jira REST API v2 — jira.zurich.com]
```

El MCP server y el service layer corren dentro de la red corporativa. Ningún dato sale hacia servicios cloud externos.

## Setup

```bash
conda env create -f environment.yml
conda activate claude-mcp-jira
cp .env.example .env  # completar JIRA_PAT y MCP_API_KEY
```

## Uso

```bash
# Levantar stack completo (service layer + MCP server)
docker compose up

# Desarrollo local (fuera de Docker)
bash scripts/dev.sh both       # service :18000 + MCP :18001
bash scripts/dev.sh service    # solo service layer
bash scripts/dev.sh stop       # detener todo
bash scripts/dev.sh restart    # reinicio limpio

# Tests
bash scripts/test-dev.sh       # service layer: 8 tests (CLI → FastAPI → Jira)
bash scripts/test-mcp.sh       # MCP server: 10 tests (SSE tools + auth + RBAC)
bash scripts/test-multi.sh     # multi-proyecto: 19 tests (ZNRX/AIPROJECTS/SAZ + auto-discovery)
bash scripts/test-actions.sh   # endpoints de acción: 24 tests (comments, assign, priority, labels, worklog, transition, clone, link, saz)
pytest tests/                  # unitarios: 52 tests (sanitizer, jql, auth, rbac)

# Comandos CLI
python cli/main.py create "bug login en producción prioridad alta"
python cli/main.py update ZNRX-123 "cambiar prioridad a alta"
python cli/main.py summarize ZNRX-123
python cli/main.py list-issues "mis tareas abiertas de esta semana"
```

## Proyectos Jira configurados

Ver [`docs/jira-projects.md`](docs/jira-projects.md) para metadata completa, restricciones de campos y configuración por proyecto.

| Proyecto | `JIRA_PROJECT_KEY` | `TICKET_LANG` | Propósito |
|---|---|---|---|
| ZNRX | `ZNRX` | `es` | Gestión de requerimientos y desarrollo |
| AIPROJECTS | `AIPROJECTS` | `en` | IA y automatización de negocio |
| SAZ | `SAZ` | `es` | Solicitudes Release / DevOps |
| SCRX | `SCRX` | `es` | Desarrollo ágil Ecuador/LATAM |

## Certificados corporativos

`certs/` contiene los certificados raíz Zurich. Ambos Dockerfiles los instalan automáticamente en `/etc/ssl/certs/`.

| Archivo | Uso |
|---|---|
| `zurichseguros-rootca-until-2031_03_20.crt` | Servicios internos estándar (`jira.zurich.com`) |
| `zurich-ssl-ca.pem` | SSL inspection CA (`ssldecrypt.latam.zurich.com`) — requerido para `api-zurich.data-fact.com` |
| `cacert-workflow-uat.pem` | Endpoints UAT de workflow |
| `localCA.crt` | CA de desarrollo local |

En `.env`, `REQUESTS_CA_BUNDLE` apunta al cert del endpoint que se va a llamar. Ver `.env.example` para detalles.

## Estado de implementación

| Fase | Estado | Descripción |
|---|---|---|
| 1 — Prototipo CLI | ✅ Completa | Comando `create` directo |
| 2 — Service Layer | ✅ Completa | FastAPI + sanitización + audit log + timeouts |
| 3 — Comandos completos | ✅ Completa | `update`, `summarize`, `list` + JQL controlado + rate limiter |
| 4 — MCP Server | ✅ Completa | SSE Docker + auth API key + RBAC + rate limit + output normalizado |
| 4.1 — Ajustes e2e + TICKET_LANG | ✅ Completa | Campos ZNRX, priority IDs, prompts ES, idioma configurable |
| 4.2 — Deuda técnica | ✅ Completa | JQL injection fix, audit MCP, rate limiter compartido, 52 unit tests |
| 4.3 — Transiciones y Log Work | ✅ Completa | `POST /issues/{key}/transition` + `POST /issues/{key}/worklog` |
| 4.4 — Mejoras API | ✅ Completa | comments, assign, priority, labels, clone |
| 4.5 — Link dinámico | ✅ Completa | `POST /issues/{key}/link` + `GET /issue-link-types` (cache TTL 1h) |
| 5 — Soporte SAZ | ✅ Completa | `POST /issues/saz` + MCP `create_saz_request` (lead); `znrx_key` opcional |
| 7 — Multi-proyecto | ✅ Completa | `project` opcional en create/search; SQLite + auto-discovery lazy; `GET /projects` |
| 6 — Observabilidad | Futura | Prometheus + OpenTelemetry + caching — activar cuando el volumen lo justifique |
| 8a — PAT dinámico | Futura | `X-Jira-Token` header opcional — cada usuario opera con su propia identidad Jira |
| 8 — UI | Futura | Streamlit MVP → Next.js si hay adopción; login PAT → JWT → propaga como X-Jira-Token |
| 9 — Git Intelligence | Futura | Mapear commits→tickets, estimar y registrar worklogs automáticamente; MCP tool `sync_git_worklogs` |

## Documentación

| Documento | Descripción |
|---|---|
| [`docs/jira-projects.md`](docs/jira-projects.md) | Proyectos Jira — restricciones, issuetypes, `TICKET_LANG` |
| [`docs/jira-fields.md`](docs/jira-fields.md) | Campos requeridos y valores permitidos por proyecto |
| [`docs/jira-roles.md`](docs/jira-roles.md) | Permisos efectivos del usuario en los 4 proyectos |
| [`docs/jira-link-types.md`](docs/jira-link-types.md) | Tipos de link — 29 tipos en jira.zurich.com; también disponible vía `GET /issue-link-types` |
| [`docs/jira-workflows.md`](docs/jira-workflows.md) | Statuses y transiciones por proyecto |
| [`arch/`](arch/README.md) | Arquitectura, plan de implementación, evaluaciones e informes técnicos |
| [`jira_mcp/README.md`](jira_mcp/README.md) | Variables de entorno y configuración del MCP server |
