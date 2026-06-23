# TODO — claude-mcp-jira

Estado general: Fases 1–5, 7 y 9.1–9.4 completas. Deuda técnica H1-H9 cerrada. Tests: 8+10+19+24+26 e2e + 52 unit. Próximo: Fase 8a (PAT dinámico) o unit tests Git Intelligence.
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

- [ ] **Fase 8a — PAT dinámico por usuario** *(futura — corto plazo, bajo esfuerzo)*
  - `X-Jira-Token` header opcional en service layer — sobreescribe `JIRA_PAT` del `.env`
  - Sin header → usa cuenta de servicio (comportamiento actual, sin ruptura)
  - Cambios: `ContextVar` en `jira_client.py` + middleware FastAPI + parámetro MCP opcional
  - Habilita autoría correcta en Jira y es el fundamento de Fase 8 UI
  - Ver plan completo en `arch/design/implementation-plan.md` → Fase 8a

- [ ] **Fase 8 — UI** *(futura — solo si hay demanda no-técnica demostrada)*
  - Ver `arch/evaluations/eval-ui-copilot.md` y evaluación en `arch/design/implementation-plan.md`
  - Recomendación: Streamlit MVP primero; migrar a Next.js si hay adopción real
  - Login PAT → JWT (PAT nunca al frontend); preview human-in-the-loop
  - Implica añadir `POST /auth/login` y `GET /me` al service layer

- [ ] **Unit tests para módulos Git Intelligence** *(deuda de cobertura — menor)*
  - `tests/` no tiene unit tests para `analyzer.py` y `mapper.py` (lógica de sesiones y extracción de issue key)
  - `scanner.py` y `repo_registry.py` dependen de filesystem/subprocess — e2e suficiente para esos
  - El e2e `scripts/test-git.sh` ya cubre los endpoints; unit tests añadirían cobertura de lógica interna

- [ ] **Fase 9.5 — Human-sensity en worklogs** *(futura — mejora de calidad)*
  - Ver `arch/evaluations/eval-human-sensity-worklogs.md` (pendiente de crear)
  - Objetivo: que los worklogs auto-registrados se sientan naturales, no mecánicos
  - Señales adicionales: tipo de archivo cambiado, hora del día, densidad de commits, patrón de mensajes
  - Human-in-the-loop: preview editable antes de registrar (`dry_run=true` + ajuste manual)
  - Integración con `default_issue_key` del repo registry para fallbacks con sentido

---

## Futuros cambios (sin fecha — activar cuando el volumen lo justifique)

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
