# TODO — claude-mcp-jira

Estado general: Fases 1–5, 7, 8a, 9.1–9.4, 9.5a, 11 completas. Deuda técnica H1-H9 cerrada. Tests: 8+10+19+24+26+19 e2e + 96 unit.
Próximo: Fase 10 Orchestrator formal (WorkflowEngine + WorkflowExecution state) — prerequisito para UI y worklogs integrados.
Evaluación externa: `arch/evaluations/eval-workflow-copilot.md` — arquitectura validada como "Internal Developer Copilot Platform"; orquestación implícita detectada como deuda crítica antes de escalar.
Actualizar este archivo al completar o añadir tareas.

---

## En progreso

*(ninguna)*

---

## Pendiente

### Implementación

- [ ] **Verificar empíricamente conversión Task→Sub-task en ZNRX, SCRX, SAZ** *(bajo — se espera mismo comportamiento)*
  - Limitación documentada en `docs/jira-subtasks.md`: en AIPROJECTS confirmado que la API no lo permite
  - Tipos de sub-task reales obtenidos para los 4 proyectos (ver tabla en `docs/jira-subtasks.md`)
  - ZNRX no tiene tipo "Sub-task" genérico — usar `Subtarea Historia` (id=18124) o `Casos de Prueba` (id=18121)
  - Workaround documentado: crear nuevo Sub-task desde el inicio con `parent` + marcar Task original como Done

- [ ] **Vaciar `JIRA_ALLOWED_PROJECTS`** — allowlist self-service *(decisión pendiente)*
  - Actualmente `JIRA_ALLOWED_PROJECTS=ZNRX,AIPROJECTS,SCRX` bloquea proyectos no listados aunque existan en Jira y estén en la DB (validado con ARQX — auto-discovery OK pero create → 400)
  - Propuesta: dejar `JIRA_ALLOWED_PROJECTS=` vacío; el control de acceso real lo da el PAT de Jira (solo puede crear donde tiene permisos)
  - Impacto: cambio solo en `.env` + reinicio; no requiere código
  - Pendiente de decisión con el equipo antes de aplicar en producción

- [ ] **Tests live Fase 11** *(bajo — requiere code-agent-mcp corriendo)*
  - Ejecutar `bash scripts/test-code-agent.sh --live` con `CODE_AGENT_URL` apuntando a una instancia del agente
  - Verificar flujo completo: `run_code_agent` → `get_code_agent_status` → `create_azure_pull_request` → `get_pull_request_status`
  - Nota: code-agent-mcp ahora expone `steps` por paso en `GET /status/<id>` — considerar exponer en `get_code_agent_status` MCP tool

- [ ] **Fase 10 — Workflow Orchestrator** *(siguiente prioridad — prerequisito para UI y worklogs integrados)*
  - Evaluación: `arch/evaluations/eval-workflow-copilot.md` — orquestación implícita detectada como deuda crítica
  - **Por qué ahora**: el flujo Jira→git→PR ya existe disperso en MCP + service layer + "scripts mentales"; formalizarlo antes de añadir UI evita acoplamiento y debugging infernal
  - **Módulo nuevo**: `service/orchestrator/` con `workflows.py`, `engine.py`, `state.py`
  - **Entidad clave**: `WorkflowExecution { id, ticket, status, steps: [...] }` — estado de negocio explícito (no solo `task_status` técnico)
  - **Workflow principal a implementar**: `CreateFeaturePRWorkflow`:
    1. `create_jira_issue` → ZNRX-XXXXX
    2. `POST /azure/prepare-and-pr/preview` → dry-run: detecta rama base + archivos (endpoint ya existe en code-agent-mcp)
    3. `run_code_agent` → task_id (202); `steps` tracked: create_branch / commit_push / create_aux_branch
    4. `wait_until_done(task_id)` → {branch, aux_branch, commit_id, steps}
    5. `create_azure_pull_request` → {action, pr_id, pr_url}  (idempotente)
    6. `wait_ci(pr_id)` → build verde
    7. `PATCH /azure/pull-requests/<pr_id>` → completar PR cuando aprobado (endpoint ya existe)
    8. `update_jira` → link PR + transición "In Review"
    9. `suggest_worklogs` → preview editable (Fase 9.5b)
  - **Problema resuelto**: MCP solo decide y llama tools; NO coordina workflows completos directamente
  - **Naming automático**: rama siempre `feature/ZNRX-123-descripcion` + linking PR→Jira automático
  - **code-agent-mcp ya provee**: detect_base_branch automático, detect_changed_files, pr_store persistente, step tracking
  - **Prerequisito para**: Fase 8 UI (que mostrará progreso por paso) y Fase 9.5b (worklogs post-PR)
  - **MCP tools candidatos adicionales** (no urgentes — sólo cuando el Orchestrator los necesite):
    - `preview_code_agent` → `POST /azure/prepare-and-pr/preview` (dry-run antes de ejecutar)
    - `complete_pull_request` → `PATCH /azure/pull-requests/<pr_id>` (completar PR aprobado)
    - `list_pull_requests` → `GET /prs` (listar PRs del agente)

