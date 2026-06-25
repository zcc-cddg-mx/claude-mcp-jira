# Arquitectura General — claude-mcp-jira

**Proyecto**: claude-mcp-jira  
**Entorno**: red corporativa Zurich — Jira Server/Data Center (`jira.zurich.com`)  
**Fecha**: Junio 2026 — estado post-Fase 11 (Fases 1–5, 7, 8a, 9.1–9.4, 9.5a, 11 completas)

---

## 1. Visión general

Sistema de tres capas que permite gestionar tickets Jira en lenguaje natural desde la CLI y desde Claude Code, sin exponer datos internos ni depender de servicios cloud externos.

```
[CLI (Typer)]     ──HTTP──►
                            [Service Layer (FastAPI :18000)] ──► [LiteLLM proxy → Claude API]
[MCP Server SSE]  ──HTTP──►                                  ──► [Jira REST API v2 — jira.zurich.com]
     :18001                                                   ──► [code-agent-mcp :5001 — git + Azure PR]
       ▲
[Claude Code]
```

**Principio central**: el MCP server y la CLI nunca llaman a Claude, Jira ni Azure directamente. Todo pasa por el service layer, que concentra la sanitización, el audit log y la lógica de negocio. Las operaciones git/PR se delegan a `code-agent-mcp` vía HTTP con `X-Agent-Token`.

---

## 2. Capas y responsabilidades

### 2.1 Capa de entrada

| Componente | Tecnología | Puerto | Invocado por |
|---|---|---|---|
| CLI | Python / Typer | — | Desarrollador en terminal |
| MCP Server | Python / SDK `mcp` + Starlette SSE | 18001 | Claude Code (LLM) |

La CLI y el MCP server son **clientes HTTP del service layer**. No duplican lógica.

El MCP server añade controles de acceso propios antes de delegar:
- Autenticación por `X-API-Key`
- IP allowlist por CIDR
- RBAC (roles `dev` / `lead` / `system`)
- Rate limiting por API key (10 calls/60s)
- Pre-validación de input (vacío / tamaño > `MCP_MAX_PAYLOAD_SIZE`)

### 2.2 Service Layer (FastAPI)

Núcleo del sistema. Expone una API REST interna y es el único componente que habla con Claude y Jira.

| Endpoint | Método | Descripción |
|---|---|---|
| `/issues` | POST | Crear ticket desde texto libre; `project` opcional |
| `/issues/{key}` | PATCH | Actualizar ticket desde texto libre |
| `/issues/{key}/summary` | GET | Resumen Claude del ticket |
| `/issues/search` | POST | Búsqueda NL → JQL controlado (máx. 50); `project` opcional |
| `/issues/{key}/transition` | POST | Cambiar estado (texto libre → Claude → transición Jira) |
| `/issues/{key}/worklog` | POST | Registrar horas (texto libre → Claude → worklog Jira) |
| `/issues/{key}/comments` | POST | Añadir comentario |
| `/issues/{key}/assign` | POST | Asignar ticket (texto libre → Claude → assignee) |
| `/issues/{key}/priority` | POST | Cambiar prioridad (texto libre → Claude → priority) |
| `/issues/{key}/labels` | POST | Gestionar labels (SET/ADD/REMOVE) |
| `/issues/{key}/clone` | POST | Clonar ticket con overrides opcionales |
| `/issues/{key}/link` | POST | Relacionar tickets (texto libre → Claude → issueLink) |
| `/issue-link-types` | GET | Tipos de link reales de Jira (cache TTL 1h) |
| `/issues/saz` | POST | Crear ticket SAZ; `znrx_key` opcional para vincularlo |
| `/projects` | GET | Lista proyectos registrados en DB |
| `/projects/{key}` | GET | Config de un proyecto; dispara auto-discovery si no existe |
| `/git/sync` | POST | Leer repo Git local → sesiones → worklogs Jira (dry_run por defecto) |
| `/git/repos` | POST/GET/DELETE | Registro de repos Git (alias → ruta + proyecto Jira) |
| `/workflows/create-feature-pr` | POST | Crear registro WorkflowExecution `pending`; retorna `execution_id` |
| `/workflows/{id}` | GET/PATCH | Consultar o actualizar estado de un workflow (steps + result) |
| `/workflows` | GET | Listar ejecuciones (`?issue_key=`, `?status=`, `?limit=20`) |
| `/health` | GET | Health check |

