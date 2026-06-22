# MCP Server — claude-mcp-jira

MCP server interno que expone las operaciones Jira como herramientas para Claude Code.
Corre como servicio Docker dentro de la red corporativa Zurich. Delega toda la lógica al service layer FastAPI.

## Herramientas disponibles

| Herramienta | Rol mínimo | Descripción |
|---|---|---|
| `create_jira_issue` | dev | Crea un ticket desde texto libre; `project` opcional |
| `update_jira_issue` | lead | Actualiza un ticket desde texto libre |
| `get_jira_issue` | dev | Obtiene resumen de un ticket |
| `search_jira_issues` | dev | Búsqueda en lenguaje natural (máx. 50); `project` opcional |
| `add_comment_jira_issue` | dev | Añade comentario a un ticket |
| `link_jira_issues` | dev | Relaciona dos tickets (depends on, blocks, relates, etc.) |
| `assign_jira_issue` | lead | Asigna un ticket a un usuario |
| `set_priority_jira_issue` | lead | Cambia la prioridad de un ticket |
| `create_saz_request` | lead | Crea ticket SAZ (DevOps/Release); `znrx_key` opcional |

## Seguridad

- **API key**: header `X-API-Key` requerido (`MCP_API_KEY` en `.env`)
- **IP allowlist**: `MCP_ALLOWED_CIDRS` — solo hosts de la red Zurich
- **RBAC**: roles `dev` / `lead` / `system` mapeados por API key (`MCP_KEY_ROLES`)
- **Pre-validación**: input vacío o superior a `MCP_MAX_PAYLOAD_SIZE` caracteres rechazado antes de llamar al backend
- **Rate limiting**: `MCP_RATE_LIMIT_MAX_CALLS` por API key (independiente del service layer)
- **Output normalizado**: Claude solo recibe `{key, status}` o `{key, summary}` — nunca payloads internos completos

## Levantar con Docker Compose

```bash
docker compose up
```

El MCP server queda disponible en `http://localhost:18001/sse` (dev) o `http://localhost:8001/sse` (Docker interno).

## Configurar en Claude Code

Agregar a `.claude/settings.json` o `~/.claude.json`:

```json
{
  "mcpServers": {
    "jira": {
      "type": "sse",
      "url": "http://localhost:8001/sse",
      "headers": {
        "X-API-Key": "<MCP_API_KEY>"
      }
    }
  }
}
```

Para despliegue interno, reemplazar `localhost:8001` por el hostname del servidor:

```json
{
  "mcpServers": {
    "jira": {
      "type": "sse",
      "url": "http://mcp-jira.internal:8001/sse",
      "headers": {
        "X-API-Key": "<MCP_API_KEY>"
      }
    }
  }
}
```

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `SERVICE_URL` | `http://service:8000` | URL del service layer |
| `MCP_API_KEY` | `` | API key requerida (vacío = sin auth, solo dev) |
| `MCP_ALLOWED_CIDRS` | `10.0.0.0/8,192.168.0.0/16` | CIDRs permitidos |
| `MCP_KEY_ROLES` | `` | Mapeo `key:role` separado por comas |
| `MCP_DEFAULT_ROLE` | `dev` | Rol cuando no hay mapeo |
| `MCP_MAX_PAYLOAD_SIZE` | `2000` | Tamaño máximo de input en caracteres |
| `MCP_RATE_LIMIT_MAX_CALLS` | `10` | Llamadas máximas por ventana |
| `MCP_RATE_LIMIT_WINDOW` | `60` | Ventana en segundos |
| `MCP_PORT` | `8001` | Puerto de escucha |
| `MCP_SERVICE_TIMEOUT` | `30` | Timeout hacia el service layer (segundos) |
| `JIRA_MAX_RESULTS` | `50` | Máximo de resultados en búsquedas (hard cap: 50) |
| `TICKET_LANG` | `es` | Idioma del contenido generado: `es` \| `en` (ver `docs/jira-projects.md`) |

## RBAC — permisos por rol

| Rol | Herramientas permitidas |
|---|---|
| `dev` | `create`, `get`, `search`, `add_comment`, `link` |
| `lead` | `create`, `update`, `get`, `search`, `add_comment`, `link`, `assign`, `set_priority`, `create_saz_request` |
| `system` | todas |

Ejemplo de configuración con múltiples claves:

```
MCP_KEY_ROLES=key-dev-1:dev,key-lead-1:lead,key-system:system
```
