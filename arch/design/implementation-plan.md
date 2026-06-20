# Plan de Implementación: claude-mcp-jira

Implementación incremental en 6 fases para red empresarial (Jira Server/Data Center en `jira.zurich.com`).
Claude API accedida vía proxy LiteLLM interno de Zurich.

> **Decisión de arquitectura**: se descartó el MCP oficial de Atlassian (solo funciona con Jira Cloud y viola políticas de red) y plataformas No-Code (N8N/Zapier). Se implementa integración propia con MCP server interno desplegable en Docker.

---

## Fase 1 — Prototipo mínimo (CLI → Claude → Jira) ✅

**Objetivo**: demostrar el flujo end-to-end básico con autenticación correcta para Jira Server.

### Entregables
- `cli/main.py` con Typer — comando único `create`
- `requirements.txt` y `environment.yml` (conda)
- `.env.example` con variables para entorno Zurich

### Ajustes para Jira Server/DC
- Auth: `Authorization: Bearer <PAT>` (no Basic Auth)
- API: `/rest/api/2/` (no v3)
- Descripción: texto plano (no ADF/JSON doc)
- SSL: `REQUESTS_CA_BUNDLE` apunta a cert corporativo en `certs/`

### Criterio de éxito
```bash
python cli/main.py create "bug login en producción prioridad alta"
# → PROJ-001 creado en jira.zurich.com
```

---

## Fase 2 — Service Layer (FastAPI) + Seguridad ✅

**Objetivo**: desacoplar CLI de las APIs externas. Sanitización, validación, trazabilidad y timeouts.

### Entregables
- `service/` — FastAPI con `POST /issues` y `GET /health`
- `service/clients/sanitizer.py` — elimina secrets antes de enviar a Claude
- `service/audit.py` — audit log JSON-lines con `request_id` para trazabilidad completa
- `service/clients/jira_client.py` — timeout configurable vía `JIRA_TIMEOUT`
- CLI simplificada a cliente HTTP del service layer
- `Dockerfile` + `docker-compose.yml`

### Seguridad implementada
- **Sanitización extendida**: Bearer tokens, passwords, emails, IPs privadas RFC 1918 (`10.x`, `172.16-31.x`, `192.168.x`), hostnames internos (`*.zurich.com`, `*.internal`, `*.local`), stack traces
- **Audit log**: `request_id` (UUID), `timestamp`, `user`, `action`, `input`, `claude_payload`, `jira_key`, `status`, `error`
- **Timeout Jira**: `JIRA_TIMEOUT=10` (segundos), configurable en `.env`

### Criterio de éxito
```bash
docker compose up
python cli/main.py create "bug login en producción"
# → CLI → FastAPI → sanitize → Claude → Jira → PROJ-002
# → audit.log: {"request_id": "uuid", "jira_key": "PROJ-002", "status": "ok", ...}
```

---

## Fase 3 — Comandos completos + JQL controlado ✅

**Objetivo**: soporte para los 4 comandos CLI con clasificación de intención y queries JQL seguras.

### Entregables
- 4 comandos CLI: `create`, `update`, `summarize`, `list_issues`
- `service/clients/jql_builder.py` — Claude → struct → JQL seguro
- `service/clients/rate_limiter.py` — sliding window por usuario
- Endpoints: `PATCH /issues/{key}`, `GET /issues/{key}/summary`, `POST /issues/search`

### JQL controlado
Claude **no genera JQL directamente**:
- Claude genera struct: `{"assignee": "currentUser()", "issuetype": "Bug", ...}`
- El service layer construye el JQL seguro
- `MAX_RESULTS = 50` fijo, sin excepciones

### Criterio de éxito
```bash
python cli/main.py update PROJ-002 "cambiar prioridad a crítica"
python cli/main.py summarize PROJ-002
python cli/main.py list "mis bugs abiertos de esta semana"
```

---

## Fase 4 — MCP Server (servicio deployable interno) ✅

