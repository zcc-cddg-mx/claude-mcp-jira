# Code Agent MCP — Plan de integración con claude-mcp-jira

## Contexto

`code-agent-mcp` es un agente HTTP genérico que ejecuta operaciones git y crea PRs en Azure DevOps.
Vive en `/home/idavid/dev/claude/code-agent-mcp`.

Se creó desde cero (no modificando `ov-suscripcion-automation`) tomando solo la infraestructura
genérica del code-agent original y descartando toda lógica específica del dominio Flyway/OV.

---

## Estado actual del `code-agent-mcp` (2026-06-25)

**133 tests.** Funcional e2e contra Azure DevOps (Zurich Insurance Ecuador) — PRs #2552–#2575 reales creados.

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

### API surface completa (23 endpoints)

#### Sistema

| Método | Path | Auth | Descripción |
|---|---|---|---|
| `GET` | `/health` | ❌ libre | Liveness check |

#### Tareas git (asíncronas)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| `POST` | `/run` | ✅ | Encolar tarea git (branch + commit + push + aux branch) → 202 inmediato; body: `repo`, `branch`, `files` (non-empty list), `ticket`, `commit_message`, `base_branch?`, `target?`, `callback_url?` |
| `GET` | `/status/<task_id>` | ✅ | Estado + `steps` (create_branch / commit_push / create_aux_branch); status: queued / running / done / error / rejected |
| `GET` | `/tasks` | ✅ | Últimas N tareas (default 50, max 200); `?ticket=` filtra por ticket |

#### Configuración de ramas (global)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| `GET` | `/config/branches` | ✅ | Ver diccionario global de ramas desde SQLite |
| `PUT` | `/config/branches` | ✅ | Reemplazar / actualizar diccionario de ramas (persiste, hot-reload); body: `{branch_name: {label, environment, url?, is_base?}}` |

#### Repositorios

| Método | Path | Auth | Descripción |
|---|---|---|---|
| `POST` | `/repos` | ✅ | Registrar repo: inspección via Azure API + git ls-remote; body: `git_url` (req), `local_path?`; 409 si ya existe |
| `GET` | `/repos` | ✅ | Listar todos los repos registrados |
| `GET` | `/repos/<name>` | ✅ | Repo por nombre; incluye `branch_roles` + `branches_by_role` (invertido) + `branch_map` |
| `PATCH` | `/repos/<name>/branches/<branch>` | ✅ | Asignar rol de una rama: body `{role: base\|integration\|feature\|other}` |
| `PATCH` | `/repos/<name>/branch-map` | ✅ | Mapping target→branch por repo: body `{developer: "developer", test: "test", prod: "develop"}`; sobreescribe resolución global para ese repo |
| `POST` | `/repos/<name>/refresh` | ✅ | Re-inspeccionar repo (re-clasifica ramas desde Azure + git ls-remote) |
| `DELETE` | `/repos/<name>` | ✅ | Eliminar repo del registro |

#### Proyectos Azure DevOps

| Método | Path | Auth | Descripción |
|---|---|---|---|
| `GET` | `/projects` | ✅ | Listar proyectos con lista de repos por proyecto |
| `GET` | `/projects/<org>/<name>` | ✅ | Proyecto por slug `{org}/{name}` con repos |

#### Pull Requests — Azure DevOps

| Método | Path | Auth | Descripción |
|---|---|---|---|
| `POST` | `/azure/prepare-and-pr/preview` | ✅ | **Dry-run:** detecta `base_branch` + archivos cambiados + `aux_branch` + `existing_pr` sin crear nada; body: `repo`, `branch`, `target` (req), `repo_path?`, `files?`, `base_branch?` |
| `POST` | `/azure/prepare-and-pr` | ✅ | **Principal (idempotente):** ensure aux branch → find-or-create PR auxiliar; body: `repo`, `branch`, `target`, `ticket`, `title` (req), `repo_path?`, `files?`, `base_branch?`, `description?`; retorna 200 (existente) o 201 (nuevo) |
| `POST` | `/azure/pull-requests` | ✅ | Legacy: crear feature PR + aux PR simultáneos; body: `branch`, `aux_branch`, `title`, `repo` (req), `description?`, `target?` |
| `GET` | `/azure/pull-requests/<pr_id>` | ✅ | Estado PR + build CI; query: `repo` (req si no hay AZURE_REPO); retorna `{pr_id, status, build_status, pr_url}` |
| `PATCH` | `/azure/pull-requests/<pr_id>` | ✅ | Cambiar estado PR; body: `repo` (req), `status: completed\|abandoned\|active`; actualiza `pr_store` local |

