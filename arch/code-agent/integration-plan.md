# Code Agent — Plan de integración con claude-mcp-jira

## Contexto

El code-agent (`ov-suscripcion-automation`) genera archivos de migración Flyway, crea ramas y hace push a Azure DevOps. Actualmente n8n es el orquestador: recibe el callback del code-agent, crea el PR y actualiza Jira.

**Objetivo:** reemplazar n8n como orquestador por `claude-mcp-jira` vía MCP tools, manteniendo el code-agent como backend especializado de generación + git.

---

## Pipeline actual (con n8n)

```
Jira (webhook)
  → n8n
    → Code Agent → branch + push
    → n8n crea PR (Azure CLI)
    → Azure DevOps pipeline → deploy DEV
    → QA Agent → valida
    → n8n actualiza Jira
```

## Pipeline objetivo (con claude-mcp-jira)

```
Claude Code (MCP tools)
  → claude-mcp-jira
    → Jira          (ya existe — tools: create, update, transition, comment)
    → Code Agent    (nuevo — tools: run_migration, get_migration_status)
    → Azure DevOps  (nuevo — tools: create_azure_pull_request, get_pull_request_status)
    → Jira          (actualizar con PR link + transición)
```

Flujo completo desde Claude Code sin tocar n8n:

```
1. create_jira_issue           → ZNRX-XXXXX
2. run_migration               → task_id  (202 inmediato)
3. get_migration_status        → polling → "done" → {branch, aux_branch, commit_id}
4. create_azure_pull_request   → {pr_id, pr_url}  (feature branch + aux branch)
5. get_pull_request_status     → esperar build verde
6. update_jira_issue           → link PR + transición "In Review"
```

---

## Capacidades del code-agent

### Ya implementadas

| Capacidad | Endpoint / módulo |
|---|---|
| Generar migración `ren-data` (xlsx + java, ams-policy) | `POST /run` + `src/generator_ren_data.py` |
| Generar migración `rules` (xlsx + java, ams-rule) | `POST /run` + `src/generator_rules.py` |
| Crear feature branch desde `origin/developer` + commit + push | `src/placer.py` — `create_feature_branch` + `git_add_commit_push` |
| Crear rama `_developer_auxiliar` (limpia, sin merge) | `src/placer.py` — `create_auxiliary_branch` |
| Verificación de compilación Java (javac) antes del push | `src/build_check.py` |
| Validar par exacto (1 xlsx + 1 java, nombres coincidentes) | `src/placer.py` — `_validate_migration_pair` |
| HTTP API asíncrona (202 inmediato + polling) | `app.py` — `POST /run`, `GET /status/<task_id>` |
| Persistencia SQLite de tareas y resultados | `src/task_store.py` |
| Callback POST con retry 3x backoff | `app.py` — `_notify_n8n` |
| Listado de tareas recientes | `GET /tasks` |

### Necesita añadir (para integración con claude-mcp-jira)

#### 1. `POST /azure/pull-requests` — crear PR ← prioritario

Elimina la dependencia de n8n para este paso. El code-agent llama directo a Azure DevOps REST API.

```
Input:
  branch       string  — rama feature (e.g. feature/ZNRX_67108_renov_agosto)
  aux_branch   string  — rama auxiliar (_developer_auxiliar)
  title        string  — título del PR
  description  string  — descripción (opcional)
  repo         string  — nombre del repo en Azure DevOps
  target       string  — rama destino (default: "developer")

Output:
  {
    "feature_pr":  {"pr_id": 123, "pr_url": "https://dev.azure.com/..."},
    "aux_pr":      {"pr_id": 124, "pr_url": "https://dev.azure.com/..."}
  }
```

Credencial: `AZURE_PAT` en `.env` del code-agent.
API: `https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullrequests?api-version=7.1`

#### 2. `GET /azure/pull-requests/<pr_id>` — estado del PR + pipeline

Permite que claude-mcp-jira sepa si el build pasó antes de actualizar Jira.

```
Output:
  {
    "pr_id": 123,
    "status": "active" | "completed" | "abandoned",
    "build_status": "pending" | "succeeded" | "failed" | "unknown",
    "pr_url": "https://dev.azure.com/..."
  }
```

#### 3. `GET /tasks?ticket=ZNRX-123` — consulta por ticket

Para que claude-mcp-jira detecte si ya hay una tarea en curso o completada para ese ticket. Evita lanzar el mismo trabajo dos veces (idempotencia).

```
Output: lista de tareas filtradas por ticket (mismo formato que GET /tasks)
```

#### 4. `X-Agent-Token` — autenticación del API

Header requerido en todos los endpoints. Variable `AGENT_TOKEN` en `.env`.
Solo claude-mcp-jira (y n8n mientras coexistan) pueden invocar el agente.

#### 5. `callback_url` en payload de `POST /run` — notificación al caller

Actualmente el callback está hardcodeado a `N8N_CALLBACK_URL`.
Aceptar `callback_url` en el body permite que claude-mcp-jira reciba notificación al terminar en vez de hacer polling activo.

---

## MCP tools a añadir en claude-mcp-jira (Fase 11)

| Tool | Rol mínimo | Qué hace |
|---|---|---|
| `run_migration` | lead | Llama `POST /run` del code-agent; texto libre → Claude extrae ticket/comando/parámetros |
| `get_migration_status` | dev | Llama `GET /status/<task_id>`; retorna estado + branch + commit_id |
| `create_azure_pull_request` | lead | Llama `POST /azure/pull-requests`; crea PR para feature y aux branch |
| `get_pull_request_status` | dev | Llama `GET /azure/pull-requests/<pr_id>`; retorna estado del PR + build |

Variables de entorno nuevas en `claude-mcp-jira`:
- `CODE_AGENT_URL` — URL del code-agent (e.g. `http://code-agent:5000`)
- `CODE_AGENT_TOKEN` — valor del `X-Agent-Token`

---

## Orden de implementación recomendado

| Paso | Dónde | Qué |
|---|---|---|
| 1 | code-agent | `POST /azure/pull-requests` + `AZURE_PAT` |
| 2 | code-agent | `X-Agent-Token` en todos los endpoints |
| 3 | code-agent | `GET /tasks?ticket=` |
| 4 | code-agent | `GET /azure/pull-requests/<pr_id>` |
| 5 | claude-mcp-jira | service_client + MCP tools (Fase 11) |
| 6 | claude-mcp-jira | e2e test del flujo completo |

---

## Coexistencia con n8n

Durante la transición, n8n y claude-mcp-jira pueden coexistir sin conflicto:
- n8n sigue usando el callback `N8N_CALLBACK_URL` para los flujos automáticos (Jira webhook)
- claude-mcp-jira usa los MCP tools para flujos manuales o supervisados desde Claude Code
- El code-agent responde a ambos — no hay estado compartido que cause conflicto

La migración completa (retirar n8n) es una decisión de equipo, no un prerequisito técnico.