**Objetivo**: exponer la integración como MCP server SSE desplegable en red interna con auth, RBAC y protecciones en dos capas.

### Entregables
- `mcp/server.py` — SSE server, 4 herramientas, delega al service layer
- `mcp/auth.py` — API key + IP allowlist por CIDR
- `mcp/rbac.py` — roles dev/lead/system, mapeo API key → rol
- `mcp/rate_limiter.py` — sliding window por API key (independiente del service layer)
- `mcp/service_client.py` — output filtrado antes de devolver al LLM
- `mcp/Dockerfile` + `docker-compose.yml` actualizado

### Protecciones MCP (segunda capa sobre el service layer)

| Control | Implementación |
|---|---|
| API key | `X-API-Key` header, `MCP_API_KEY` |
| IP allowlist | CIDRs `10.0.0.0/8`, `192.168.0.0/16` |
| RBAC | dev (create/get/search) · lead (+update) · system (todo) |
| Pre-validación | input vacío o >2000 chars rechazado antes de llamar al backend |
| Rate limiting | `MCP_RATE_LIMIT_MAX_CALLS=10/60s` por API key |
| Output normalizado | LLM recibe solo `{key,status}` o `{key,summary}` |

### Configuración `.claude/settings.json`
```json
{
  "mcpServers": {
    "jira": {
      "type": "sse",
      "url": "http://mcp-jira.internal:8001/sse",
      "headers": { "X-API-Key": "<MCP_API_KEY>" }
    }
  }
}
```

### Criterio de éxito
```
Claude Code: "crea un ticket para el bug que encontramos en auth"
→ auth OK → RBAC OK → rate limit OK → pre-validación OK
→ service layer → Claude → Jira → PROJ-003
→ Claude recibe: {"key": "PROJ-003", "status": "created"}
```

---

## Fase 4.1 — Ajustes post-validación e2e ✅

Correcciones aplicadas tras pruebas contra `jira.zurich.com` real (2026-06-19):

| Ajuste | Archivo | Detalle |
|---|---|---|
| `customfield_25832` obligatorio | `jira_client.py` | "Línea de Servicio" = BAU (id 44461) en todos los issues ZNRX |
| Priority por ID | `jira_client.py` | ZNRX solo acepta: Highest (1), High (2), Low (4) — no por nombre |
| Bug issuetype → Task fallback | `jira_client.py` | Validaciones de workflow bloquean Bug vía API en ZNRX |
| Prompts traducidos al español | `service/prompts/*.txt` | `create_issue`, `update_issue`, `search_issues` |
| `TICKET_LANG` env var | `claude_client.py` | `es` (default) / `en`; instrucción de idioma añadida al prompt en runtime |
| `JIRA_TIMEOUT=30` | `.env`, scripts | 10s insuficiente desde WSL; default actualizado |
| Scripts de desarrollo | `scripts/` | `dev.sh` (stop/restart/status/both) + `test-dev.sh` (kill/reinicio automático) |
| Documentación proyectos | `docs/jira-projects.md` | Metadata real de ZNRX, AIPROJECTS, SAZ, SCRX desde API Jira |

**Proyectos configurados:**

| Proyecto | `JIRA_PROJECT_KEY` | `TICKET_LANG` | Propósito |
|---|---|---|---|
| ZNRX | `ZNRX` | `es` | Gestión de requerimientos y desarrollo |
| AIPROJECTS | `AIPROJECTS` | `en` | IA y automatización de negocio (internacional) |
| SAZ | `SAZ` | `es` | Solicitudes Release / DevOps |
| SCRX | `SCRX` | `es` | Desarrollo ágil Ecuador/LATAM |

---

## Fase 4.2 — Deuda técnica: seguridad y confiabilidad ✅

Correcciones aplicadas tras auditoría de deuda técnica (2026-06-19):