Responsabilidades exclusivas del service layer:
- **Sanitización**: elimina tokens, IPs RFC1918, hostnames internos (`*.zurich.com`, `*.internal`), stack traces antes de enviar a Claude
- **Audit log**: JSON-lines con `request_id` UUID por operación; rotación 10 MB × 5 backups
- **JQL controlado**: Claude genera un struct → el service layer construye el JQL seguro (nunca JQL libre)
- **Rate limiting por usuario**: sliding window (30 calls/60s)
- **Timeouts**: `JIRA_TIMEOUT` para Jira, `MCP_SERVICE_TIMEOUT` para el MCP server
- **Registro de proyectos**: SQLite con auto-discovery lazy desde Jira

### 2.3 Registro de proyectos (SQLite)

`service/clients/project_db.py` — backend persistente con discovery automático:

```
POST /issues {"project": "NEWTEAM", "text": "..."}
    │
    ├─► resolve_project("NEWTEAM") → DB lookup → miss
    ├─► GET /rest/api/2/project/NEWTEAM (verifica existencia en Jira; 400 si 404)
    ├─► GET /rest/api/2/issue/createmeta?projectKeys=NEWTEAM (extrae campos requeridos si disponible)
    └─► INSERT INTO projects (source: "jira_auto") → procede con la creación
```

Proyectos seeded al startup con configs curadas (source: `seed`): ZNRX, AIPROJECTS, SCRX.  
Cualquier otro proyecto Jira válido se registra en el primer acceso, sin intervención admin.

### 2.4 Clientes externos

| Cliente | Destino | Auth | Cert |
|---|---|---|---|
| `claude_client.py` | LiteLLM proxy → Claude API | `ANTHROPIC_AUTH_TOKEN` | Firewall Zurich |
| `jira_client.py` | `jira.zurich.com` REST API v2 | `Bearer <JIRA_PAT>` | `zurich-root-ca.crt` |
| `code_agent_client.py` | `code-agent-mcp :5001` | `X-Agent-Token` | Red interna |

---

## 3. Flujos de datos

### 3.1 Crear ticket desde CLI

```
cli/main.py create "bug login en producción prioridad alta" --project ZNRX
    │
    ▼ POST /issues {"text": "...", "project": "ZNRX", "user": "carlos.duarte2"}
service/routes/issues.py
    │
    ├─► resolve_project("ZNRX") → config del proyecto (priority_format, required_custom, etc.)
    ├─► sanitizer.py  →  texto limpio
    ├─► claude_client.parse_create_issue()  →  {summary, description, priority, issuetype}
    ├─► jira_client.create_issue()  →  POST /rest/api/2/issue  →  {"key": "ZNRX-1234"}
    └─► audit.log()  →  {"request_id": "uuid", "jira_key": "ZNRX-1234", "status": "ok"}
    │
    ▼ {"key": "ZNRX-1234", "status": "created"}
```

### 3.2 Crear ticket desde Claude Code (MCP)

```
Claude Code: "crea un ticket para el bug de autenticación"
    │
    ▼ MCP call: create_jira_issue(text="bug de autenticación", project="ZNRX")
jira_mcp/server.py
    ├─► verify_api_key + verify_ip + check_permission + rate_check
    ├─► pre-validación (vacío / tamaño)
    └─► jira_mcp/service_client.py  →  POST http://service:18000/issues
                                         (mismo flujo que 3.1)
    │
    ▼ {"key": "ZNRX-1234", "status": "created"}  ← output normalizado al LLM
```

### 3.3 Búsqueda con JQL controlado

```
"mis bugs abiertos de esta semana en AIPROJECTS"
    │
    ▼ claude_client.parse_search_query()
    │   → struct: {assignee: "currentUser()", issuetype: "Bug", date_range: "last_week"}
    ▼ jql_builder.build_jql(struct, project_key="AIPROJECTS")
    │   → "project = "AIPROJECTS" AND assignee = currentUser() AND issuetype = "Bug" AND created >= -7d"
    ▼ jira_client.search_issues(jql, max_results=50)
```

Claude nunca genera JQL directamente — solo el struct de parámetros controlados.

### 3.4 Crear ticket SAZ vinculado a ZNRX

