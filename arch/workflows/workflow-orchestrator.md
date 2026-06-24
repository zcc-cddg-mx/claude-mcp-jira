# Fase 10 — Workflow Orchestrator

## Contexto

La orquestación Jira→git→PR ya existe pero está dispersa entre los tools MCP, el service layer y
"scripts mentales". La evaluación `arch/evaluations/eval-workflow-copilot.md` lo identifica como
deuda crítica: sin un Orchestrator formal el MCP se sobrecarga de lógica de coordinación, el
estado de negocio es invisible (solo hay `task_status` técnico), y construir UI encima es imposible.

**Decisiones de diseño:**
- El MCP tool ejecuta los pasos secuencialmente + hace el polling. El service layer solo persiste estado.
- El entry point es un `issue_key` ya existente (ZNRX-123) — el workflow NO crea el ticket.

---

## Arquitectura

```
Claude Code (MCP tools)
  → run_create_feature_pr_workflow   ← NEW tool (lead)
  → get_workflow_status              ← NEW tool (dev)
     ↓
claude-mcp-jira service layer
  POST /workflows/create-feature-pr  ← crea registro pending
  GET  /workflows/{execution_id}     ← consulta estado
  PATCH /workflows/{execution_id}    ← actualiza estado tras cada paso
     ↓
service/clients/workflow_store.py    ← SQLite persistence
service/clients/code_agent_client.py ← ya existe (Fase 11)
service/clients/jira_client.py       ← ya existe
     ↓
code-agent-mcp      (POST /run, GET /status, POST /azure/prepare-and-pr/preview, POST /azure/prepare-and-pr)
Jira REST API v2    (PATCH /issues/{key})
```

---

## Nuevos archivos

| Archivo | Responsabilidad |
|---|---|
| `service/clients/workflow_store.py` | SQLite tabla `workflow_executions` — CRUD |
| `service/routes/workflows.py` | REST endpoints del orchestrator |
| `service/schemas/workflow_schemas.py` | Pydantic models |

**Patrones de referencia:**
- `workflow_store.py` → seguir `service/clients/project_db.py` (`threading.Lock` + `CREATE TABLE IF NOT EXISTS` + upsert)
- `routes/workflows.py` → seguir `service/routes/git_sync.py` (coordinación multi-paso)
- `workflow_schemas.py` → seguir `service/schemas/git_schemas.py`

---

## Entidad WorkflowExecution — SQLite

```sql
CREATE TABLE IF NOT EXISTS workflow_executions (
    execution_id   TEXT PRIMARY KEY,           -- UUID 8 chars
    workflow_type  TEXT NOT NULL,              -- "create_feature_pr"
    issue_key      TEXT NOT NULL,              -- ZNRX-123
    status         TEXT NOT NULL,              -- pending|running|completed|failed
    steps_json     TEXT NOT NULL DEFAULT '[]', -- [{name, status, detail?}]
    result_json    TEXT,                       -- {pr_id, pr_url, branch, aux_branch} al completar
    error          TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    user           TEXT NOT NULL
);
```

**Funciones del store:**
- `init_workflow_db()` — llamado en `lifespan` de `service/main.py`
- `create_execution(execution_id, workflow_type, issue_key, user)` → dict
- `update_execution(execution_id, status, steps=None, result=None, error=None)` → None
- `get_execution(execution_id)` → dict | None
- `list_executions(issue_key=None, status=None, limit=20)` → list[dict]

---

## Schemas Pydantic — `service/schemas/workflow_schemas.py`

```python
class CreateFeaturePRRequest(BaseModel):
    issue_key: str = Field(..., pattern=r"^[A-Z]+-\d+$")
    repo: str
    repo_path: str
    target: str = "developer"
    commit_message: str = Field(..., max_length=500)
    files: list[str] = []          # vacío → auto-detect vía preview

class WorkflowStepStatus(BaseModel):
    name: str                      # preview|run_agent|wait_agent|create_pr|wait_ci|update_jira
    status: str                    # pending|running|done|failed
    detail: str | None = None

class WorkflowExecutionResponse(BaseModel):
    execution_id: str
    workflow_type: str
    issue_key: str
    status: str                    # pending|running|completed|failed
    steps: list[WorkflowStepStatus]
    result: dict | None = None     # {pr_id, pr_url, branch, aux_branch}
    error: str | None = None
    created_at: str
    updated_at: str

class WorkflowUpdateRequest(BaseModel):
    status: str | None = None
    steps: list[WorkflowStepStatus] | None = None
    result: dict | None = None
    error: str | None = None
```

---

## Endpoints REST — `service/routes/workflows.py`

| Método | Path | Descripción |
|---|---|---|
| `POST` | `/workflows/create-feature-pr` | Crea registro `pending`; retorna `execution_id` |
| `GET` | `/workflows/{execution_id}` | Estado actual del workflow |
| `GET` | `/workflows` | Lista (`?issue_key=`, `?status=`, `?limit=20`) |
| `PATCH` | `/workflows/{execution_id}` | Actualiza status/steps/result (llamado por MCP tool tras cada paso) |

---

## Steps del workflow `CreateFeaturePR`