- [ ] **Fase 8 — UI (Streamlit MVP)** *(futura — después de Fase 10 Orchestrator; también requiere demanda no-técnica validada)*
  - Evaluación: `arch/evaluations/eval-workflow-copilot.md` sección 5 y `arch/evaluations/eval-orchestrator-copilot.md`
  - **Decisión previa**: ¿hay usuarios no-técnicos que necesiten esto? Sin esa respuesta, no construir
  - UI muestra progreso por paso del WorkflowExecution: 🟡 Creando ticket → 🟡 Ejecutando agent → 🟢 Build OK → ✅ COMPLETADO
  - Fase 1 UI (quick win): registro de horas desde Git con preview editable + factores humanos (checkbox debugging/meetings)
  - Fase 2 UI: trigger de workflows (seleccionar proyecto + repo + feature → ejecutar todo)
  - Stack recomendado: Streamlit MVP → Next.js si hay adopción; login PAT → JWT (PAT nunca al frontend)
  - Implica añadir `POST /auth/login` y `GET /me` al service layer

---

## Futuros cambios (sin fecha — activar cuando el volumen lo justifique)

- **Fase 9.5b — Human factors + learning layer** *(después de Fase 10 Orchestrator + Fase 8 UI)*
  - Factores multiplicadores interactivos: debugging (+30%), meetings (+15%), investigación (+25%) — requieren checkbox en UI
  - Learning layer por usuario: `user_factor = avg(user_input / system_estimate)` persistido en SQLite; ajusta estimación futura automáticamente
  - Evaluación: `arch/evaluations/eval-human-sensity-copilot.md` estrategias 2.2 y 2.4 + `arch/evaluations/eval-workflow-copilot.md` sección 6
  - Integración natural: paso 7 del `CreateFeaturePRWorkflow` → `suggest_worklogs` → preview editable → `register_worklog()`
  - **No implementar** sin UI — los checkboxes sin interfaz gráfica no tienen UX viable

- **Fase 6 — Observabilidad**
  - Métricas Prometheus en `/metrics`
  - Trazas OpenTelemetry con `trace_id` propagado
  - Caching 30-60s en `search_jira_issues`
  - Dashboard Grafana básico

---

## Completado

- [x] Fase 1 — Prototipo CLI (`create`)
- [x] Fase 2 — Service Layer FastAPI + sanitización + audit log
- [x] Fase 3 — Comandos completos (`update`, `summarize`, `list-issues`) + JQL controlado
- [x] Fase 4 — MCP Server SSE + auth API key + RBAC + rate limit + output normalizado
- [x] Fase 4.1 — Ajustes post-validación e2e ZNRX (customfield_25832, priority IDs, Bug fallback)
- [x] Prompts traducidos al español (`create_issue`, `update_issue`, `search_issues`)
- [x] `TICKET_LANG` env var — soporte bilingüe es/en por proyecto
- [x] `scripts/dev.sh` — modos stop/restart/status/both + nohup + pidfile + JIRA_TIMEOUT=30
- [x] `scripts/test-dev.sh` — kill/reinicio automático + prefijo `[MCP Claude Jira Test]`
- [x] Documentación Jira real en `docs/`:
  - [x] `jira-projects.md` — metadata ZNRX, AIPROJECTS, SAZ, SCRX
  - [x] `jira-roles.md` — permisos efectivos por proyecto
  - [x] `jira-fields.md` — campos requeridos/opcionales, restricción screen subtasks
  - [x] `jira-link-types.md` — 29 link types; recomendación SAZ→ZNRX
  - [x] `jira-workflows.md` — statuses y transiciones por proyecto
- [x] Fase 5 — bloqueantes resueltos (link type + campos SAZ documentados)
- [x] Fase 5 — Soporte SAZ implementado:
  - [x] `POST /issues/saz` — SAZ standalone o vinculado a ZNRX (`znrx_key` opcional)
  - [x] MCP tool `create_saz_request` (lead) — text + znrx_key opcional
  - [x] `JIRA_SAZ_PROJECT_KEY=SAZ` en `.env.example`
  - [x] Prompt SAZ especializado en lenguaje DevOps/Release
