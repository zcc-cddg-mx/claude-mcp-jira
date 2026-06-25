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

## Pendiente de decisión — Allowlist self-service

**Contexto**: validado con el proyecto ARQX (2026-06-22) — `GET /projects/ARQX` dispara auto-discovery correctamente y persiste la config en DB, pero `POST /issues {project: "ARQX"}` devuelve 400 porque `JIRA_ALLOWED_PROJECTS=ZNRX,AIPROJECTS,SCRX` lo bloquea antes de llegar a Jira.

**Resuelto (2026-06-25)**: `JIRA_ALLOWED_PROJECTS` vaciado en `.env` y `.env.example`. La seguridad la ejerce el PAT de Jira (403/404 si el usuario no tiene permisos) y el token Azure en code-agent-mcp. La allowlist queda disponible como restricción opcional. Fase 8 UI la populará dinámicamente con los proyectos accesibles según el PAT del usuario.

**Cambio necesario**: solo `.env` + reinicio del service layer. Sin cambios de código.

**Pendiente de decisión** con el equipo antes de aplicar en producción.

---

## Fase 8a — PAT dinámico por usuario

**Objetivo**: permitir que cada usuario opere con su propia identidad Jira en lugar de la cuenta de servicio compartida, sin infraestructura adicional.

### Problema

El `JIRA_PAT` en `.env` es un único PAT de cuenta de servicio. Todos los tickets se crean con esa identidad — en Jira aparecen como del mismo autor, independientemente de quién ejecutó la acción.

### Solución: header `X-Jira-Token` opcional

El service layer acepta un header `X-Jira-Token` en cada request. Si está presente, sobreescribe el PAT de `.env` para esa llamada. Si no, usa el PAT de servicio como fallback.

```
Request con X-Jira-Token:
  → jira_client usa ese PAT → ticket aparece como autor real en Jira

Request sin X-Jira-Token:
  → jira_client usa JIRA_PAT del .env → comportamiento actual (cuenta de servicio)
```

### Por qué esta opción

| Opción | Coste | Autoría correcta | Infraestructura |
|---|---|---|---|
| A — `X-Jira-Token` header (esta) | Bajo — horas | ✅ Sí | Ninguna |
| B — PAT único de servicio (actual) | Cero | ❌ No | Ninguna |
| C — Vault / DB cifrada (Fase 8 UI) | Alto — días | ✅ Sí | Vault o cifrado |

La Opción A desbloquea multi-usuario hoy. La Opción C es la evolución natural cuando se implemente la UI (Fase 8) — el login almacenaría el PAT en sesión y lo propagaría en cada request de forma transparente.

### Cambios necesarios

**`service/clients/jira_client.py`** — leer el token de contexto:

```python
# Variable de contexto por request (threading o contextvars)
_request_pat: ContextVar[str | None] = ContextVar("request_pat", default=None)

def _get_headers() -> dict:
    pat = _request_pat.get() or _JIRA_PAT
    return {"Authorization": f"Bearer {pat}", "Accept": "application/json"}
```

**Middleware o dependency en FastAPI** — extraer el header y inyectarlo en el contexto:

```python
# service/middleware/jira_auth.py
async def jira_auth_middleware(request: Request, call_next):
    token = request.headers.get("X-Jira-Token")
    if token:
        _request_pat.set(token)
    return await call_next(request)
```

**MCP server** — propagar el header si el cliente lo pasa en el tool call:

```python
# jira_mcp/server.py — añadir parámetro opcional jira_token a cada tool
# El MCP server lo reenvía como X-Jira-Token al service layer
```

### Flujo de uso (CLI y MCP)

```bash
# CLI — con PAT propio
X_JIRA_TOKEN=<mi-pat> python cli/main.py create "bug login en producción"

# Service layer directo
curl -X POST http://localhost:18000/issues \
  -H "X-Jira-Token: <mi-pat>" \
  -H "x-user: carlos.duarte2" \
  -d '{"text": "bug login en producción"}'

# MCP tool — Claude Code pasa el token si está configurado
# (o usa el de servicio si no se configura)
```