```
POST /issues/saz {"text": "reiniciar servicio auth en prod", "znrx_key": "ZNRX-1234"}
    │
    ├─► rate_limit_check
    ├─► parse_saz_request(text) → {summary, description, issue_type: "Support"}
    ├─► create_saz_issue(payload) → POST /rest/api/2/issue → "SAZ-7403"
    ├─► POST /rest/api/2/issueLink (Relates: SAZ-7403 → ZNRX-1234)
    └─► {"saz_key": "SAZ-7403", "znrx_key": "ZNRX-1234", "status": "linked"}
```

---

## 4. Proyectos Jira

| Key | Nombre | Uso | `TICKET_LANG` | Fuente config |
|---|---|---|---|---|
| `ZNRX` | Gestión requerimientos | Features, bugs, tareas del equipo | `es` | seed |
| `AIPROJECTS` | IA y automatización | Proyectos IA internacionales | `en` | seed |
| `SCRX` | Desarrollo LATAM | Desarrollo ágil Ecuador/LATAM | `es` | seed |
| `SAZ` | Solicitudes Release | DevOps: reinicios, deploys, repos, accesos | `es` | jira_auto |
| cualquier otro | — | Auto-descubierto en primer acceso | `es` (default) | jira_auto |

### Relación ZNRX ↔ SAZ

Un SAZ es autónomo pero habitualmente se vincula a un ZNRX como documentación y justificación:

```
ZNRX-1234  (feature en desarrollo)
    └── SAZ-7403  (link: "Relates" — solicitud de deploy al equipo Release)
```

### Restricciones ZNRX

| Restricción | Valor |
|---|---|
| `customfield_25832` (Línea de Servicio) | obligatorio — BAU id=44461 |
| Priority | solo por ID: Highest=1, High=2, Low=4 |
| Bug issuetype | bloqueado por workflow → fallback a Task |
| Subtasks | screen diferente — no acepta `customfield_25832` ni `priority` |

---

## 5. Seguridad en capas

```
[Claude Code]
     │
     ▼  X-API-Key + IP CIDR check
[MCP Server]  ──── RBAC + rate limit + pre-validación
     │
     ▼  HTTP interno (red Docker)
[Service Layer]  ── sanitización + audit log + rate limit por usuario
     │
     ▼  PAT Bearer + REQUESTS_CA_BUNDLE
[jira.zurich.com]
```

| Capa | Control | Variable |
|---|---|---|
| MCP | API key | `MCP_API_KEY` |
| MCP | IP allowlist | `MCP_ALLOWED_CIDRS` |
| MCP | RBAC | `MCP_KEY_ROLES`, `MCP_DEFAULT_ROLE` |
| MCP | Rate limit | `MCP_RATE_LIMIT_MAX_CALLS` / `_WINDOW` |
| MCP | Pre-validación payload | `MCP_MAX_PAYLOAD_SIZE` |
| Service | Sanitización (tokens, IPs, hosts, stack traces) | — |
| Service | Audit log con `request_id` y rotación | `AUDIT_LOG_PATH` |
| Service | Rate limit por usuario | `RATE_LIMIT_MAX_CALLS` / `_WINDOW` |
| Service | JQL controlado (máx. 50 resultados) | `JIRA_MAX_RESULTS` |
| Service | Project allowlist (opcional) | `JIRA_ALLOWED_PROJECTS` |
| Jira client | PAT Bearer + cert corporativo | `JIRA_PAT`, `REQUESTS_CA_BUNDLE` |
| Claude client | Proxy interno LiteLLM | `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` |

### RBAC — herramientas MCP por rol

| Tool | dev | lead | system |
|---|---|---|---|
| `create_jira_issue` | ✅ | ✅ | ✅ |
| `get_jira_issue` | ✅ | ✅ | ✅ |
| `search_jira_issues` | ✅ | ✅ | ✅ |
| `add_comment_jira_issue` | ✅ | ✅ | ✅ |
| `link_jira_issues` | ✅ | ✅ | ✅ |
| `sync_git_worklogs` | ✅ | ✅ | ✅ |
| `register_git_repo` | ✅ | ✅ | ✅ |
| `list_git_repos` | ✅ | ✅ | ✅ |
| `get_code_agent_status` | ✅ | ✅ | ✅ |
| `get_pull_request_status` | ✅ | ✅ | ✅ |
| `get_workflow_status` | ✅ | ✅ | ✅ |
| `update_jira_issue` | ❌ | ✅ | ✅ |
| `assign_jira_issue` | ❌ | ✅ | ✅ |
| `set_priority_jira_issue` | ❌ | ✅ | ✅ |
| `create_saz_request` | ❌ | ✅ | ✅ |
| `run_code_agent` | ❌ | ✅ | ✅ |
| `create_azure_pull_request` | ❌ | ✅ | ✅ |
| `run_create_feature_pr_workflow` | ❌ | ✅ | ✅ |