- [x] Fase 4.2 — Deuda técnica: JQL injection, audit MCP, rate limiter compartido, 52 unit tests
- [x] Fase 4.3 — Transiciones y log work: `POST /issues/{key}/transition` + `POST /issues/{key}/worklog`
- [x] Docker — build + e2e 8/8 service + 10/10 MCP (cert DER→PEM, puertos 18000/18001, JIRA_TIMEOUT=30)
- [x] Bitácora de tests — `logs/test-results.jsonl`, `scripts/test-docker.sh`, `scripts/test-log.sh`
- [x] Fase 4.4 — Mejoras API:
  - [x] `POST /issues/{key}/comments` + MCP tool `add_comment_jira_issue` (dev)
  - [x] `POST /issues/{key}/assign` + MCP tool `assign_jira_issue` (lead)
  - [x] `POST /issues/{key}/priority` + MCP tool `set_priority_jira_issue` (lead)
  - [x] `POST /issues/{key}/labels` — SET/ADD/REMOVE
  - [x] `POST /issues/{key}/clone` — subtasks y top-level; overrides opcionales vía texto
  - [x] `/actions` tipado (enum long-tail); Swagger deshabilitado en `APP_ENV=prod`
  - [x] `example=` en `Field()` de todos los schemas Request
- [x] Fase 4.5 — Link dinámico (eval-link-copilot):
  - [x] `GET /issue-link-types` — tipos reales de Jira con cache TTL 1h
  - [x] `POST /issues/{key}/link` — Claude recibe lista real, elige por nombre (no ID hardcodeado)
  - [x] `clone_issue()` y `link_issue()` usan `type.name` en lugar de `type.id`
  - [x] MCP tool `link_jira_issues` (dev)
- [x] Limpieza Jira — 6 tickets `[MCP Claude Jira Test]` eliminados el 2026-06-20
  - ZNRX-68147, 68154, 68163 (top-level + subtasks), 68161, 68162, 68170 (subtasks directos)
- [x] Fase 7 — Multi-proyecto + SQLite auto-discovery:
  - [x] `service/clients/project_config.py` — configs ZNRX/AIPROJECTS/SCRX + `resolve_project()` + `get_config()`
  - [x] `project` opcional en `POST /issues` y `POST /issues/search`
  - [x] `create_issue()` y `update_issue()` y `set_priority()` usan config del proyecto
  - [x] `build_jql()` acepta `project_key` para acotar búsqueda
  - [x] `JIRA_DEFAULT_PROJECT` + `JIRA_ALLOWED_PROJECTS` en `.env`/`.env.example`
  - [x] MCP tools `create_jira_issue` y `search_jira_issues` aceptan `project` opcional
  - [x] CLI `create` y `list-issues` aceptan `--project` flag
  - [x] `TICKET_LANG` per-proyecto según `project_config.py`
  - [x] `service/clients/project_db.py` — SQLite + auto-discovery lazy desde Jira
  - [x] Seed ZNRX/AIPROJECTS/SCRX en startup (constraints conocidos)
  - [x] Proyectos desconocidos: verify en Jira + intenta `createmeta` + persiste en DB
  - [x] `GET /projects` + `GET /projects/{key}` — consulta + discovery explícito
  - [x] `PROJECT_DB_PATH` configurable (default resuelve relativo al módulo)
- [x] Deuda técnica H1–H9 — remediación completa (2026-06-22):
  - [x] H1: `scripts/test-actions.sh` — 24/24 e2e (comments, assign, priority, labels, worklog, transition, clone, link, saz)
  - [x] H2: auto-link check en `link.py` (422 si source == target)
  - [x] H3: rate limit en endpoints GET públicos (`/issue-link-types`, `/projects`, `/projects/{key}`)
  - [x] H4: mitigado por H3 — sin cambios de código
  - [x] H5: `znrx_key` con pattern regex en `CreateSAZRequest`
  - [x] H6: `LabelsRequest`/`LabelsResponse` schemas dedicados
  - [x] H7: `assignee min_length=1` en `AssignIssuePayload`
  - [x] H8: `time_spent_seconds ge=60` en `LogWorkPayload`
  - [x] H9: `PROJECT_DB_PATH` relativo al módulo en `project_db.py`
- [x] Fase 9 — Git Intelligence completa (2026-06-22):
  - [x] 9.1 Scanner (`service/git/scanner.py`) — subprocess git log, solo metadata
  - [x] 9.2 Analyzer + mapper (`service/git/analyzer.py`, `service/git/mapper.py`) — sesiones, estimación de tiempo, extracción de issue key
  - [x] 9.3 `POST /git/sync` + MCP tool `sync_git_worklogs` (dev+) — dry_run/real, Claude NLP fallback
  - [x] 9.4 Repo registry (`service/git/repo_registry.py`) — SQLite `git_repos`, CRUD, fallback por default_issue_key
  - [x] MCP tools `register_git_repo` + `list_git_repos` (dev+)
  - [x] `POST/GET/DELETE /git/repos` endpoints REST
