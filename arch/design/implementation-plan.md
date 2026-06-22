# Plan de Implementación: claude-mcp-jira

Implementación incremental para red empresarial (Jira Server/Data Center en `jira.zurich.com`).
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
- `service/audit.py` — audit log JSON-lines con `request_id`
- `service/clients/jira_client.py` — timeout configurable vía `JIRA_TIMEOUT`
- CLI simplificada a cliente HTTP del service layer
- `Dockerfile` + `docker-compose.yml`

### Seguridad implementada
- **Sanitización extendida**: Bearer tokens, passwords, emails, IPs privadas RFC 1918 (`10.x`, `172.16-31.x`, `192.168.x`), hostnames internos (`*.zurich.com`, `*.internal`, `*.local`), stack traces
- **Audit log**: `request_id` (UUID), `timestamp`, `user`, `action`, `input`, `claude_payload`, `jira_key`, `status`, `error`
- **Timeout Jira**: `JIRA_TIMEOUT=30` (segundos), configurable en `.env`

---

## Fase 3 — Comandos completos + JQL controlado ✅

**Objetivo**: soporte para los 4 comandos CLI con clasificación de intención y queries JQL seguras.

### Entregables
- 4 comandos CLI: `create`, `update`, `summarize`, `list-issues`
- `service/clients/jql_builder.py` — Claude → struct → JQL seguro
- `service/clients/rate_limiter.py` — sliding window por usuario
- Endpoints: `PATCH /issues/{key}`, `GET /issues/{key}/summary`, `POST /issues/search`

### JQL controlado
Claude **no genera JQL directamente**:
- Claude genera struct: `{"assignee": "currentUser()", "issuetype": "Bug", ...}`
- El service layer construye el JQL seguro
- `MAX_RESULTS = 50` fijo, sin excepciones

---

## Fase 4 — MCP Server (servicio deployable interno) ✅

**Objetivo**: exponer la integración como MCP server SSE desplegable en red interna con auth, RBAC y protecciones en dos capas.

### Entregables
- `jira_mcp/server.py` — SSE server, herramientas core, delega al service layer
- `jira_mcp/auth.py` — API key + IP allowlist por CIDR
- `jira_mcp/rbac.py` — roles dev/lead/system, mapeo API key → rol
- `jira_mcp/service_client.py` — output filtrado antes de devolver al LLM
- `jira_mcp/Dockerfile` + `docker-compose.yml` actualizado

### Protecciones MCP (segunda capa sobre el service layer)

| Control | Implementación |
|---|---|
| API key | `X-API-Key` header, `MCP_API_KEY` |
| IP allowlist | CIDRs `10.0.0.0/8`, `192.168.0.0/16` |
| RBAC | dev (create/get/search) · lead (+update/assign/priority/saz) · system (todo) |
| Pre-validación | input vacío o >2000 chars rechazado antes de llamar al backend |
| Rate limiting | `MCP_RATE_LIMIT_MAX_CALLS=10/60s` por API key |
| Output normalizado | LLM recibe solo `{key,status}` o `{key,summary}` |

### Configuración `.claude/settings.json`
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

---

## Fase 4.1 — Ajustes post-validación e2e ✅

Correcciones aplicadas tras pruebas contra `jira.zurich.com` real (2026-06-19):

| Ajuste | Archivo | Detalle |
|---|---|---|
| `customfield_25832` obligatorio | `jira_client.py` | "Línea de Servicio" = BAU (id 44461) en todos los issues ZNRX top-level |
| Priority por ID | `jira_client.py` | ZNRX solo acepta: Highest (1), High (2), Low (4) — no por nombre |
| Bug issuetype → Task fallback | `jira_client.py` | Validaciones de workflow bloquean Bug vía API en ZNRX |
| Prompts traducidos al español | `service/prompts/*.txt` | `create_issue`, `update_issue`, `search_issues` |
| `TICKET_LANG` env var | `claude_client.py` | `es` (default) / `en`; instrucción de idioma añadida al prompt en runtime |
| `JIRA_TIMEOUT=30` | `.env`, scripts | 10s insuficiente desde WSL; default actualizado |
| Scripts de desarrollo | `scripts/` | `dev.sh` (stop/restart/status/both) + `test-dev.sh` (kill/reinicio automático) |
| Documentación proyectos | `docs/jira-projects.md` | Metadata real de ZNRX, AIPROJECTS, SAZ, SCRX desde API Jira |