| Categoría | Ajuste | Archivo |
|---|---|---|
| **Crítica** | JQL injection — `_jql_escape()` en todos los campos (no solo `text_search`) | `jql_builder.py` |
| **Crítica** | Audit log en MCP — `_audit()` con `request_id` en cada `call_tool()` | `jira_mcp/server.py` |
| **Crítica** | HTTP errors saneados — `sanitize(str(e))` en todos los `HTTPException.detail` | `routes/*.py` |
| **Media** | JSON parsing controlado — `_parse_json()` con `ValueError` descriptivo | `claude_client.py` |
| **Media** | Rate limiter compartido — `shared/rate_limiter.py`; ambas capas instancian `RateLimiter` | `shared/` |
| **Media** | Validación respuesta service layer — `_require()` en `service_client.py` | `jira_mcp/service_client.py` |
| **Media** | SSE timeout — `asyncio.wait_for(timeout=MCP_SSE_TIMEOUT)` en `handle_sse` | `jira_mcp/server.py` |
| **Media** | Audit log con rotación — `RotatingFileHandler` (10 MB × 5 backups) | `service/audit.py` |
| **Baja** | Path conda portable — `scripts/_conda_env.sh`; detecta env sin path hardcodeado | `scripts/` |
| **Baja** | Tests unitarios — `tests/` con 52 tests en 4 módulos de seguridad | `tests/` |

---

## Fase 4.3 — Transiciones y Log Work ✅

Nuevos endpoints para gestión del ciclo de vida del ticket (2026-06-19):

| Endpoint | Descripción |
|---|---|
| `POST /issues/{key}/transition` | Texto libre → Claude → transición Jira. Consulta transiciones disponibles en tiempo real; 422 con lista si el estado no es alcanzable |
| `POST /issues/{key}/worklog` | Texto libre → Claude → worklog Jira. Soporta `time_spent_seconds`, `comment` y `started` (ISO 8601) |

**Archivos añadidos:**
- `service/routes/transitions.py` + `service/routes/worklog.py`
- `service/prompts/transition_issue.txt` + `service/prompts/log_work.txt`
- Schemas: `TransitionIssueRequest/Payload/Response`, `LogWorkRequest/Payload/Response`
- Jira client: `get_transitions()`, `transition_issue()`, `log_work()`
- Claude client: `parse_transition_issue()`, `parse_log_work()`

**Validado e2e:** ZNRX-68128 Open→In Progress→Done + 3 worklogs (7h registradas)

---

## Fase 5 — Soporte multi-proyecto: tickets SAZ vinculados a ZNRX (futura)

**Objetivo**: extender el sistema para crear tickets SAZ (*Solicitudes Release Zurich*) vinculados a un ticket ZNRX existente, cubriendo el flujo oficial de solicitudes DevOps dentro de un proyecto.

### Contexto

Un ticket SAZ **siempre nace asociado a un ZNRX**. El flujo típico:
1. Existe un ticket ZNRX (feature, bug, tarea de desarrollo)
2. El equipo necesita apoyo de Release/DevOps: reinicio, despliegue, repo, accesos, etc.
3. Se crea un SAZ en `jira.zurich.com/projects/SAZ` que queda **linked al ZNRX de origen**
4. El equipo de Release trabaja el SAZ; el ZNRX avanza cuando el SAZ se resuelve

Tipos de solicitud SAZ habituales:
- Reinicios de servicios / ambientes
- Despliegues (Docker, Kubernetes, pipelines CI/CD)
- Gestión de repositorios Git (creación, permisos, ramas)
- Solicitudes de infraestructura (accesos, configs, certificados)

### Relación con ZNRX

El SAZ es **autónomo** — puede crearse sin ningún ticket ZNRX asociado. Sin embargo, la buena práctica del equipo es vincularlo a un ZNRX existente como documentación y justificación de la solicitud.

El sistema debe soportar ambos casos:
- SAZ standalone: sin `znrx_key`
- SAZ vinculado: con `znrx_key` opcional → crea el link `SAZ → ZNRX` vía `POST /rest/api/2/issueLink`

