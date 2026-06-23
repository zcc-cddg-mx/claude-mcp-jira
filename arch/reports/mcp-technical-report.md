# Informe Técnico: Model Context Protocol (MCP)

**Proyecto**: claude-mcp-jira  
**Propósito**: referencia técnica para evaluaciones, auditorías y decisiones de arquitectura futuras  
**Fecha**: Junio 2026 — actualizado post-Fase 9.4 (Git Intelligence completa)

---

## 1. ¿Qué es MCP?

El **Model Context Protocol (MCP)** es un protocolo abierto desarrollado por Anthropic que estandariza la forma en que los modelos de lenguaje (LLMs) se conectan con herramientas, datos y servicios externos.

Es el equivalente a una "API universal" entre un LLM y el mundo exterior: en lugar de que cada integración requiera un conector ad-hoc, MCP define un contrato común que cualquier herramienta puede implementar.

```
[Claude / LLM]  ←──MCP──►  [MCP Server]  ←──►  [Servicio externo]
                                                   (Jira, GitHub, DB, etc.)
```

### Analogía
MCP es para los LLMs lo que USB fue para los periféricos: un estándar que evita el caos de conectores propietarios.

---

## 2. Componentes principales

### 2.1 MCP Host
La aplicación que aloja al LLM y actúa como cliente MCP.

Ejemplos:
- Claude Code (CLI)
- Claude Desktop
- Aplicaciones propias que usan la API de Anthropic

### 2.2 MCP Server
Proceso que expone capacidades (herramientas, recursos, prompts) al host vía el protocolo MCP.

Puede estar implementado en cualquier lenguaje. En este proyecto: **Python con el SDK oficial `mcp`**.

### 2.3 Primitivas del protocolo

| Primitiva | Descripción | Ejemplo en este proyecto |
|---|---|---|
| **Tools** | Funciones que el LLM puede invocar | `create_jira_issue`, `search_jira_issues`, `create_saz_request` |
| **Resources** | Datos que el LLM puede leer | Contenido de un ticket Jira |
| **Prompts** | Templates de prompt reutilizables | Prompt de resumen de ticket |

---

## 3. Transportes disponibles

MCP soporta dos mecanismos de transporte:

### 3.1 stdio (Standard I/O)
- El MCP server corre como proceso hijo del host
- Comunicación por stdin/stdout
- Ideal para: scripts locales, herramientas de desarrollo, uso personal
- **No recomendado para entornos corporativos** — el servidor vive en la máquina del usuario

```json
{
  "mcpServers": {
    "jira": {
      "command": "python",
      "args": ["jira_mcp/server.py"]
    }
  }
}
```

### 3.2 SSE (Server-Sent Events)
- El MCP server corre como servicio HTTP independiente
- Claude se conecta vía HTTP/SSE a una URL
- Ideal para: entornos corporativos, servidores compartidos, Docker
- **Implementado en este proyecto** — el servidor vive en la red interna Zurich

```json
{
  "mcpServers": {
    "jira": {
      "type": "sse",
      "url": "http://localhost:18001/sse",
      "headers": { "X-API-Key": "<clave-interna>" }
    }
  }
}
```

---

## 4. Flujo de una invocación MCP

```
1. Usuario escribe en Claude Code:
   "Crea un ticket para el bug de autenticación"

2. Claude (LLM) decide invocar la herramienta:
   create_jira_issue(text="bug de autenticación", project="ZNRX")

3. Claude Code (host MCP) envía la llamada al MCP server vía SSE

4. MCP server:
   - Verifica API key, IP, RBAC y rate limit
   - Pre-valida el input (vacío / tamaño > MCP_MAX_PAYLOAD_SIZE)
   - Delega al service layer FastAPI:
     POST http://service:18000/issues  {"text": "bug de autenticación", "project": "ZNRX", "user": "..."}

5. Service layer: resolve_project → sanitiza → Claude API (LiteLLM proxy) → Jira REST API v2

6. MCP server devuelve resultado normalizado a Claude Code:
   {"key": "ZNRX-1234", "status": "created"}
   (nunca el payload completo de Jira)

7. Claude responde al usuario:
   "Ticket ZNRX-1234 creado con prioridad Alta."
```

---

## 5. SDK Python

```bash
pip install mcp
```

### Estructura mínima de un MCP server

```python
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

server = Server("jira-mcp")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="create_jira_issue",
            description="Crea un ticket Jira a partir de texto libre",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Descripción del ticket"},
                    "project": {"type": "string", "description": "Proyecto Jira (opcional)"}
                },
                "required": ["text"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "create_jira_issue":
        # Delegar al service layer — nunca duplicar lógica aquí
        result = await service_client.create_issue(arguments["text"], arguments.get("project"))
        return [TextContent(type="text", text=f"Ticket creado: {result['key']}")]
```