---

## Fase 4.2 — Deuda técnica: seguridad y confiabilidad ✅

| Categoría | Ajuste | Archivo |
|---|---|---|
| **Crítica** | JQL injection — `_jql_escape()` en todos los campos | `jql_builder.py` |
| **Crítica** | Audit log en MCP — `_audit()` con `request_id` en cada `call_tool()` | `jira_mcp/server.py` |
| **Crítica** | HTTP errors saneados — `sanitize(str(e))` en todos los `HTTPException.detail` | `routes/*.py` |
| **Media** | JSON parsing controlado — `_parse_json()` con `ValueError` descriptivo | `claude_client.py` |
| **Media** | Rate limiter compartido — `shared/rate_limiter.py` | `shared/` |
| **Media** | Validación respuesta service layer — `_require()` en `service_client.py` | `jira_mcp/service_client.py` |
| **Media** | SSE timeout — `asyncio.wait_for(timeout=MCP_SSE_TIMEOUT)` | `jira_mcp/server.py` |
| **Media** | Audit log con rotación — `RotatingFileHandler` (10 MB × 5 backups) | `service/audit.py` |
| **Baja** | Path conda portable — `scripts/_conda_env.sh` | `scripts/` |
| **Baja** | Tests unitarios — 52 tests en 4 módulos de seguridad | `tests/` |

---

## Fase 4.3 — Transiciones y Log Work ✅

| Endpoint | Descripción |
|---|---|
| `POST /issues/{key}/transition` | Texto libre → Claude → transición Jira. Consulta transiciones disponibles en tiempo real; 422 con lista si el estado no es alcanzable |
| `POST /issues/{key}/worklog` | Texto libre → Claude → worklog Jira. Soporta `time_spent_seconds`, `comment` y `started` (ISO 8601) |

**Validado e2e:** ZNRX-68128 Open→In Progress→Done + 3 worklogs (7h registradas)

---

## Fase 4.4 — Mejoras API ✅

Basado en `arch/evaluations/eval-apis-copilot.md` y `arch/evaluations/eval-swagger-copilot.md`.

> Un issue en Jira no es un recurso CRUD genérico — es un aggregate con acciones explícitas.  
> Endpoints específicos por acción → mejor control, mejor auditoría, mejor uso por Claude/MCP.

### Endpoints añadidos

| Endpoint | Tool MCP | Rol mínimo |
|---|---|---|
| `POST /issues/{key}/comments` | `add_comment_jira_issue` | dev |
| `POST /issues/{key}/assign` | `assign_jira_issue` | lead |
| `POST /issues/{key}/priority` | `set_priority_jira_issue` | lead |
| `POST /issues/{key}/labels` | — | — |
| `POST /issues/{key}/clone` | — | — |

**Restricción ZNRX subtasks (clone):** Los subtasks (`Subtarea Historia`) tienen un screen diferente que no expone `customfield_25832` ni `priority`. `clone_issue()` detecta si hay `parent` y omite esos campos para subtasks.

**Swagger:** deshabilitado en prod (`APP_ENV=prod` → `docs_url=None`).

---

## Fase 4.5 — Link dinámico ✅

Basado en `arch/evaluations/eval-link-copilot.md`.

| Mejora | Detalle |
|---|---|
| `GET /issue-link-types` | Tipos reales de Jira con cache TTL 1h en memoria; devuelve 29 tipos en `jira.zurich.com` |
| `POST /issues/{key}/link` | Claude recibe la lista real antes de elegir el tipo |
| `link_issue()` usa `{"type": {"name": "..."}}` | Portátil entre instancias Jira; no depende de IDs hardcodeados |