### Seguridad

- El token viaja solo dentro de la red corporativa (HTTP interno)
- El service layer nunca loguea el valor del PAT — solo loguea si estaba presente (`pat_source: header | env`)
- Sanitizer ya elimina patrones de token de los audit logs
- La validación del PAT la hace Jira — si es inválido, devuelve 401 que se propaga como 502

### Entregables

- `service/clients/jira_client.py` — `ContextVar` + `_get_headers()` dinámico
- `service/middleware/jira_auth.py` — extrae `X-Jira-Token` y lo inyecta en contexto
- `service/main.py` — registrar middleware
- `jira_mcp/server.py` — parámetro `jira_token` opcional; propagado como header al service layer
- `service/audit.py` — añadir campo `pat_source: "header" | "env"` al audit log
- Tests unitarios: header presente sobreescribe env; sin header usa env; token nunca en logs

### Criterio de éxito

```bash
# Con PAT propio: ticket en Jira aparece como autor "carlos.duarte2"
curl -X POST http://localhost:18000/issues \
  -H "X-Jira-Token: <pat-carlos>" -H "x-user: carlos.duarte2" \
  -d '{"text": "[MCP Claude Jira Test] con PAT propio"}'
→ ticket creado con reporter = carlos.duarte2 en Jira

# Sin header: usa cuenta de servicio (comportamiento actual)
curl -X POST http://localhost:18000/issues \
  -H "x-user: carlos.duarte2" \
  -d '{"text": "[MCP Claude Jira Test] sin PAT header"}'
→ ticket creado con reporter = cuenta de servicio
```

### Relación con otras fases

- **Fase 8 (UI)**: el login captura el PAT, lo guarda en sesión JWT, y lo propaga automáticamente en cada request como `X-Jira-Token`. El usuario no necesita gestionarlo manualmente.
- **Fase 9 (Git Intelligence)**: `sync_git_worklogs` acepta `jira_token` opcional para registrar worklogs con la identidad correcta.

---

## Fase 8 — Interfaz UI

> Evaluación basada en `arch/evaluations/eval-ui-copilot.md`.

**Objetivo**: complementar el acceso CLI/MCP con una interfaz web ligera para usuarios no técnicos del equipo Zurich.

### Evaluación

#### Valor real para el proyecto

El sistema actual ya cubre a usuarios técnicos vía CLI y Claude Code MCP. La UI añade valor principalmente para:
- Usuarios que no usan el terminal (PMs, analistas, stakeholders)
- Flujo "human-in-the-loop" con preview antes de crear/modificar tickets
- Dashboard de actividad y auditoría visual

La evaluación externa (`eval-ui-copilot.md`) confirma que es viable y diferenciador, pero implica infraestructura adicional (sesiones, JWT, posiblemente Vault para PAT).

#### Decisión de stack

| Opción | Coste | Cuando usar |
|---|---|---|
| Streamlit | Bajo — 1-2 días | MVP interno rápido; validar demanda real |
| htmx + FastAPI | Medio — 1 semana | Si se quiere SPA sin JS moderno |
| Next.js / React | Alto — 2-3 semanas | Si la UI se convierte en producto propio |

**Recomendación**: empezar con Streamlit sobre los endpoints del service layer existente. Si hay demanda demostrada, migrar a Next.js.

#### Arquitectura

```
[Streamlit / React]  ──REST──►  [Service Layer FastAPI]  ──►  [Jira / Claude]
                                 ▲
                        NO pasa por el MCP server
```

La UI habla directamente con el service layer. El MCP server es solo para Claude Code.

#### Auth

```
POST /auth/login {"jira_pat": "..."}
→ backend valida PAT contra Jira
→ devuelve JWT {user_id, projects, roles, expiration}
→ PAT nunca llega al frontend
```

Implica añadir `POST /auth/login` y `GET /me` al service layer.

#### Alcance MVP recomendado (Fase 8.1)