#### Pull Requests — Registro local (pr_store)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| `GET` | `/prs` | ✅ | Listar PRs del registro local; `?repo=`, `?status=`, `?task_id=`, `?limit=` (default 50) |
| `GET` | `/prs/<pr_id>` | ✅ | PR del registro con estado refrescado desde Azure; si no está en registry, devuelve datos live sin persistir |

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

## Pipelines disponibles

### Flujo feature completo (Fase 11 — `run_create_feature_pr_workflow`)

```
1. create_jira_issue           → ZNRX-XXXXX
2. run_code_agent              → task_id  (202 inmediato; commit + push en background)
3. get_code_agent_status       → polling → "done" → {branch, aux_branch, commit_id}
4. create_azure_pull_request   → {pr_id, pr_url}  (idempotente; aux branch → integration)
5. get_pull_request_status     → polling → build verde
6. update_jira_issue           → comentario con link PR + transición "In Review"
```

### Flujo despliegue (Fase 12 — `create_deployment_saz_workflow`)

```
[rama ya tiene cambios — no se necesita commit]
1. get_repo_by_alias           → repo_path desde registry claude-mcp-jira
2. create_azure_pull_request   → PR aux (feature/REQ → developer|test|develop)
3. create_deployment_saz       → SAZ Jira con datos del PR (template determinista)
   retorna → {pr_id, pr_url, aux_branch, saz_key, summary}
```

### Ciclo de vida de PR (Fase 12 — `update_pull_request_status`)

```
update_pull_request_status(pr_id, repo, "abandoned")  → DevOps cierra sin merge
update_pull_request_status(pr_id, repo, "completed")  → DevOps completa/merge
update_pull_request_status(pr_id, repo, "active")     → DevOps reactiva PR cerrado
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

### MCP tools implementados en `jira_mcp/server.py` (Fases 11 + 12)

| Tool | Rol mínimo | Endpoint que llama | Descripción |
|---|---|---|---|
| `run_code_agent` | lead | `POST /run` | Encola tarea git; retorna `task_id` |
| `get_code_agent_status` | dev | `GET /status/<task_id>` | Estado + steps + branch + commit_id |
| `create_azure_pull_request` | lead | `POST /azure/prepare-and-pr` | Idempotente: ensure aux + find-or-create PR |
| `get_pull_request_status` | dev | `GET /azure/pull-requests/<pr_id>` | Estado PR + build CI |
| `update_pull_request_status` | lead | `PATCH /azure/pull-requests/<pr_id>` | Cambiar estado PR: abandoned / completed / active |
| `create_deployment_saz_workflow` | lead | `POST /azure/prepare-and-pr` + service layer | Workflow sincrónico: resolve repo → PR → SAZ |
| `set_repo_branch_map` | lead | `PATCH /repos/<name>/branch-map` | Configura mapping target→branch por repo |

### Endpoints del agente no expuestos como MCP tools (aún)

| Endpoint | Descripción | Candidato para |
|---|---|---|
| `POST /azure/prepare-and-pr/preview` | Dry-run antes de crear PR | Usado internamente en `run_create_feature_pr_workflow` |
| `POST /azure/pull-requests` | Crear feature + aux PR (legacy) | Sin uso activo — reemplazado por `prepare-and-pr` |
| `GET /prs` | Listar PRs del registro local | Futuro MCP tool `list_pull_requests` |
| `GET /prs/<pr_id>` | PR individual con estado refrescado | Puede unificarse con `get_pull_request_status` |
| `POST /repos` | Registrar repo | Administración manual vía Swagger — no exponer como MCP |
| `PUT /config/branches` | Actualizar diccionario global de ramas | Administración manual vía Swagger |

---

## Coexistencia con n8n y el code-agent original

- `ov-suscripcion-automation` sigue sin cambios para su dominio (migraciones Flyway OV)
- `code-agent-mcp` es independiente — sin dependencia del anterior
- n8n puede seguir usando `ov-suscripcion-automation` para flujos automáticos (webhook Jira)
- `claude-mcp-jira` usa `code-agent-mcp` para flujos supervisados desde Claude Code
- Retirar n8n es una decisión de equipo, no un prerequisito técnico
