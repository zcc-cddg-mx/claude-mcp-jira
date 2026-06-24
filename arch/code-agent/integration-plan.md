# Code Agent MCP — Plan de integración con claude-mcp-jira

## Contexto

`code-agent-mcp` es un agente HTTP genérico que ejecuta operaciones git y crea PRs en Azure DevOps.
Vive en `/home/idavid/dev/claude/code-agent-mcp`.

Se creó desde cero (no modificando `ov-suscripcion-automation`) tomando solo la infraestructura
genérica del code-agent original y descartando toda lógica específica del dominio Flyway/OV.

---

## Estado actual del `code-agent-mcp` (2026-06-24)

**133 tests.** Funcional e2e contra Azure DevOps (Zurich Insurance Ecuador) — PRs #2552–#2554 reales creados.

### Módulos implementados

| Módulo | Responsabilidad |
|---|---|
| `app.py` | Flask HTTP API, todos los endpoints, Swagger UI (`/apidocs/`) |
| `src/auth.py` | `X-Agent-Token` header → 401 si falta/incorrecto; `/health` es el único endpoint libre |
| `src/task_store.py` | SQLite: tabla `tasks` (patrón async 202 + polling); columna `steps` con tracking por paso |
| `src/repo_store.py` | SQLite: tabla `repos` con columna `branch_roles` (JSON); allowlist de seguridad |
| `src/project_store.py` | SQLite: tabla `projects` (slug `{org}/{name}`); auto-upsert al registrar repo |
| `src/pr_store.py` | SQLite: tabla `prs` — registro persistente de pull requests (pr_id, repo, branches, status, task_id) |
| `src/repo_inspector.py` | Parsea URLs Azure DevOps, `git ls-remote`, clasifica ramas, auto-asigna roles |
| `src/branch_config.py` | Registro de ramas en SQLite (tabla `branch_config`) — persistente, hot-reload, defaults seeded |
| `src/placer.py` | Git genérico: `create_feature_branch`, `git_add_commit_push`, `ensure_auxiliary_branch` (idempotente), `detect_base_branch`, `detect_changed_files`, `aux_branch_name` |
| `src/azure_client.py` | Azure DevOps REST API v7.1: crear PR, buscar PR existente, completar/abandonar PR, estado PR + build |
| `src/logger.py` | Log estructurado |

### API surface completa (22 endpoints)

| Método | Path | Descripción |
|---|---|---|
| `GET` | `/health` | Liveness (sin token) |
| `POST` | `/run` | Encolar tarea git → 202 inmediato; `steps` tracked internamente |
| `GET` | `/status/<task_id>` | Estado de la tarea + `steps` por paso (create_branch/commit_push/create_aux_branch) |
| `GET` | `/tasks` | Últimas N tareas; `?ticket=` filtra por ticket |
| `GET` | `/config/branches` | Ver diccionario de ramas (desde SQLite) |
| `PUT` | `/config/branches` | Actualizar diccionario (persiste en SQLite, hot-reload) |
| `POST` | `/repos` | Registrar repo + inspección inmediata; 403 para repos no registrados en operaciones git |
| `GET` | `/repos` | Listar repos |
| `GET` | `/repos/<name>` | Repo por nombre (incluye `branch_roles` + `branches_by_role`) |
| `POST` | `/repos/<name>/refresh` | Re-inspeccionar repo |
| `DELETE` | `/repos/<name>` | Eliminar del registro |
| `PATCH` | `/repos/<name>/branches/<branch>` | Corregir rol de una rama (sin re-inspeccionar) |
| `GET` | `/projects` | Listar proyectos con sus repos |
| `GET` | `/projects/<org>/<name>` | Proyecto por slug |
| `POST` | `/azure/prepare-and-pr/preview` | **Dry-run:** detecta rama base y archivos sin efectos; devuelve `existing_pr` si ya hay PR |
| `POST` | `/azure/prepare-and-pr` | **Endpoint principal** — idempotente: ensure aux branch + find-or-create PR aux |
| `POST` | `/azure/pull-requests` | Crear feature PR + aux PR simultáneos (legacy) |
| `GET` | `/azure/pull-requests/<pr_id>` | Estado del PR + build CI |
| `PATCH` | `/azure/pull-requests/<pr_id>` | Completar / abandonar / reactivar PR |
| `GET` | `/prs` | Lista PRs persistidos en `pr_store`; `?repo=`, `?status=`, `?task_id=`, `?limit=` |
| `GET` | `/prs/<pr_id>` | PR individual con estado refrescado desde Azure DevOps |

