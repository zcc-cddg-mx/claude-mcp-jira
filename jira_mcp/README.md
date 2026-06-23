# MCP Server — claude-mcp-jira

MCP server interno que expone las operaciones Jira como herramientas para Claude Code.
Corre como servicio Docker dentro de la red corporativa Zurich. Delega toda la lógica al service layer FastAPI.

## Herramientas disponibles

### Jira

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

### Git Intelligence (Fase 9)

| Herramienta | Rol mínimo | Descripción |
|---|---|---|
| `sync_git_worklogs` | dev | Lee repo Git local, detecta sesiones de trabajo vinculadas a tickets y registra worklogs. Acepta `repo_name` (alias), `repo_path` (ruta absoluta), o usa el repo default. `dry_run=true` por defecto. |
| `register_git_repo` | dev | Registra un repo local en el registry: alias → ruta + proyecto Jira + ticket default |
| `list_git_repos` | dev | Lista los repos registrados en el registry (alias, ruta, proyecto, ticket default) |

### Azure DevOps / code-agent-mcp (Fase 11)

| Herramienta | Rol mínimo | Descripción |
|---|---|---|
| `run_code_agent` | lead | Encola tarea git en code-agent-mcp: crear rama feature, commit de archivos, push y rama auxiliar. Retorna `task_id` inmediatamente (202). |
| `get_code_agent_status` | dev | Consulta estado de la tarea (queued/running/done/error). En `done` incluye `branch`, `aux_branch`, `commit_id`. |
| `create_azure_pull_request` | lead | Idempotente: asegura que la rama auxiliar existe/está al día y crea (o devuelve el existente) el PR en Azure DevOps. Retorna `action` (created/updated/unchanged), `pr_id`, `pr_url`. |
| `get_pull_request_status` | dev | Estado del PR (`active/completed/abandoned`) + build CI (`pending/succeeded/failed/unknown`). |

**Flujo orquestado desde Claude Code:**
```
1. create_jira_issue       → ZNRX-XXXXX
2. run_code_agent          → task_id  (202 inmediato)
3. get_code_agent_status   → polling → done → {branch, aux_branch, commit_id}
4. create_azure_pull_request → {action, pr_id, pr_url}  (idempotente)
5. get_pull_request_status → esperar build verde
6. update_jira_issue       → link PR + transición "In Review"
```

**Requisito**: `code-agent-mcp` corriendo en `CODE_AGENT_URL` (default `http://code-agent-mcp:5001`). Ver `arch/code-agent/integration-plan.md`.

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
| `CODE_AGENT_URL` | `http://code-agent-mcp:5001` | URL del code-agent-mcp (Fase 11) |
| `CODE_AGENT_TOKEN` | `` | Token de auth para code-agent-mcp (`X-Agent-Token`); mismo valor que `TOKEN_AZURE` en ese servicio |
| `CODE_AGENT_TIMEOUT` | `30` | Timeout para llamadas al code-agent-mcp (segundos) |

## RBAC — permisos por rol

| Rol | Herramientas permitidas |
|---|---|
| `dev` | `create`, `get`, `search`, `add_comment`, `link`, `sync_git_worklogs`, `register_git_repo`, `list_git_repos`, `get_code_agent_status`, `get_pull_request_status` |
| `lead` | `create`, `update`, `get`, `search`, `add_comment`, `link`, `assign`, `set_priority`, `create_saz_request`, `sync_git_worklogs`, `register_git_repo`, `list_git_repos`, `run_code_agent`, `get_code_agent_status`, `create_azure_pull_request`, `get_pull_request_status` |
| `system` | todas |

Ejemplo de configuración con múltiples claves:

```
MCP_KEY_ROLES=key-dev-1:dev,key-lead-1:lead,key-system:system
```

## Limitaciones conocidas

### `sync_git_worklogs` requiere acceso al filesystem del host

La herramienta `sync_git_worklogs` ejecuta `git log` en rutas locales del host. En Docker, el contenedor del service layer no tiene acceso a esos paths a menos que se monten explícitamente como volúmenes en `docker-compose.yml`.

**Funcionamiento garantizado**: modo dev (`bash scripts/dev.sh both`), donde el service layer corre directamente en el host.

**En Docker**: para usar `git sync`, montar los repos necesarios en `docker-compose.yml`:

```yaml
services:
  service:
    volumes:
      - /home/usuario/dev/mi-repo:/home/usuario/dev/mi-repo:ro
```

O bien limitar `sync_git_worklogs` a entornos de desarrollo y no exponer en Docker de producción.