MCP tool `link_jira_issues` disponible para rol `dev`.

---

## Fase 5 — Soporte SAZ ✅

**Objetivo**: crear tickets SAZ (*Solicitudes Release Zurich*) desde texto libre, con link opcional a un ZNRX existente.

### Contexto

Un SAZ **siempre nace en el proyecto SAZ** y habitualmente se vincula a un ZNRX como documentación de la solicitud DevOps (reinicios, deploys, repos, accesos, infraestructura).

### Endpoint

```
POST /issues/saz
{"text": "reiniciar servicio auth en producción", "znrx_key": "ZNRX-1234"}
```

- Claude clasifica el tipo: `Support` (default), `Incident` (urgente/producción caída), `Nueva Iniciativa` (nueva infra)
- Si se provee `znrx_key` → link `Relates` SAZ→ZNRX automático
- RBAC: rol `lead` o superior

### Entregables
- `service/routes/saz.py` — endpoint `POST /issues/saz`
- `service/prompts/saz_create.txt` — prompt especializado en lenguaje DevOps/Release
- MCP tool `create_saz_request` (lead) con `text` + `znrx_key` opcional
- `JIRA_SAZ_PROJECT_KEY=SAZ` en `.env.example`

### Criterio de éxito
```bash
# SAZ standalone
POST /issues/saz {"text": "solicitar reinicio del servicio de autenticación en producción"}
→ {"saz_key": "SAZ-7403", "znrx_key": null, "status": "created"}

# SAZ vinculado a ZNRX
POST /issues/saz {"text": "...", "znrx_key": "ZNRX-68171"}
→ {"saz_key": "SAZ-7403", "znrx_key": "ZNRX-68171", "status": "linked"}
```

**Validado e2e:** ZNRX-68171 + SAZ-7403 linked (2026-06-22)

---

## Fase 6 — Observabilidad + Caching (futura)

> No bloqueante para producción. Activar cuando el volumen lo justifique.

- Métricas Prometheus en `/metrics` (service layer + MCP)
- Trazas distribuidas OpenTelemetry con `trace_id` propagado
- Caching 30-60s en `search_jira_issues`
- Dashboard Grafana básico

---

## Fase 7 — Multi-proyecto ✅

Basado en `arch/evaluations/eval-multiproject-copilot.md`.

**Objetivo**: operar contra múltiples proyectos Jira con configuración por proyecto y routing dinámico.

### Cambios principales

| Cambio | Archivo |
|---|---|
| `project` opcional en `POST /issues` y `POST /issues/search` | `service/routes/issues.py`, `search.py` |
| `resolve_project()` — valida, descubre y devuelve la config | `service/clients/project_config.py` |
| `create_issue()`, `update_issue()`, `set_priority()` usan config dinámica | `jira_client.py` |
| `build_jql(struct, project_key)` — prepend `project = "KEY"` | `jql_builder.py` |
| `JIRA_DEFAULT_PROJECT` + `JIRA_ALLOWED_PROJECTS` | `.env` / `.env.example` |
| MCP tools `create_jira_issue` y `search_jira_issues` aceptan `project` | `jira_mcp/server.py` |
| CLI `create` y `list-issues` aceptan `--project` flag | `cli/main.py` |
| `TICKET_LANG` per-proyecto según config | `claude_client.py` |

---

## Fase 7b — SQLite auto-discovery ✅

**Objetivo**: registro de proyectos persistente con descubrimiento automático — cualquier proyecto Jira válido funciona sin intervención admin.

### Motivación
Compartir el MCP server con otros equipos implica que usuarios distintos accederán a proyectos no previstos. En lugar de mantener un dict hardcodeado, el sistema descubre y registra nuevos proyectos en el primer acceso.

### Flujo get_or_discover()

