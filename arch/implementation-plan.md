# Plan de Implementación: claude-mcp-jira

Implementación incremental en 4 fases para red empresarial (Jira Server/Data Center en `jira.zurich.com`).
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

## Fase 3 — Comandos completos + JQL controlado

**Objetivo**: soporte para los 4 comandos CLI con clasificación de intención y queries JQL seguras.

### Entregables
- Dispatcher de intención en el service layer
- 4 comandos: `create`, `update`, `summarize`, `list`
- Endpoints adicionales en FastAPI

### Tareas
1. Implementar clasificador de intención: texto → `{intent, params}`
2. Agregar `PATCH /issues/{key}` — actualiza summary/description/status vía transiciones Jira v2
3. Agregar `GET /issues/{key}/summary` — Claude genera resumen legible
4. Agregar `GET /issues?query=<texto>` con JQL controlado (ver abajo)
5. Prompt templates separados por operación en `service/prompts/`
6. Validar output de Claude con Pydantic antes de llamar a Jira
7. Rate limiting en FastAPI + quotas por usuario

### JQL controlado (riesgo mitigado)
Claude **no genera JQL directamente**. En su lugar:
- Claude genera un objeto estructurado: `{"assignee": "me", "status": "open", "date_range": "last_week"}`
- El service layer construye el JQL seguro a partir de ese objeto
- `MAX_RESULTS = 50` fijo en todas las queries
- `ALLOWED_FIELDS` lista blanca de campos permitidos en filtros

```python
# Claude → struct → builder JQL controlado
struct = claude_parse_query("mis bugs abiertos de esta semana")
# → {"assignee": "currentUser()", "issuetype": "Bug", "status": "Open", "date_range": "last_week"}
jql = build_jql(struct, max_results=50)
# → "assignee = currentUser() AND issuetype = Bug AND status = Open AND created >= -7d ORDER BY created DESC"
```

### Criterio de éxito
```bash
python cli/main.py update PROJ-002 "cambiar prioridad a crítica"
python cli/main.py summarize PROJ-002
python cli/main.py list "mis bugs abiertos de esta semana"
```

---

## Fase 4 — MCP Server (servicio deployable interno) + Auth + RBAC

**Objetivo**: exponer la integración como MCP server desplegable en red interna con autenticación y control de acceso por rol.

### Entregables
- `mcp/server.py` — SDK `mcp`, 4 herramientas, delega al service layer
- Auth MCP: API key interna + IP allowlist
- RBAC básico: `dev` (crear/comentar), `lead` (actualizar/priorizar), `system` (todo)
- `mcp/Dockerfile` — imagen deployable en red interna
- Configuración para `.claude/settings.json`
- (Opcional) Policy Engine: aprobación humana para acciones críticas

### Tareas
1. Instalar SDK MCP (`pip install mcp`)
2. Crear `mcp/server.py` con herramientas: `create_jira_issue`, `update_jira_issue`, `search_jira_issues`, `get_jira_issue`
3. Cada herramienta delega al service layer FastAPI (no duplicar lógica)
4. Middleware de autenticación: `X-API-Key` header + lista de IPs permitidas
5. Middleware RBAC: mapeo `user → rol → acciones permitidas`
6. `mcp/Dockerfile` — servicio independiente deployable
7. (Opcional) Policy Engine: `enforce_policy()` — si `priority == Critical` o acción destructiva → `require_approval()`
8. Documentar configuración SSE interna en `mcp/README.md`

### Auth MCP
```python
# API key interna — nunca expuesta fuera de la red
X-API-Key: <clave-interna>

# IP allowlist — solo hosts de la red Zurich
ALLOWED_IPS = ["10.0.0.0/8", "192.168.0.0/16"]
```

### RBAC
```python
ROLES = {
    "dev":    ["create_issue", "get_issue", "search_issues"],
    "lead":   ["create_issue", "update_issue", "get_issue", "search_issues"],
    "system": ["create_issue", "update_issue", "get_issue", "search_issues"],
}
```

### Policy Engine (opcional)
```python
def enforce_policy(action):
    if action.type == "update" and action.priority == "Critical":
        require_approval()   # notifica al lead antes de ejecutar
```

### Configuración `.claude/settings.json`
```json
{
  "mcpServers": {
    "jira": {
      "type": "sse",
      "url": "http://mcp-jira.internal/sse",
      "headers": { "X-API-Key": "<clave-interna>" }
    }
  }
}
```

### Criterio de éxito
```
Claude Code: "crea un ticket para el bug que encontramos en auth"
→ Claude invoca create_jira_issue (MCP interno, auth OK) → PROJ-003 creado
```

---

## Estructura de directorios final

```
claude-mcp-jira/
├── cli/
│   └── main.py                  # Typer CLI — cliente HTTP del service layer
├── service/
│   ├── main.py                  # FastAPI app
│   ├── audit.py                 # JSON-lines con request_id
│   ├── routes/
│   ├── schemas/
│   ├── clients/
│   │   ├── sanitizer.py         # Sanitización extendida
│   │   ├── claude_client.py
│   │   └── jira_client.py       # PAT Bearer + cert + timeout
│   └── prompts/                 # Templates por operación
├── mcp/
│   ├── server.py                # MCP server con auth + RBAC
│   ├── Dockerfile
│   └── README.md
├── certs/                       # Certificados raíz corporativos Zurich
├── arch/
├── Dockerfile                   # Service layer
├── docker-compose.yml
├── environment.yml
├── .env.example
└── CLAUDE.md
```

---

## Dependencias Python

```
anthropic
mcp
fastapi
uvicorn[standard]
httpx
requests
typer
pydantic
python-dotenv
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
| Timeout Jira | `JIRA_TIMEOUT=10s` configurable | Evitar bloqueos por Jira lento o caído |
| Trazabilidad | `request_id` UUID por operación | Correlacionar logs entre CLI, service y Jira |
| Auth MCP | API key + IP allowlist | Expone capacidades críticas; no debe ser acceso abierto |
| RBAC MCP | dev / lead / system | Principio de menor privilegio por rol |