```
SAZ-7176  (standalone — solicitud DevOps sin proyecto asociado)

ZNRX-1234  (proyecto de desarrollo)
    └── SAZ-7177  (link: "relates to" — justificación/contexto del ZNRX)
```

### Decisiones resueltas ✅

| Decisión | Resolución | Fuente |
|---|---|---|
| Link type SAZ→ZNRX | **"Relates"** id `10003` — `POST /rest/api/2/issueLink` | `docs/jira-link-types.md` |
| Campos obligatorios SAZ | Solo `reporter` (automático). Campo relevante: `customfield_25896` (Tipo de Solicitud) | `docs/jira-fields.md` |
| Endpoint | `POST /issues/saz` con `znrx_key` opcional | decisión de diseño |
| Prompt Claude para SAZ | Especializado en lenguaje DevOps + campo `customfield_25896` | pendiente de implementar |
| RBAC | Rol `lead` o superior para crear SAZ | coherente con `update_jira_issue` |
| `znrx_key` | Opcional — link solo se crea si se provee | confirmado |

### Entregables estimados
- `service/routes/saz.py` — endpoint `POST /issues/saz` con `znrx_key` requerido
- `service/clients/jira_client.py` — función `create_saz_issue(znrx_key, payload)` + `link_issues(saz_key, znrx_key, link_type)`
- `service/clients/claude_client.py` — `parse_saz_request(text, znrx_key)` con prompt DevOps
- `service/prompts/saz_create.txt` — prompt especializado
- Herramienta MCP `create_saz_request` con `znrx_key` y `text` como inputs
- `.env.example` con `JIRA_SAZ_PROJECT_KEY=SAZ`

### Criterio de éxito
```bash
# SAZ standalone
python cli/main.py create-saz "solicitar reinicio del servicio de autenticación en producción"
# → SAZ-XXXXX creado
# → output: {"saz_key": "SAZ-XXXXX", "status": "created"}

# SAZ vinculado a ZNRX (buena práctica)
python cli/main.py create-saz "solicitar reinicio del servicio de autenticación en producción" --znrx ZNRX-1234
# 1. → SAZ-XXXXX creado en jira.zurich.com/projects/SAZ
# 2. → issue link SAZ-XXXXX → ZNRX-1234 creado
# → output: {"saz_key": "SAZ-XXXXX", "znrx_key": "ZNRX-1234", "status": "linked"}
```

> **Bloqueantes resueltos** — ver `docs/jira-link-types.md` y `docs/jira-fields.md`. Fase 5 lista para implementar.

---

## Fase 6 — Observabilidad + Caching (opcional / futura)

**Objetivo**: llevar el sistema a producción top-tier con métricas, trazas distribuidas y reducción de carga en Jira.

> No bloqueante para producción. Activar cuando el volumen lo justifique.

### Entregables
- Métricas Prometheus en `/metrics` (service layer + MCP)
- Trazas distribuidas OpenTelemetry con `trace_id` propagado
- Caching 30-60s en `search_jira_issues`
- Dashboard Grafana básico

---

## Estructura de directorios final