---

## 6. Seguridad en entornos corporativos

### 6.1 Por qué NO usar el MCP oficial de Atlassian

```bash
# Este comando NO es válido para jira.zurich.com
claude mcp add --transport sse atlassian https://atlassian.com
```

Problemas:
- Apunta a infraestructura pública de Atlassian Cloud
- No puede alcanzar `jira.zurich.com` detrás del firewall
- Los datos (tickets, comentarios, metadata) saldrían de la red corporativa
- Incumple ISO 27001 y políticas de seguridad de Zurich

### 6.2 Arquitectura segura para Zurich

```
[Dev machine]                [Red interna Zurich]
    │                                │
    │  Claude Code ──SSE──►  [MCP Server Docker :18001]
    │                                │
    │                         [Service Layer FastAPI :18000]
    │                                │
    │                         [jira.zurich.com]  (ZNRX, SAZ, AIPROJECTS, SCRX, ...)
    │                         [LiteLLM proxy → Claude API]
```

### 6.3 Controles de seguridad implementados

| Control | Implementación | Variable |
|---|---|---|
| Autenticación MCP | `X-API-Key` header — clave interna rotable | `MCP_API_KEY` |
| Red | IP allowlist por CIDR | `MCP_ALLOWED_CIDRS` |
| RBAC | Roles `dev` / `lead` / `system` con permisos acotados | `MCP_KEY_ROLES` |
| Pre-validación | Rechaza input vacío o mayor al límite | `MCP_MAX_PAYLOAD_SIZE` |
| Rate limiting MCP | Sliding window por API key | `MCP_RATE_LIMIT_MAX_CALLS` |
| Rate limiting service | Sliding window por usuario | `RATE_LIMIT_MAX_CALLS` |
| Sanitización | Tokens, IPs RFC1918, hostnames internos, stack traces | — |
| Audit log | Trazabilidad completa con `request_id` UUID + rotación 10 MB × 5 | `AUDIT_LOG_PATH` |
| Output normalizado | LLM solo recibe `{key, status}` o `{key, summary}` | — |
| Timeout | Todos los clientes externos con timeout configurable | `JIRA_TIMEOUT`, `MCP_SERVICE_TIMEOUT` |
| SSE timeout | `asyncio.wait_for` en `handle_sse` | `MCP_SSE_TIMEOUT` |

---

## 7. Diferencia entre MCP server y el service layer FastAPI

| Aspecto | MCP Server (`jira_mcp/`) | Service Layer (`service/`) |
|---|---|---|
| Propósito | Interfaz entre Claude y el sistema | Lógica de negocio + seguridad |
| Invocado por | Claude Code (LLM) | MCP server + CLI |
| Contiene lógica | No — solo delega | Sí — sanitización, audit, validación, project registry |
| Protocolo | MCP (SSE) | HTTP/REST (FastAPI) |
| Autenticación | API key MCP + IP + RBAC | PAT Jira, API key Anthropic |

**Regla**: el MCP server no duplica lógica. Todo pasa por el service layer.

---

## 8. Herramientas MCP implementadas

| Tool | Rol mínimo | Endpoint service layer | Descripción |
|---|---|---|---|
| `create_jira_issue` | dev | `POST /issues` | Crea ticket desde texto; `project` opcional |
| `update_jira_issue` | lead | `PATCH /issues/{key}` | Actualiza ticket desde texto |
| `get_jira_issue` | dev | `GET /issues/{key}/summary` | Resumen Claude del ticket |
| `search_jira_issues` | dev | `POST /issues/search` | Búsqueda NL; `project` opcional |
| `add_comment_jira_issue` | dev | `POST /issues/{key}/comments` | Añade comentario |
| `link_jira_issues` | dev | `POST /issues/{key}/link` | Relaciona dos tickets |
| `assign_jira_issue` | lead | `POST /issues/{key}/assign` | Asigna un responsable |
| `set_priority_jira_issue` | lead | `POST /issues/{key}/priority` | Cambia la prioridad |
| `create_saz_request` | lead | `POST /issues/saz` | Crea ticket SAZ; `znrx_key` opcional |
| `sync_git_worklogs` | dev | `POST /git/sync` | Lee repo Git local, detecta sesiones y registra worklogs. `dry_run=true` por defecto. Acepta `repo_name` o `repo_path`. |
| `register_git_repo` | dev | `POST /git/repos` | Registra alias de repo con proyecto y ticket Jira por defecto |
| `list_git_repos` | dev | `GET /git/repos` | Lista repos registrados en el registry |

---

## 9. Proyectos Jira integrados

