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

**Objetivo**: exponer la integración como MCP server desplegable en red interna con autenticación, control de acceso por rol y robustez ante abuso.

### Entregables
- `mcp/server.py` — SDK `mcp`, 4 herramientas, delega al service layer
- Auth MCP: API key interna + IP allowlist
- RBAC básico: `dev` (crear/consultar), `lead` (actualizar/priorizar), `system` (todo)
- Pre-validación ligera en cada herramienta MCP (antes de llamar al backend)
- Rate limiting por API key en el MCP server
- Output normalizado — Claude solo recibe `{key, status}`, nunca el payload completo
- `mcp/Dockerfile` — imagen deployable en red interna
- Configuración para `.claude/settings.json`

### Tareas
1. Instalar SDK MCP (`pip install mcp`)
2. Crear `mcp/server.py` con herramientas: `create_jira_issue`, `update_jira_issue`, `search_jira_issues`, `get_jira_issue`
3. Cada herramienta delega al service layer FastAPI (no duplicar lógica)
4. Middleware de autenticación: `X-API-Key` header + IP allowlist (`10.0.0.0/8`, `192.168.0.0/16`)
5. Middleware RBAC: mapeo `user → rol → acciones permitidas`
6. Pre-validación ligera por herramienta: longitud de input, tipos requeridos — rechazar antes de llamar al backend
7. Rate limiting por API key: `max_calls = 10/min` por defecto, configurable
8. Normalizar respuestas: devolver solo campos esenciales al LLM
9. `mcp/Dockerfile` — servicio independiente deployable
10. (Opcional) Policy Engine: `enforce_policy()` — si `priority == Critical` → `require_approval()`
11. Documentar configuración SSE interna en `mcp/README.md`

### Pre-validación ligera (defensa en profundidad)
```python
# Bloquear abuso antes de llegar al backend
if len(arguments["text"]) > 2000:
    raise ValueError("input demasiado largo — máximo 2000 caracteres")
if not arguments.get("text", "").strip():
    raise ValueError("input vacío")
```

### Rate limiting por API key
```python
@rate_limit(key=api_key, max_calls=10, window_seconds=60)
async def create_jira_issue(arguments): ...
```

### Output normalizado
```python
# Nunca reenviar el payload completo al LLM
return {"key": result["key"], "status": "created"}   # create
return {"key": key, "status": "updated"}              # update
return {"issues": [{"key": i["key"], "summary": i["summary"]} for i in results]}  # search
```

### Auth MCP
```python
X-API-Key: <clave-interna>   # header requerido en cada llamada
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
→ Claude invoca create_jira_issue (auth OK, pre-validación OK, rate limit OK)
→ MCP delega a service layer → PROJ-003 creado
→ Claude recibe: {"key": "PROJ-003", "status": "created"}
```

---

## Fase 5 — Observabilidad + Caching (opcional / futura)

**Objetivo**: llevar el sistema de ~85% a producción top-tier con métricas, trazas distribuidas y reducción de carga en Jira.

> Esta fase no es bloqueante para producción. Activar cuando el volumen de uso lo justifique.

### Entregables
- Métricas Prometheus expuestas en `/metrics` (service layer + MCP)
- Trazas distribuidas con OpenTelemetry — correlación entre MCP, service layer y Jira
- Caching de 30-60s en `search_jira_issues` — reduce carga repetitiva en Jira

### Tareas
1. Instrumentar FastAPI con `prometheus-fastapi-instrumentator`
2. Agregar `opentelemetry-sdk` con exportador configurable (Jaeger / Zipkin)
3. Propagar `trace_id` desde MCP → service layer → Jira (header `X-Trace-ID`)
4. Implementar cache en memoria (TTL 30-60s) para resultados de búsqueda
5. Dashboard Grafana básico: latencia, errores, tickets creados/día

### Por qué es opcional
- `request_id` UUID ya cubre trazabilidad básica para el volumen inicial
- El caching requiere decisiones sobre invalidación que dependen del uso real
- Prometheus/OTel requieren infraestructura adicional (Grafana, Jaeger) no disponible en todos los entornos Zurich

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
| Pre-validación MCP | Ligera, antes de llamar al backend | Bloquear abuso (input >2000 chars, vacíos) sin latencia de red |
| Rate limiting | En MCP (por API key) + FastAPI (por endpoint) | Defensa en profundidad — dos capas independientes |
| Output MCP | Normalizado (`{key, status}` solamente) | Evitar filtración de datos internos hacia el LLM |
| Session context | `request_id` UUID (sin estado de sesión completo) | Trazabilidad suficiente; sesiones completas añaden complejidad innecesaria en esta etapa |
| Observabilidad | Opcional — Fase 5 | Requiere infra adicional; `request_id` cubre el MVP |
| Caching | Opcional — Fase 5 | `search_jira_issues` 30-60s TTL cuando el volumen lo justifique |
