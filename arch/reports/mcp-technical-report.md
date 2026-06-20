# Informe Técnico: Model Context Protocol (MCP)

**Proyecto**: claude-mcp-jira  
**Propósito**: referencia técnica para evaluaciones, auditorías y decisiones de arquitectura futuras  
**Fecha**: Junio 2026 — actualizado post-Fase 4

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
| **Tools** | Funciones que el LLM puede invocar | `create_jira_issue`, `search_jira_issues` |
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
      "args": ["mcp/server.py"]
    }
  }
}
```

### 3.2 SSE (Server-Sent Events)
- El MCP server corre como servicio HTTP independiente
- Claude se conecta vía HTTP/SSE a una URL
- Ideal para: entornos corporativos, servidores compartidos, Docker
- **Recomendado para este proyecto** — el servidor vive en la red interna Zurich

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

---

## 4. Flujo de una invocación MCP

```
1. Usuario escribe en Claude Code:
   "Crea un ticket para el bug de autenticación"

2. Claude (LLM) decide invocar la herramienta:
   create_jira_issue(text="bug de autenticación")

3. Claude Code (host MCP) envía la llamada al MCP server vía SSE

4. MCP server:
   - Verifica API key, IP, RBAC y rate limit
   - Pre-valida el input (vacío / tamaño > MCP_MAX_PAYLOAD_SIZE)
   - Delega al service layer FastAPI:
     POST http://service:8000/issues  {"text": "bug de autenticación", "user": "..."}

5. Service layer: sanitiza → Claude API (LiteLLM proxy) → Jira REST API v2

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
                    "text": {"type": "string", "description": "Descripción del ticket"}
                },
                "required": ["text"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "create_jira_issue":
        # Delegar al service layer — nunca duplicar lógica aquí
        result = await service_client.create_issue(arguments["text"])
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
    │  Claude Code ──SSE──►  [MCP Server Docker :8001]
    │                                │
    │                         [Service Layer FastAPI :8000]
    │                                │
    │                         [jira.zurich.com]  (ZNRX, SAZ)
    │                         [LiteLLM proxy → Claude API]
```

### 6.3 Controles de seguridad implementados (Fase 4)

| Control | Implementación | Variable |
|---|---|---|
| Autenticación MCP | `X-API-Key` header — clave interna rotable | `MCP_API_KEY` |
| Red | IP allowlist por CIDR | `MCP_ALLOWED_CIDRS` |
| RBAC | Roles `dev` / `lead` / `system` con permisos acotados | `MCP_KEY_ROLES` |
| Pre-validación | Rechaza input vacío o mayor al límite | `MCP_MAX_PAYLOAD_SIZE` |
| Rate limiting MCP | Sliding window por API key | `MCP_RATE_LIMIT_MAX_CALLS` |
| Rate limiting service | Sliding window por usuario | `RATE_LIMIT_MAX_CALLS` |
| Sanitización | Tokens, IPs RFC1918, hostnames internos, stack traces | — |
| Audit log | Trazabilidad completa con `request_id` UUID | `AUDIT_LOG_PATH` |
| Output normalizado | LLM solo recibe `{key, status}` o `{key, summary}` | — |
| Timeout | Todos los clientes externos con timeout configurable | `JIRA_TIMEOUT`, `MCP_SERVICE_TIMEOUT` |

---

## 7. Diferencia entre MCP server y el service layer FastAPI

Un error común es confundir ambos componentes. En este proyecto tienen roles distintos:

| Aspecto | MCP Server (`mcp/`) | Service Layer (`service/`) |
|---|---|---|
| Propósito | Interfaz entre Claude y el sistema | Lógica de negocio + seguridad |
| Invocado por | Claude Code (LLM) | MCP server + CLI |
| Contiene lógica | No — solo delega | Sí — sanitización, audit, validación |
| Protocolo | MCP (SSE) | HTTP/REST (FastAPI) |
| Autenticación | API key MCP + IP + RBAC | PAT Jira, API key Anthropic |

**Regla**: el MCP server no duplica lógica. Todo pasa por el service layer.

---

## 8. Proyectos Jira integrados

| Proyecto | Key | Descripción | Estado |
|---|---|---|---|
| Desarrollo / bugs | `ZNRX` | Tickets de desarrollo del equipo | ✅ Activo (`JIRA_PROJECT_KEY=ZNRX`) |
| Solicitudes Release | `SAZ` | Solicitudes DevOps: reinicios, deploys, repos, accesos | Fase 5 — futura |

### Relación ZNRX ↔ SAZ

Un ticket SAZ es autónomo pero habitualmente se vincula a un ZNRX como documentación y justificación de la solicitud:

```
ZNRX-1234  (feature / bug en desarrollo)
    └── SAZ-7177  (link: "relates to" — solicitud de deploy al equipo de Release)
```

El link se crea vía `POST /rest/api/2/issueLink`. El tipo de link exacto está pendiente de confirmar contra `jira.zurich.com/rest/api/2/issueLinkType`.

---

## 9. Comparativa de opciones para integración LLM-Jira

| Opción | Viabilidad Zurich | Seguridad | Esfuerzo | Recomendación |
|---|---|---|---|---|
| MCP oficial Atlassian (`atlassian.com`) | ❌ Solo Jira Cloud | ❌ Datos salen de la red | Bajo | Descartar |
| N8N / Zapier | ❌ Servicios cloud | ❌ Datos en terceros | Bajo | Descartar |
| CLI directo (Fase 1) | ✅ | ⚠️ Sin sanitización | Bajo | Solo prototipo |
| Service Layer + CLI (Fase 2-3) | ✅ | ✅ | Medio | Producción básica |
| MCP Server interno (Fase 4) | ✅ | ✅ Auth+RBAC+rate limit | Medio-Alto | **Producción — estado actual** |

---

## 10. Estado de implementación y roadmap

```
✅ Fase 1 — Prototipo CLI
   └── CLI Typer con comando create directo a Jira

✅ Fase 2 — Service Layer
   └── FastAPI + sanitización + audit log + timeouts

✅ Fase 3 — Comandos completos
   └── create, update, summarize, list + JQL controlado + rate limiter

✅ Fase 4 — MCP Server
   └── SSE Docker + API key + IP allowlist + RBAC + rate limit + output normalizado

🔜 Fase 5 — Soporte SAZ (futura)
   └── Tickets Solicitudes Release Zurich
   └── znrx_key opcional → link automático SAZ → ZNRX
   └── Bloqueante: inspeccionar issueLinkType y createmeta SAZ

⬜ Fase 6 — Observabilidad (opcional)
   └── Prometheus + OpenTelemetry + caching
```

---

## 11. Referencias

- [MCP Specification](https://spec.modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Anthropic MCP Docs](https://docs.anthropic.com/en/docs/agents-and-tools/mcp)
- Jira REST API v2: `https://jira.zurich.com/rest/api/2/`
- Jira issue links: `GET /rest/api/2/issueLinkType`
- Jira create meta: `GET /rest/api/2/issue/createmeta?projectKeys=SAZ`