```
claude-mcp-jira/
├── cli/
│   └── main.py                  # Typer CLI — 4 comandos
├── service/
│   ├── main.py                  # FastAPI v0.3.0
│   ├── audit.py                 # JSON-lines con request_id
│   ├── routes/                  # issues, update, summarize, search
│   ├── schemas/
│   ├── clients/
│   │   ├── sanitizer.py         # Sanitización extendida
│   │   ├── claude_client.py
│   │   ├── jira_client.py       # PAT Bearer + cert + timeout
│   │   ├── jql_builder.py       # Claude → struct → JQL seguro
│   │   └── rate_limiter.py      # Sliding window por usuario
│   └── prompts/                 # Templates: create, update, summarize, search
├── jira_mcp/
│   ├── server.py                # SSE server — 4 herramientas + audit log
│   ├── auth.py                  # API key + IP allowlist
│   ├── rbac.py                  # Roles y permisos
│   ├── rate_limiter.py          # Rate limit MCP por API key (usa shared/)
│   ├── service_client.py        # Cliente httpx con output filtrado + _require()
│   ├── Dockerfile
│   └── README.md
├── shared/
│   └── rate_limiter.py          # RateLimiter reutilizable (service + jira_mcp)
├── tests/
│   ├── test_sanitizer.py        # 13 tests
│   ├── test_jql_builder.py      # 18 tests (escape + injection)
│   ├── test_auth.py             # 10 tests
│   └── test_rbac.py             # 11 tests
├── docs/
│   ├── jira-projects.md         # Metadata proyectos: ZNRX, AIPROJECTS, SAZ, SCRX
│   ├── jira-fields.md           # Campos requeridos/opcionales por proyecto
│   ├── jira-roles.md            # Permisos efectivos del usuario
│   ├── jira-link-types.md       # 29 link types; recomendación SAZ→ZNRX
│   └── jira-workflows.md        # Statuses y transiciones por proyecto
├── certs/                       # Certificados raíz corporativos Zurich
├── arch/
│   ├── design/
│   ├── evaluations/
│   └── reports/
├── Dockerfile                   # Service layer
├── docker-compose.yml           # service (8000) + mcp (8001)
├── environment.yml
├── .env.example
└── CLAUDE.md
```

---

## Dependencias Python

```
anthropic
fastapi
uvicorn[standard]
httpx
requests
typer
pydantic
python-dotenv
mcp[cli]
starlette
pytest
```

---

## Decisiones de arquitectura

| Decisión | Opción elegida | Motivo |
|---|---|---|
| MCP oficial Atlassian | ❌ Descartado | Solo Jira Cloud; viola políticas de red Zurich |
| N8N / Zapier | ❌ Descartado | Servicios cloud; bloqueados por firewall corporativo |
| Auth Jira | PAT Bearer token | Jira Server/DC no usa Basic Auth con email+token |
| Jira REST API | v2 | v3 es exclusiva de Jira Cloud |
| Descripción tickets | Texto plano | Jira Server no acepta ADF (Atlassian Document Format) |
| SSL | `REQUESTS_CA_BUNDLE` | Certificado raíz corporativo del firewall de Zurich |
| MCP deployment | Servicio Docker interno | Debe vivir en red corporativa para acceder a `jira.zurich.com` |
| Sanitización | Extendida (tokens, IPs RFC1918, hosts internos, stack traces) | Prevenir fuga de datos hacia Claude API |
| JQL | Claude → struct → builder controlado | JQL libre puede generar queries destructivas o masivas |
| Timeout Jira | `JIRA_TIMEOUT=30s` en dev (10s en Docker) | WSL requiere más tiempo; Docker va directo a la red |
| Trazabilidad | `request_id` UUID por operación | Correlacionar logs entre CLI, service y Jira |
| Auth MCP | API key + IP allowlist | Expone capacidades críticas; no debe ser acceso abierto |
| RBAC MCP | dev / lead / system | Principio de menor privilegio por rol |
| Pre-validación MCP | Ligera, antes de llamar al backend | Bloquear abuso sin latencia de red |
| Rate limiting | En MCP (por API key) + service (por usuario) | Defensa en profundidad — dos capas independientes |
| Output MCP | Normalizado (`{key,status}`) | Evitar filtración de datos internos hacia el LLM |
| Session context | `request_id` UUID (sin estado de sesión completo) | Trazabilidad suficiente; sesiones añaden complejidad innecesaria |
| Persistencia MCP | Ninguna — stateless | Sin disco, escalable horizontalmente, menor superficie de ataque |
| Observabilidad | Opcional — Fase 5 | Requiere infra adicional; `request_id` cubre el MVP |
