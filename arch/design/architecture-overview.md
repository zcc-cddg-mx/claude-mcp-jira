# Arquitectura General — claude-mcp-jira

**Proyecto**: claude-mcp-jira  
**Entorno**: red corporativa Zurich — Jira Server/Data Center (`jira.zurich.com`)  
**Fecha**: Junio 2026 — estado post-Fase 4

---

## 1. Visión general

Sistema de tres capas que permite gestionar tickets Jira en lenguaje natural desde la CLI y desde Claude Code, sin exponer datos internos ni depender de servicios cloud externos.

```
[CLI (Typer)]     ──HTTP──►
                            [Service Layer (FastAPI :8000)] ──► [LiteLLM proxy → Claude API]
[MCP Server SSE]  ──HTTP──►                                 ──► [Jira REST API v2]
     :8001                                                        jira.zurich.com
       ▲
[Claude Code]
```

**Principio central**: el MCP server y la CLI nunca llaman a Claude ni a Jira directamente. Todo pasa por el service layer, que concentra la sanitización, el audit log y la lógica de negocio.

---

## 2. Capas y responsabilidades

### 2.1 Capa de entrada

| Componente | Tecnología | Puerto | Invocado por |
|---|---|---|---|
| CLI | Python / Typer | — | Desarrollador en terminal |
| MCP Server | Python / SDK `mcp` + Starlette SSE | 8001 | Claude Code (LLM) |

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
| `/issues` | POST | Crear ticket desde texto libre |
| `/issues/{key}` | PATCH | Actualizar ticket desde texto libre |
| `/issues/{key}/summary` | GET | Resumen Claude del ticket |
| `/issues/search` | POST | Búsqueda NL → JQL controlado (máx. 50) |
| `/health` | GET | Health check |

Responsabilidades exclusivas del service layer:
- **Sanitización**: elimina tokens, IPs RFC1918, hostnames internos (`*.zurich.com`, `*.internal`), stack traces antes de enviar a Claude
- **Audit log**: JSON-lines con `request_id` UUID por operación (`AUDIT_LOG_PATH`)
- **JQL controlado**: Claude genera un struct → el service layer construye el JQL seguro (nunca JQL libre)
- **Rate limiting por usuario**: sliding window (30 calls/60s)
- **Timeouts**: `JIRA_TIMEOUT` para Jira, `MCP_SERVICE_TIMEOUT` para el MCP server

### 2.3 Clientes externos

| Cliente | Destino | Auth | Cert |
|---|---|---|---|
| `claude_client.py` | LiteLLM proxy → Claude API | `ANTHROPIC_AUTH_TOKEN` | Firewall Zurich |
| `jira_client.py` | `jira.zurich.com` REST API v2 | `Bearer <JIRA_PAT>` | `zurich-root-ca.crt` |

---

## 3. Flujos de datos

### 3.1 Crear ticket desde CLI

```
cli/main.py create "bug login en producción prioridad alta"
    │
    ▼ POST /issues {"text": "...", "user": "carlos.duarte2"}
service/routes/issues.py
    │
    ├─► sanitizer.py  →  texto limpio (sin IPs, tokens, hosts internos)
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
    ▼ MCP call: create_jira_issue(text="bug de autenticación")
mcp/server.py
    ├─► verify_api_key + verify_ip + check_permission + rate_check
    ├─► pre-validación (vacío / tamaño)
    └─► mcp/service_client.py  →  POST http://service:8000/issues
                                         (mismo flujo que 3.1)
    │
    ▼ {"key": "ZNRX-1234", "status": "created"}  ← output normalizado al LLM
```

### 3.3 Búsqueda con JQL controlado

```
"mis bugs abiertos de esta semana"
    │
    ▼ claude_client.parse_search_query()
    │   → struct: {assignee: "currentUser()", issuetype: "Bug", date_range: "last_week"}
    ▼ jql_builder.build_jql(struct)
    │   → "assignee = currentUser() AND issuetype = "Bug" AND created >= -7d ORDER BY created DESC"
    ▼ jira_client.search_issues(jql, max_results=50)
```

Claude nunca genera JQL directamente — solo el struct de parámetros controlados.

---

## 4. Proyectos Jira

| Key | Nombre | Uso | Estado |
|---|---|---|---|
| `ZNRX` | Proyecto de desarrollo | Tickets de features, bugs y tareas del equipo | Activo |
| `SAZ` | Solicitudes Release Zurich | Reinicios, deploys, repos, accesos DevOps | Fase 5 — futura |

### Relación ZNRX ↔ SAZ

Un SAZ es autónomo pero habitualmente se vincula a un ZNRX como documentación y justificación:

```
ZNRX-1234  (feature en desarrollo)
    └── SAZ-7177  (solicitud de deploy al equipo Release)
                   link: POST /rest/api/2/issueLink
```

El `znrx_key` será opcional en la Fase 5 — el link solo se crea si se provee.

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
| Service | Audit log con `request_id` | `AUDIT_LOG_PATH` |
| Service | Rate limit por usuario | `RATE_LIMIT_MAX_CALLS` / `_WINDOW` |
| Service | JQL controlado (máx. 50 resultados) | `JIRA_MAX_RESULTS` |
| Jira client | PAT Bearer + cert corporativo | `JIRA_PAT`, `REQUESTS_CA_BUNDLE` |
| Claude client | Proxy interno LiteLLM | `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` |

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
  service:   # FastAPI — puerto 8000
  mcp:       # MCP SSE — puerto 8001
             # depends_on: service
volumes:
  audit_log: # /app/audit.log persistido entre reinicios
```

```bash
docker compose up          # producción
uvicorn service.main:app   # service en dev (sin Docker)
python -m mcp.server       # MCP en dev (sin Docker)
```

---

## 8. Decisiones de arquitectura clave

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