---

## 6. Certificados corporativos

Todos los certificados viven en `certs/` y se instalan en `/etc/ssl/certs/` dentro de los contenedores Docker.

| Archivo | Endpoint | Variable |
|---|---|---|
| `zurichseguros-rootca-until-2031_03_20.crt` | `jira.zurich.com` (alias: `zurich-root-ca.crt`) | `REQUESTS_CA_BUNDLE` |
| `zurich-ssl-ca.pem` | `api-zurich.data-fact.com` (SSL inspection via `ssldecrypt.latam.zurich.com`) | `REQUESTS_CA_BUNDLE` |
| `cacert-workflow-uat.pem` | Endpoints UAT de workflow | `REQUESTS_CA_BUNDLE` |
| `localCA.crt` | Desarrollo local | `REQUESTS_CA_BUNDLE` |

---

## 7. Despliegue Docker

```yaml
services:
  service:   # FastAPI — host:18000 → container:8000
  mcp:       # MCP SSE — host:18001 → container:8001
             # depends_on: service
volumes:
  audit_log: # /app/audit.log persistido entre reinicios
  projects_db: # /app/projects.db — registro SQLite de proyectos
```

```bash
docker compose up                # producción
bash scripts/dev.sh both         # dev sin Docker (service :18000 + MCP :18001)
bash scripts/dev.sh restart      # reinicio limpio
```

---

## 8. Estructura de directorios