```
1. DB lookup (SQLite) → si existe, devuelve config inmediatamente
2. Si no existe:
   a. GET /rest/api/2/project/{key} — verifica que el proyecto exista en Jira (400 si 404)
   b. GET /rest/api/2/issue/createmeta?projectKeys={key} — extrae campos requeridos (opcional; 403/404 ignorado)
   c. INSERT INTO projects (source: "jira_auto") con config deducida o default
   d. Devuelve config recién creada
```

### Proyectos seeded al startup (source: `seed`)

| Proyecto | priority_format | required_custom | issuetype_fallback | ticket_lang |
|---|---|---|---|---|
| ZNRX | id (1/2/4) | customfield_25832=BAU | Bug→Task, Improvement→Task | es |
| AIPROJECTS | name | — | — | en |
| SCRX | name | — | — | es |

### Endpoints

| Endpoint | Descripción |
|---|---|
| `GET /projects` | Lista todos los proyectos registrados en DB |
| `GET /projects/{key}` | Config de un proyecto; dispara discovery si no existe |

### Entregables
- `service/clients/project_db.py` — SQLite con `init_db`, `seed`, `get_or_discover`, `list_projects`
- `service/clients/project_config.py` — fachada delgada: `get_config()`, `resolve_project()`
- `service/routes/projects.py` — `GET /projects`, `GET /projects/{key}`
- `service/main.py` — lifespan: `init_db()` + seed ZNRX/AIPROJECTS/SCRX; v0.4.0
- `PROJECT_DB_PATH` env var (default: `projects.db`)
- Thread-safe: `threading.Lock()` para writes

---

## Fase 8 — Interfaz UI (futura)

> Ver evaluación completa en `arch/evaluations/eval-ui-copilot.md` antes de implementar.

**Objetivo**: complementar el acceso CLI/MCP con una interfaz web ligera para usuarios no técnicos.

### Líneas a evaluar
- Stack tecnológico (htmx+FastAPI vs. React standalone vs. extensión VS Code)
- Alcance: ¿read-only (consulta/resumen) o también write (crear/actualizar)?
- Auth de usuario en UI vs. API key de servicio
- La UI consumiría los mismos endpoints del service layer existente

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
| Timeout Jira | `JIRA_TIMEOUT=30s` | WSL requiere más tiempo desde red corporativa |
| Trazabilidad | `request_id` UUID por operación | Correlacionar logs entre CLI, service y Jira |
| Auth MCP | API key + IP allowlist | Expone capacidades críticas; no debe ser acceso abierto |
| RBAC MCP | dev / lead / system | Principio de menor privilegio por rol |
| Pre-validación MCP | Ligera, antes de llamar al backend | Bloquear abuso sin latencia de red |
| Rate limiting | MCP (por API key) + service (por usuario) | Defensa en profundidad — dos capas independientes |
| Output MCP | Normalizado (`{key,status}`) | Evitar filtración de datos internos hacia el LLM |
| Persistencia MCP | Ninguna — stateless | Sin disco, escalable horizontalmente, menor superficie de ataque |
| Registro proyectos | SQLite + auto-discovery lazy | Soporte multi-equipo sin admin; cualquier proyecto Jira válido funciona en el primer acceso |
| Allowlist proyectos | Opcional (`JIRA_ALLOWED_PROJECTS`) | Si está vacía, cualquier proyecto Jira válido es aceptado; si está poblada, restringe |
| Link types | Consultados en tiempo real + cache 1h | Portable entre instancias Jira; no depende de IDs hardcodeados |
| Endpoints | Commands explícitos por acción | Issue Jira = aggregate; mejor auditoría y uso por Claude/MCP |
| `/actions` genérico | Long-tail tipado (enum) | Acciones poco frecuentes sin endpoint propio; tipado previene abuso |
| Swagger en producción | Deshabilitado (`APP_ENV=prod`) | Evitar exposición de contratos internos; disponible solo en `dev` |
| Observabilidad | Opcional — Fase 6 | Requiere infra adicional; `request_id` cubre el MVP |