1. Login con PAT → sesión JWT
2. Crear ticket con preview (AI + human-in-the-loop)
3. Buscar y resumir tickets

#### Alcance avanzado (Fase 8.2+, solo si el MVP tiene adopción)

- Dashboard de historial / auditoría
- Configuración por usuario (proyecto default, idioma)
- Governance UI (aprobar acciones críticas)
- Admin panel (gestión API keys MCP, rate limits, roles)

#### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| PAT expuesto en frontend | PAT nunca sale del backend; solo se emite JWT |
| Sesiones y expiración | JWT con `expiration`; validar en cada request |
| Scope creep | Empezar con Streamlit read-only+create; no construir admin panel sin demanda |
| Esfuerzo vs. adopción | Medir si los no-técnicos realmente usarían la UI antes de invertir en Next.js |

#### Estado

**Pendiente de evaluación de demanda.** Implementar solo si hay usuarios no técnicos concretos que lo requieran. El service layer ya expone todos los endpoints necesarios — la UI es solo la capa de presentación.

---

## Fase 9 — Git Intelligence ✅ Completa (9.1–9.4) / Futura (9.5)

> Evaluación basada en `arch/evaluations/eval-git-copilot.md`.

**Objetivo**: leer repos Git locales, mapear commits a tickets Jira y registrar worklogs automáticamente. Convierte el sistema en un "Engineering Productivity Copilot".

### Evaluación

#### Valor real

El registro manual de worklogs es la fricción más alta del flujo actual. Los commits ya contienen información suficiente para inferir qué ticket se trabajó y cuánto tiempo se dedicó. La propuesta es automatizar ese mapeo con validación humana antes de registrar.

#### Flujo principal

```
1. git log --since=... (repo local)
2. Agrupar commits en sesiones (delta < 2h = misma sesión)
3. Extraer issue key: regex [A-Z]+-\d+ en mensaje o nombre de rama
4. Si no hay key: Claude como fallback (solo metadata, nunca código completo)
5. Estimar tiempo: timestamps + LOC cambiados + Claude
6. Preview: usuario revisa y ajusta antes de registrar
7. POST /issues/{key}/worklog para cada sesión confirmada
```

#### Seguridad crítica

- **No enviar código a Claude** — solo mensajes de commit, nombres de archivo y LOC count
- Sanitizar todo input antes de pasar a Claude (reutilizar `sanitizer.py`)
- Procesamiento local — ningún dato de código sale de la red interna

#### Estrategias de correlación Git → Jira (por precedencia)

1. **Regex en mensaje de commit**: `r"[A-Z]+-\d+"` — ej. `ZNRX-68171 fix auth timeout`
2. **Nombre de rama**: `feature/ZNRX-68171-login-fix` → `ZNRX-68171`
3. **Claude fallback**: si no hay key — prompt con mensaje + archivos modificados, sin contenido de código

#### Estimación de tiempo (heurística combinada)

```python
# 1. Delta entre commits
delta = commit_n.timestamp - commit_n_minus_1.timestamp
if delta < timedelta(hours=2): misma_sesion()

# 2. Límites por sesión
min_session = timedelta(minutes=15)
max_session = timedelta(hours=4)

# 3. Ajuste por tamaño
if loc_changed > 200: sesion *= 1.2

# 4. Claude mejora la estimación (opcional, solo en modo pro)
# Input: mensajes de commit + LOC (no el diff completo)
```

#### Componentes implementados

```
service/
└── git/
    ├── scanner.py       — subprocess git log (metadata only, nunca código)
    ├── analyzer.py      — group_sessions(), estimate_time() con LOC nudge
    ├── mapper.py        — extract_issue_key() regex + Claude fallback
    └── repo_registry.py — SQLite git_repos: name/alias → path/origin/defaults

service/routes/
    ├── git_sync.py      — POST /git/sync (repo_name | repo_path | default)
    └── git_repos.py     — CRUD POST/GET/DELETE /git/repos

service/prompts/
    └── git_sync_fallback.txt — prompt Claude NLP (mensajes + branch, sin código)
```

