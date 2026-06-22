# TODO — claude-mcp-jira

Estado general: Fases 1–5 y 7 completas. Docker validado (8/8 + 10/10). Jira limpio. Próximo: Fase 8 (UI, opcional).
Actualizar este archivo al completar o añadir tareas.

---

## En progreso

*(ninguna)*

---

## Pendiente

### Implementación

- [ ] **Vaciar `JIRA_ALLOWED_PROJECTS`** — allowlist self-service *(decisión pendiente)*
  - Actualmente `JIRA_ALLOWED_PROJECTS=ZNRX,AIPROJECTS,SCRX` bloquea proyectos no listados aunque existan en Jira y estén en la DB (validado con ARQX — auto-discovery OK pero create → 400)
  - Propuesta: dejar `JIRA_ALLOWED_PROJECTS=` vacío; el control de acceso real lo da el PAT de Jira (solo puede crear donde tiene permisos)
  - Impacto: cambio solo en `.env` + reinicio; no requiere código
  - Pendiente de decisión con el equipo antes de aplicar en producción

- [ ] **Fase 8 — UI** *(futura — evaluar antes de implementar)*
  - Ver `arch/evaluations/eval-ui-copilot.md`
  - Objetivo: interfaz web para usuarios no técnicos sobre los mismos endpoints

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
  - [x] `PROJECT_DB_PATH` configurable (default `projects.db`)