| Proyecto | Key | Descripción | Config |
|---|---|---|---|
| Gestión requerimientos | `ZNRX` | Features, bugs y tareas del equipo | seed — constraints curados |
| IA y automatización | `AIPROJECTS` | Proyectos IA internacionales | seed — TICKET_LANG=en |
| Desarrollo LATAM | `SCRX` | Desarrollo ágil Ecuador/LATAM | seed |
| Solicitudes Release | `SAZ` | DevOps: reinicios, deploys, repos, accesos | jira_auto |
| Cualquier otro | `*` | Auto-descubierto en primer acceso | jira_auto |

### Auto-discovery de proyectos

El sistema no requiere configuración manual para nuevos proyectos. Al primer acceso a un proyecto desconocido:

```
GET /projects/NEWTEAM
→ DB miss → GET /rest/api/2/project/NEWTEAM → 200 OK
→ createmeta (intento; ignorado si 403/404)
→ INSERT INTO projects (source: "jira_auto")
→ {"project_key": "NEWTEAM", "discovery_source": "jira_auto", ...}
```

### Relación ZNRX ↔ SAZ

```
ZNRX-1234  (feature / bug en desarrollo)
    └── SAZ-7403  (link: "Relates" — solicitud de deploy al equipo de Release)
```

El link se crea automáticamente si se provee `znrx_key` en `POST /issues/saz`.

---

## 10. Comparativa de opciones para integración LLM-Jira

| Opción | Viabilidad Zurich | Seguridad | Esfuerzo | Recomendación |
|---|---|---|---|---|
| MCP oficial Atlassian (`atlassian.com`) | ❌ Solo Jira Cloud | ❌ Datos salen de la red | Bajo | Descartar |
| N8N / Zapier | ❌ Servicios cloud | ❌ Datos en terceros | Bajo | Descartar |
| CLI directo (Fase 1) | ✅ | ⚠️ Sin sanitización | Bajo | Solo prototipo |
| Service Layer + CLI (Fases 2-3) | ✅ | ✅ | Medio | Producción básica |
| MCP Server interno (Fases 4+) | ✅ | ✅ Auth+RBAC+rate limit | Medio-Alto | **Producción — estado actual** |

---

## 11. Estado de implementación

```
✅ Fase 1 — Prototipo CLI
   └── CLI Typer con comando create directo a Jira

✅ Fase 2 — Service Layer
   └── FastAPI + sanitización + audit log + timeouts

✅ Fase 3 — Comandos completos
   └── create, update, summarize, list + JQL controlado + rate limiter

✅ Fase 4 — MCP Server
   └── SSE Docker + API key + IP allowlist + RBAC + rate limit + output normalizado

✅ Fase 4.1 — Ajustes e2e + TICKET_LANG
✅ Fase 4.2 — Deuda técnica (52 unit tests, JQL injection fix, rate limiter compartido)
✅ Fase 4.3 — Transiciones y Log Work
✅ Fase 4.4 — Mejoras API (comments, assign, priority, labels, clone)
✅ Fase 4.5 — Link dinámico (tipos reales de Jira, cache TTL 1h)

✅ Fase 5 — Soporte SAZ
   └── POST /issues/saz + MCP tool create_saz_request (lead)
   └── znrx_key opcional → link Relates automático

⬜ Fase 6 — Observabilidad (futura)
   └── Prometheus + OpenTelemetry + caching

✅ Fase 7 — Multi-proyecto
   └── project opcional en create/search; config dinámica por proyecto

✅ Fase 7b — SQLite auto-discovery
   └── Cualquier proyecto Jira válido se registra en el primer acceso
   └── GET /projects + GET /projects/{key}

⬜ Fase 8a — PAT dinámico (futura)
   └── X-Jira-Token header opcional — autoría correcta por usuario

⬜ Fase 8 — UI (futura)
   └── Interfaz web para usuarios no técnicos

✅ Fase 9.1–9.4 — Git Intelligence
   └── Scanner subprocess (metadata only, nunca código)
   └── Analyzer: sesiones por gap temporal + estimación LOC nudge
   └── Mapper: regex en mensaje/rama + Claude NLP fallback
   └── POST /git/sync (dry_run=true por defecto)
   └── Repo registry SQLite git_repos: alias → path/origin/default_issue_key
   └── MCP tools: sync_git_worklogs, register_git_repo, list_git_repos

⬜ Fase 9.5 — Human-sensity worklogs (futura)
   └── Señales contextuales + preview editable human-in-the-loop
```

---

## 12. Referencias

- [MCP Specification](https://spec.modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Anthropic MCP Docs](https://docs.anthropic.com/en/docs/agents-and-tools/mcp)
- Jira REST API v2: `https://jira.zurich.com/rest/api/2/`
- Jira issue links: `GET /rest/api/2/issueLinkType`
- Jira project meta: `GET /rest/api/2/project/{key}`