#### Tools MCP implementadas

| Tool | Rol | Descripción |
|---|---|---|
| `sync_git_worklogs` | dev+ | Sincroniza worklogs desde repo. Acepta `repo_name` o `repo_path`. `dry_run=true` por defecto. |
| `register_git_repo` | dev+ | Registra alias de repo con proyecto y ticket default |
| `list_git_repos` | dev+ | Lista repos registrados en el registry |

#### Endpoints service layer implementados

```http
POST /git/sync
{ "repo_name": "auth-service", "since_days": 1, "dry_run": true }
→ {sessions: [{issue_key, estimated_hours, commits, confidence, worklog_registered}]}

POST   /git/repos        — registrar/actualizar alias (origin auto-detectado)
GET    /git/repos        — listar todos
GET    /git/repos/{name} — obtener uno
DELETE /git/repos/{name} — eliminar
```

#### Repo registry — fallback en cascada

```
1. repo_name  → busca por alias en git_repos
2. repo_path  → busca por path o usa directamente
3. (ninguno)  → usa repo con is_default=1
Para sesiones sin key: regex → Claude NLP → default_issue_key del repo (confidence=low)
```

#### Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `GIT_SESSION_GAP_MINUTES` | `120` | Minutos de inactividad que separan sesiones |
| `GIT_MIN_SESSION_MINUTES` | `15` | Mínimo de minutos por sesión |
| `GIT_MAX_SESSION_MINUTES` | `240` | Máximo de minutos por sesión |
| `GIT_LOC_NUDGE_THRESHOLD` | `200` | LOC mínimas para aplicar nudge +20% |
| `GIT_CLAUDE_FALLBACK` | `true` | Activar fallback Claude NLP para commits sin key |

#### Sub-fases

| Sub-fase | Descripción | Estado |
|---|---|---|
| 9.1 | Scanner + mapper (regex + rama) + endpoint `/git/sync` dry_run | ✅ Completa |
| 9.2 | Estimación de tiempo + registro real de worklogs | ✅ Completa |
| 9.3 | MCP tool `sync_git_worklogs` + Claude fallback | ✅ Completa |
| 9.4 | Repo registry SQLite + CRUD + MCP tools register/list | ✅ Completa |
| 9.5a | Claude humanizer — ajuste semántico de estimaciones | ✅ Completa |
| 9.5b | Human-sensity — factores multiplicadores + learning layer por usuario | Futura — requiere Fase 10 + UI |

#### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Sobreestimación de horas | `dry_run=true` por defecto; clamp min/max configurable |
| Commits sin ticket | Fallback Claude NLP → `default_issue_key` del repo → sin registrar |
| Privacidad del código | Solo metadata a Claude — mensajes, branch, LOC; nunca el diff |
| Mono-repo / múltiples proyectos | Repo registry con `default_issue_key` y `jira_project` por repo |
| Estimaciones mecánicas | Fase 9.5 — human-sensity con señales contextuales y edición manual |

#### Fase 9.5a — Claude humanizer ✅ Completa (2026-06-23)

Ajuste semántico de estimaciones git con Claude antes de registrar worklogs:

- `service/prompts/git_humanizer.txt` — detecta señales: debugging keywords, alta complejidad (LOC>400), trabajo nocturno (20–23h / 0–5h)
- `parse_git_humanizer(session)` en `claude_client.py` — devuelve multiplicador; clamp 0.25–4.0h, redondeo 0.25h; falla silenciosamente al valor base
- `GitSessionResult` — campo `base_estimated_hours` (solo cuando hay ajuste) + `humanizer_reason`
- Flag `GIT_HUMANIZER=true` en `.env.example`

#### Estado

**Fases 9.1–9.4 + 9.5a completadas.** El sistema lee repos Git locales, extrae issue keys, estima sesiones de trabajo con ajuste semántico Claude y registra worklogs en Jira con `dry_run=true` por defecto. Pendiente: Fase 9.5b (human factors + learning layer, requiere UI).