| # | Step name | Endpoint | Acción |
|---|---|---|---|
| 1 | `preview` | `POST /azure/prepare-and-pr/preview` (code-agent) | Detecta base_branch + files; sin side effects |
| 2 | `run_agent` | `POST /run` (code-agent) | Encola tarea git → task_id |
| 3 | `wait_agent` | `GET /status/{task_id}` × N (code-agent) | Polling hasta done/error (max 60 × 5s = 5 min) |
| 4 | `create_pr` | `POST /azure/prepare-and-pr` (code-agent) | Idempotente: ensure aux branch + find-or-create PR |
| 5 | `wait_ci` | `GET /azure/pull-requests/{pr_id}` × N (code-agent) | Polling hasta build≠pending (max 120 × 15s = 30 min) |
| 6 | `update_jira` | `PATCH /issues/{issue_key}` (jira) | Link PR + comentario + transición "In Review" |

Tras cada paso el MCP tool llama `PATCH /workflows/{execution_id}` para persistir el progreso.

Si timeout en step 3 o 5: `status=failed`, retorna `execution_id` para retry manual vía `get_workflow_status`.

---

## MCP tools nuevos

### `run_create_feature_pr_workflow` (rol: lead)

```json
{
  "name": "run_create_feature_pr_workflow",
  "description": "Ejecuta el workflow completo: preview → git → PR → CI → link Jira. Retorna execution_id con estado final.",
  "inputSchema": {
    "type": "object",
    "required": ["issue_key", "repo", "repo_path", "commit_message"],
    "properties": {
      "issue_key":      {"type": "string", "description": "Ticket Jira existente (ZNRX-123)"},
      "repo":           {"type": "string", "description": "Nombre del repo en Azure DevOps"},
      "repo_path":      {"type": "string", "description": "Ruta absoluta del repo en code-agent server"},
      "target":         {"type": "string", "description": "Integration branch (default: developer)"},
      "commit_message": {"type": "string"},
      "files":          {"type": "array", "items": {"type": "string"}, "description": "Vacío → auto-detect vía preview"},
      "jira_token":     {"type": "string"}
    }
  }
}
```

**Flujo interno (MCP tool ejecuta todos los pasos):**

```
1. POST /workflows/create-feature-pr           → execution_id
2. POST /azure/prepare-and-pr/preview          → files_detected, base_branch
3. PATCH /workflows/{id} preview=done
4. POST /run                                   → task_id
5. PATCH /workflows/{id} run_agent=running
6. LOOP GET /status/{task_id} → done/error     (max 60 × 5s)
7. PATCH /workflows/{id} wait_agent=done
8. POST /azure/prepare-and-pr                  → {pr_id, pr_url}
9. PATCH /workflows/{id} create_pr=done
10. LOOP GET /azure/pull-requests/{pr_id}       (max 120 × 15s)
11. PATCH /workflows/{id} wait_ci=done
12. PATCH /issues/{issue_key}  link PR + transición
13. PATCH /workflows/{id} status=completed, result={...}
```

**Output al LLM:**
```json
{"execution_id": "...", "status": "completed", "issue_key": "ZNRX-123",
 "branch": "feature/ZNRX-123-...", "pr_id": 2600, "pr_url": "https://..."}
```

### `get_workflow_status` (rol: dev)

```json
{
  "name": "get_workflow_status",
  "description": "Consulta el estado de una ejecución de workflow (polling manual o diagnóstico).",
  "inputSchema": {
    "type": "object",
    "required": ["execution_id"],
    "properties": {
      "execution_id": {"type": "string"}
    }
  }
}
```

---

## Modificaciones a archivos existentes

| Archivo | Cambio |
|---|---|
| `service/main.py` | Añadir `init_workflow_db()` en `lifespan`; importar y registrar `workflows_router` |
| `service/routes/__init__.py` | Exportar `workflows_router` |
| `jira_mcp/server.py` | 2 tool definitions en `_make_tools()` + 2 dispatch branches en `call_tool()` |
| `jira_mcp/service_client.py` | 2 funciones: `run_workflow(...)` y `get_workflow_status(execution_id)` |

---

## Verificación

```bash
# 1. Levantar stack
bash scripts/dev.sh restart

# 2. Crear workflow (solo persiste — no ejecuta nada)
curl -s -X POST http://localhost:18000/workflows/create-feature-pr \
  -H "Content-Type: application/json" -H "x-user: carlos.duarte2" \
  -d '{"issue_key":"ZNRX-123","repo":"ov-arizona","repo_path":"/repos/ov-arizona","commit_message":"test"}' \
  | python3 -m json.tool
# Respuesta esperada: {"execution_id": "abc12345", "status": "pending", "steps": [], ...}

# 3. Consultar estado
curl -s http://localhost:18000/workflows/abc12345 -H "x-user: carlos.duarte2"

# 4. Listar ejecuciones
curl -s "http://localhost:18000/workflows?issue_key=ZNRX-123" -H "x-user: carlos.duarte2"

# 5. Tests MCP schema (añadir checks de run_create_feature_pr_workflow y get_workflow_status)
bash scripts/test-code-agent.sh   # debe pasar existentes + nuevos

# 6. Live e2e (requiere code-agent-mcp corriendo en :5001)
bash scripts/test-code-agent.sh --live
```

---

## Notas de implementación

- **No crear `service/orchestrator/`** — la eval lo sugiere pero `service/routes/` + `service/clients/` es suficiente y evita over-engineering
- El MCP tool es el "engine" — el service layer solo persiste estado, no coordina
- `workflow_store.py` va en `service/clients/` (par de `project_db.py`)
- `workflow_schemas.py` va en `service/schemas/` (par de `git_schemas.py`)
- `workflows.py` va en `service/routes/` (par de `git_sync.py`)
- Incluir en `CLAUDE.md` y `jira_mcp/README.md` al completar la fase