```
claude-mcp-jira/
├── cli/
│   └── main.py                    # Typer CLI — create, update, summarize, list-issues (--project)
├── service/
│   ├── main.py                    # FastAPI v0.5.0 — lifespan: init_db + init_repo_registry + init_workflow_db + seed
│   ├── audit.py                   # JSON-lines con request_id + pat_source, rotación 10 MB × 5
│   ├── middleware/
│   │   └── jira_auth.py           # JiraAuthMiddleware — extrae X-Jira-Token → ContextVar
│   ├── routes/                    # issues, update, summarize, search, transitions, worklog,
│   │                              # comments, assign, priority, labels, clone, link, saz, projects,
│   │                              # actions, git_sync, git_repos, workflows
│   ├── schemas/
│   │   ├── issue.py               # Schemas Request/Payload/Response de tickets
│   │   └── git_schemas.py         # Schemas Git Intelligence
│   ├── git/
│   │   ├── scanner.py             # subprocess git log (metadata only)
│   │   ├── analyzer.py            # group_sessions(), estimate_time()
│   │   ├── mapper.py              # extract_issue_key() regex + Claude fallback
│   │   └── repo_registry.py       # SQLite git_repos: alias → ruta + proyecto Jira
│   ├── clients/
│   │   ├── sanitizer.py           # Sanitización extendida
│   │   ├── claude_client.py       # parse_*(). _lang_suffix() per-proyecto; git_humanizer
│   │   ├── jira_client.py         # PAT Bearer + ContextVar + cert + timeout; config dinámica
│   │   ├── code_agent_client.py   # httpx → code-agent-mcp; X-Agent-Token; run/status/pr/pr-status
│   │   ├── jql_builder.py         # Claude → struct → JQL seguro; project_key opcional
│   │   ├── project_config.py      # Fachada: get_config(), resolve_project()
│   │   ├── project_db.py          # SQLite projects: init_db, seed, get_or_discover, list
│   │   ├── workflow_store.py      # SQLite workflow_executions: CRUD 5 funciones
│   │   └── rate_limiter.py        # Sliding window por usuario
│   └── prompts/                   # create, update, summarize, search, transition, log_work,
│                                  # add_comment, assign, priority, labels, clone, link, saz_create,
│                                  # git_sync_fallback, git_humanizer
├── jira_mcp/
│   ├── server.py                  # SSE server — 15 herramientas + audit log + _run_create_feature_pr_workflow
│   ├── auth.py                    # API key + IP allowlist
│   ├── rbac.py                    # Roles dev/lead/system y permisos
│   ├── service_client.py          # Cliente httpx con output filtrado; _agent_client() independiente
│   └── README.md
├── shared/
│   └── rate_limiter.py            # RateLimiter compartido entre service y jira_mcp
├── tests/
│   ├── test_sanitizer.py          # 13 tests
│   ├── test_jql_builder.py        # 18 tests (escape + injection)
│   ├── test_auth.py               # 10 tests
│   ├── test_rbac.py               # 11 tests
│   ├── test_jira_pat_routing.py   # 7 tests (PAT dinámico)
│   ├── test_git_analyzer.py       # 22 tests
│   └── test_git_mapper.py         # 15 tests
├── docs/
│   ├── jira-projects.md           # Metadata ZNRX, AIPROJECTS, SAZ, SCRX
│   ├── jira-fields.md             # Campos requeridos/opcionales por proyecto
│   ├── jira-roles.md              # Permisos efectivos del usuario
│   ├── jira-link-types.md         # 29 link types; recomendación SAZ→ZNRX
│   ├── jira-workflows.md          # Statuses y transiciones por proyecto
│   └── jira-subtasks.md           # Sub-tasks por proyecto (limitaciones API)
├── certs/                         # Certificados raíz corporativos Zurich
├── arch/
│   ├── design/                    # arquitectura + plan de implementación
│   ├── evaluations/               # evals externas por fase
│   ├── reports/                   # informe técnico MCP
│   ├── bd/                        # schema SQLite (projects + git_repos + workflow_executions)
│   ├── code-agent/                # plan de integración Fase 11
│   └── workflows/                 # diseño + especificación Workflow Orchestrator Fase 10
├── scripts/
│   ├── dev.sh                     # arranque/stop/restart/status local
│   ├── test-dev.sh                # 8 tests e2e service layer
│   ├── test-mcp.sh                # 10 tests e2e MCP server
│   ├── test-multi.sh              # 19 tests e2e multi-proyecto
│   ├── test-actions.sh            # 24 tests e2e acciones
│   ├── test-git.sh                # 26 tests e2e Git Intelligence
│   └── test-code-agent.sh         # 19 tests Fase 11 (schema/dispatch)
├── Dockerfile                     # Service layer
├── docker-compose.yml             # service (:18000) + mcp (:18001)
├── environment.yml
├── .env.example
└── CLAUDE.md
```

---

## 9. Decisiones de arquitectura clave

| Decisión | Elegida | Motivo |
|---|---|---|
| MCP oficial Atlassian | Descartado | Solo Jira Cloud; viola políticas de red |
| N8N / Zapier | Descartado | Servicios cloud bloqueados por firewall |
| Jira API version | v2 | v3 es exclusiva de Jira Cloud |
| Auth Jira | PAT Bearer | Jira Server/DC — no Basic Auth con email+token |
| Descripción tickets | Texto plano | Jira Server no acepta ADF |
| JQL | Claude → struct → builder | JQL libre genera riesgo de queries destructivas |
| Output MCP | Normalizado `{key, status}` | Evitar filtración de datos internos al LLM |
| Persistencia MCP | Ninguna — stateless | Sin disco, escalable, menor superficie de ataque |
| Trazabilidad | `request_id` UUID por operación | Correlacionar logs sin sesiones complejas |
| Registro proyectos | SQLite + auto-discovery lazy | Soporte multi-equipo sin admin; cualquier proyecto Jira válido funciona en el primer acceso |
| Allowlist proyectos | `JIRA_ALLOWED_PROJECTS` (vacío por defecto) | Seguridad delegada al PAT de Jira y token Azure; allowlist solo si se quiere restricción adicional |
| Link types | Consultados en tiempo real + cache 1h | Portable entre instancias Jira; no hardcodeados |
| Endpoints | Commands explícitos por acción | Issue Jira = aggregate; mejor auditoría y uso por Claude/MCP |
| Swagger en producción | Deshabilitado (`APP_ENV=prod`) | Evitar exposición de contratos internos |