### Git flow implementado

- Features se cortan desde la rama `base` del branch_config (default: `develop`)
- Rama base se detecta automáticamente con `detect_base_branch()` (git merge-base + rev-list)
- Archivos modificados se detectan automáticamente con `detect_changed_files()` (git diff --name-only)
- Rama auxiliar: `{feature_branch}_{target}_auxiliar`, base `origin/{target}`
- `ensure_auxiliary_branch()` — idempotente: crea si no existe, actualiza si los archivos difieren, no-op si está al día
- Repo registry actúa como allowlist de seguridad: 403 si el repo no está registrado

### Diccionario de ramas (defaults — persistidos en SQLite)

| Rama | Label | Rol | `is_base` |
|---|---|---|---|
| `develop` | producción-pre | `base` | ✅ feature branches se cortan desde aquí |
| `developer` | desarrollo | `integration` | — DEV/UAT |
| `test` | pruebas | `integration` | — Preprod |
| `main` | producción-desplegado | `integration` | — Producción |

### Step tracking en tareas

`GET /status/<task_id>` devuelve campo `steps` con estado por paso:

```json
{
  "task_id": "a1b2c3d4",
  "status": "done",
  "steps": {
    "create_branch":    "done",
    "commit_push":      "done",
    "create_aux_branch":"done"
  }
}
```

---

## Pipeline objetivo (claude-mcp-jira como orquestador)

```
Claude Code (MCP tools)
  → claude-mcp-jira
    → Jira          (create, update, transition, comment)
    → code-agent-mcp (run_code_agent, get_code_agent_status)
    → Azure DevOps   (create_azure_pull_request, get_pull_request_status)
    → Jira           (link PR + transición "In Review")
```

Flujo completo desde Claude Code (Fase 11 — implementado):

```
1. create_jira_issue           → ZNRX-XXXXX
2. run_code_agent              → task_id  (202 inmediato)
3. get_code_agent_status       → polling → "done" → {branch, aux_branch, commit_id, steps}
4. create_azure_pull_request   → {action, pr_id, pr_url}  (idempotente via prepare-and-pr)
5. get_pull_request_status     → esperar build verde
6. update_jira_issue           → link PR + transición "In Review"
```

---

## Integración desde claude-mcp-jira (Fase 11 — completa)

### Módulo: `service/clients/code_agent_client.py`

Cliente httpx hacia `code-agent-mcp`. Variables de entorno:

```
CODE_AGENT_URL=http://code-agent-mcp:5001
CODE_AGENT_TOKEN=                         # mismo valor que TOKEN_AZURE del agente
CODE_AGENT_TIMEOUT=30
```

### MCP tools implementados en `jira_mcp/server.py`

| Tool | Rol mínimo | Endpoint que llama | Descripción |
|---|---|---|---|
| `run_code_agent` | lead | `POST /run` | Encola tarea git; retorna `task_id` |
| `get_code_agent_status` | dev | `GET /status/<task_id>` | Estado + steps + branch + commit_id |
| `create_azure_pull_request` | lead | `POST /azure/prepare-and-pr` | Idempotente: ensure aux + find-or-create PR |
| `get_pull_request_status` | dev | `GET /azure/pull-requests/<pr_id>` | Estado PR + build CI |

### Endpoints del agente no expuestos como MCP tools (aún)

| Endpoint | Descripción | Candidato para |
|---|---|---|
| `POST /azure/prepare-and-pr/preview` | Dry-run antes de crear PR | Fase 10 Orchestrator (paso previo) |
| `PATCH /azure/pull-requests/<pr_id>` | Completar / abandonar PR | Futuro MCP tool `complete_pull_request` |
| `GET /prs` | Listar PRs registrados | Futuro MCP tool `list_pull_requests` |
| `GET /prs/<pr_id>` | PR con estado refrescado | Puede unificarse con `get_pull_request_status` |

---

## Coexistencia con n8n y el code-agent original

- `ov-suscripcion-automation` sigue sin cambios para su dominio (migraciones Flyway OV)
- `code-agent-mcp` es independiente — sin dependencia del anterior
- n8n puede seguir usando `ov-suscripcion-automation` para flujos automáticos (webhook Jira)
- `claude-mcp-jira` usa `code-agent-mcp` para flujos supervisados desde Claude Code
- Retirar n8n es una decisión de equipo, no un prerequisito técnico