- [x] Documentación BD (`arch/bd/README.md`) — tablas `projects` y `git_repos`, columnas, repos actuales, endpoints (2026-06-22)
- [x] Lagunas multi-proyecto cerradas (2026-06-22):
  - [x] L1: `clone_issue()` usa config dinámica por proyecto (`get_config(_project_from_key(source_key))`)
  - [x] L2, L3: no requieren fix (documentado en `arch/fix/fix-multi-project-gaps.md`)
- [x] Deuda documentación Fase 9 cerrada (2026-06-23):
  - [x] Bug `repo_path` en `required` de MCP `sync_git_worklogs` — quitado (`"required": []`)
  - [x] `.env.example` sin variables `GIT_*` — añadida sección `GIT INTELLIGENCE` con los 4 parámetros
  - [x] `jira_mcp/README.md` sin tools Fase 9 — tabla herramientas + RBAC + limitación Docker actualizadas
  - [x] Limitación Docker `git sync` documentada en `jira_mcp/README.md`
- [x] `scripts/test-git.sh` — 26/26 e2e Git Intelligence (2026-06-23):
  - CRUD `/git/repos`: register, list, get, 404, upsert, delete, 404-post-delete
  - `/git/sync`: dry_run por repo_path, por repo_name, error 404 alias inválido, error 422 path relativo
- [x] Unit tests `analyzer.py` + `mapper.py` — 37 tests (2026-06-23): suite total 89 unit tests
  - `test_git_mapper.py`: 15 tests — message key, branch fallback, precedencia, límites de patrón
  - `test_git_analyzer.py`: 22 tests — sesiones, gap, ordenación, issue key, confidence, LOC, estimación
- [x] Fase 9.5a — Claude humanizer de estimación (2026-06-23):
  - `service/prompts/git_humanizer.txt` — señales: debugging keywords, high churn (LOC>400), late-night (20-23/0-5)
  - `parse_git_humanizer(session)` en `claude_client.py` — clamp 0.25–4.0h, redondeo 0.25h, falla silenciosamente al base
  - `GitSessionResult` — `base_estimated_hours` (solo cuando hay ajuste) + `humanizer_reason`
  - `git_sync.py` — paso post-analyzer; flag `GIT_HUMANIZER=true` en `.env.example`
- [x] Fase 11 — Integración code-agent-mcp (2026-06-23):
  - `service/clients/code_agent_client.py` — cliente httpx: `run_task`, `get_task_status`, `prepare_and_pr`, `get_pr_status`; auth `X-Agent-Token`
  - `jira_mcp/service_client.py` — 4 funciones: `run_code_agent`, `get_code_agent_status`, `create_azure_pull_request`, `get_pull_request_status`; `_agent_client()` independiente del `_client()` Jira
  - `jira_mcp/server.py` — 4 tools MCP con schema completo + dispatch; lead: `run_code_agent`, `create_azure_pull_request`; dev: status tools
  - `scripts/test-code-agent.sh` — 19/19 tests (schema, dispatch, funciones, env vars)
  - `.env.example` — sección `CODE AGENT MCP`: `CODE_AGENT_URL`, `CODE_AGENT_TOKEN`, `CODE_AGENT_TIMEOUT`
  - `code-agent-mcp` ya funcional (73 tests, PRs #2552-2554 reales); claude-mcp-jira ahora orquesta flujo completo Jira → git → PR Azure
- [x] Fase 8a — PAT dinámico por usuario vía `X-Jira-Token` (2026-06-23):
  - `service/clients/jira_client.py` — `ContextVar _request_pat` + `_get_headers()`; fallback a `JIRA_PAT` env
  - `service/middleware/jira_auth.py` — `JiraAuthMiddleware` extrae header, inyecta ContextVar con `try/finally`
  - `service/audit.py` — `pat_source: "header" | "env"` en cada entrada; token nunca logueado
  - `service/main.py` — middleware registrado; versión `0.5.0`
  - `jira_mcp/service_client.py` — `jira_token` opcional en todas las funciones; `_client(user, jira_token)`
  - `jira_mcp/server.py` — `jira_token` propiedad opcional en los 9 tools MCP; dispatch propaga
  - `tests/test_jira_pat_routing.py` — 7 tests; suite total 96 unit tests