---

## Fase 11 — Integración code-agent-mcp ✅ Completa (2026-06-23)

**Objetivo**: delegar las operaciones git y Azure DevOps PR al servicio `code-agent-mcp` ya funcional.

### Nuevo módulo: `service/clients/code_agent_client.py`

Cliente httpx hacia `code-agent-mcp`. Auth: `X-Agent-Token: {CODE_AGENT_TOKEN}`.

```python
CODE_AGENT_URL=http://code-agent-mcp:5001   # default
CODE_AGENT_TOKEN=                            # mismo valor que TOKEN_AZURE del agente
CODE_AGENT_TIMEOUT=30
```

Funciones: `run_task()`, `get_task_status()`, `prepare_and_pr()`, `get_pr_status()`.

### MCP tools añadidos

| Tool | Rol | Endpoint code-agent |
|---|---|---|
| `run_code_agent` | lead | `POST /run` — encola tarea git; 202 inmediato + `task_id` |
| `get_code_agent_status` | dev | `GET /status/{task_id}` — estado + steps + branch + commit_id |
| `create_azure_pull_request` | lead | `POST /azure/prepare-and-pr` — idempotente |
| `get_pull_request_status` | dev | `GET /azure/pull-requests/{pr_id}` — estado PR + build CI |

### `jira_mcp/service_client.py`

`_agent_client()` — cliente httpx independiente del `_client()` Jira (diferente URL, auth y timeout).

### Criterio de éxito

```bash
bash scripts/test-code-agent.sh   # 19/19 tests (schema, dispatch, funciones, env vars)
```

Flujo completo validado con PRs #2552–#2554 reales en Azure DevOps Zurich Insurance Ecuador.

---

## Fase 10 — Workflow Orchestrator ✅ Completa (2026-06-25)

**Objetivo**: formalizar la orquestación implícita Jira→git→PR en una entidad `WorkflowExecution` persistida en SQLite, con 4 endpoints REST y 2 MCP tools.

**Evaluación**: `arch/evaluations/eval-workflow-copilot.md` — arquitectura validada; orquestación dispersa identificada como deuda crítica antes de construir UI.

**Diseño completo**: `arch/workflows/workflow-orchestrator.md`.

### Decisiones de diseño

- El MCP tool ejecuta los pasos secuencialmente y hace el polling
- El service layer solo persiste estado (`WorkflowExecution` en SQLite)
- Entry point es un `issue_key` ya existente (ZNRX-123)

### Archivos creados

| Archivo | Responsabilidad |
|---|---|
| `service/clients/workflow_store.py` | SQLite tabla `workflow_executions` — 5 funciones CRUD |
| `service/schemas/workflow_schemas.py` | Pydantic: `CreateFeaturePRRequest`, `WorkflowExecutionResponse`, `WorkflowStepStatus`, `WorkflowUpdateRequest` |
| `service/routes/workflows.py` | `POST /create-feature-pr`, `GET /{id}`, `GET /`, `PATCH /{id}` |

### Workflow `CreateFeaturePR` — 6 steps

1. `preview` — `POST /azure/prepare-and-pr/preview` (detecta base_branch + files, dry-run)
2. `run_agent` — `POST /run` → task_id
3. `wait_agent` — polling `GET /status/{task_id}` (max 60 × 5s = 5 min)
4. `create_pr` — `POST /azure/prepare-and-pr` (idempotente)
5. `wait_ci` — polling `GET /azure/pull-requests/{pr_id}` (max 120 × 15s = 30 min)
6. `update_jira` — comentario con link PR en el ticket Jira

### Tests

`scripts/test-code-agent.sh` — 32/32 (7 secciones: schema Fase 11, dispatch, funciones, env vars, schema Fase 10, RBAC, workflow_store).

### MCP tools nuevos

- `run_create_feature_pr_workflow` (lead) — orquesta los 6 steps + persiste progreso
- `get_workflow_status` (dev) — consulta estado por `execution_id`

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
