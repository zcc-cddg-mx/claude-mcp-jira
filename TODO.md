# TODO — claude-mcp-jira

Estado general: Fases 1–4.3 completas + labels/actions implementados. Docker validado (8/8 + 10/10). Mejoras API pendientes según eval-apis-copilot + eval-swagger-copilot.
Actualizar este archivo al completar o añadir tareas.

---

## En progreso

*(ninguna)*

---

## Pendiente

### Mejoras API (eval-apis-copilot + eval-swagger-copilot)

#### Alta prioridad

- [ ] **`POST /issues/{key}/comments`** — endpoint dedicado para comentarios
  - Actualmente el comentario está dentro del `PATCH /issues/{key}` general → poco visible para MCP
  - Patrón: texto libre → Claude → `{"comment": "..."}` → Jira `POST /rest/api/2/issue/{key}/comment`
  - Agregar tool MCP `add_comment_jira_issue` (rol dev)

- [ ] **Swagger deshabilitado en producción**
  - En `service/main.py`: `docs_url="/docs" if ENV=="dev" else None`
  - Variable de entorno `APP_ENV=dev|prod` en `.env.example` y `docker-compose.yml`

#### Media prioridad

- [ ] **`POST /issues/{key}/assign`** — endpoint dedicado para asignación
  - Patrón: texto libre → Claude → `{"assignee": "user.name"}` → Jira `PUT /rest/api/2/issue/{key}/assignee`
  - Agregar tool MCP `assign_jira_issue` (rol lead)

- [ ] **`POST /issues/{key}/priority`** — endpoint dedicado para prioridad
  - Actualmente dentro del `PATCH /issues/{key}` general
  - Patrón: texto libre → Claude → `{"priority": "High"}` → ID mapping → Jira PUT
  - Agregar tool MCP `set_priority_jira_issue` (rol lead)

- [ ] **Migrar labels de `/actions` a `/issues/{key}/labels`**
  - El eval clasifica labels como endpoint core (no long-tail)
  - Mover lógica de `actions.py` a nuevo `service/routes/labels.py`
  - `/actions` queda reservado para acciones long-tail: watchers, links, custom fields

- [ ] **`/actions` tipado con enum** — validar `action` contra lista permitida antes de llamar a Claude
  - Acciones long-tail iniciales: `add_watcher`, `link_issue`, `set_fix_version`, `set_component`, `update_custom_field`

#### Baja prioridad / opcional

- [ ] **`example` en `Field()` de schemas** — mejora UI de `/docs`
  - Añadir `example=` en los campos `text` de cada `Request` model
  - Sin impacto funcional, solo mejora la documentación interactiva

### Implementación

- [ ] **Fase 5 — Soporte SAZ** — tickets Solicitudes Release Zurich vinculados a ZNRX
  - Bloqueantes resueltos: link type = `Relates` (id `10003`), campos SAZ en `docs/jira-fields.md`
  - Ver plan completo en `arch/design/implementation-plan.md` → Fase 5
  - Entregables: `service/routes/saz.py`, prompt SAZ, herramienta MCP `create_saz_request`

- [ ] **Fase 6 — Observabilidad** *(opcional — activar cuando el volumen lo justifique)*
  - Métricas Prometheus en `/metrics`
  - Trazas OpenTelemetry con `trace_id` propagado
  - Caching 30-60s en `search_jira_issues`
  - Dashboard Grafana básico

### Deuda técnica

#### Crítica (seguridad) — resuelto en 2026-06-19

- [x] **JQL injection** — `assignee`/`status`/`issuetype`/`priority` escapados con `_jql_escape()` en `jql_builder.py`
- [x] **MCP sin audit log** — `jira_mcp/server.py` ahora escribe en `AUDIT_LOG_PATH` con `request_id` en cada tool call
- [x] **HTTP responses exponen internals** — todas las rutas llaman `sanitize(str(e))` antes de incluir error en HTTPException detail

#### Media (confiabilidad) — resuelto en 2026-06-19

- [x] **JSON parsing sin control** — `json.loads()` envuelto en `_parse_json()` con `ValueError` descriptivo en `claude_client.py`
- [x] **Rate limiter duplicado** — lógica extraída a `shared/rate_limiter.py`; `service/` y `jira_mcp/` usan `RateLimiter` con sus propios parámetros
- [x] **Respuesta service layer sin validar** — `service_client.py` llama `_require()` para verificar campos esperados
- [x] **SSE handler sin timeout** — `asyncio.wait_for(..., timeout=MCP_SSE_TIMEOUT)` en `handle_sse`; default 300s
- [x] **Audit log sin rotación** — `service/audit.py` usa `RotatingFileHandler` (10 MB × 5 backups); configurable via `AUDIT_LOG_MAX_BYTES` / `AUDIT_LOG_BACKUP_COUNT`

#### Baja (mantenibilidad) — resuelto en 2026-06-19

- [x] **`scripts/dev.sh` — path miniconda hardcodeado** — extraído a `scripts/_conda_env.sh`; detecta `$CONDA_PREFIX`, `conda info --base` o búsqueda en paths comunes
- [x] **Tests unitarios** — `tests/` con pytest: 52 tests, 4 módulos (sanitizer, jql_builder, auth, rbac); cobertura de inyección JQL, RBAC y sanitización
- [x] **SSE handler — `import json` tardío** — movido al top de `server.py`

### Limpieza Jira

- [x] **Eliminar tickets `[MCP Claude Jira Test]` activos** — 10 tickets + subtareas eliminados el 2026-06-19
  - Los tickets de hackathon (ZNRX-67942..67946) son histórico del proyecto y no se tocan

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
  - [x] `jira-fields.md` — campos requeridos/opcionales y valores permitidos
  - [x] `jira-link-types.md` — 29 link types; recomendación SAZ→ZNRX
  - [x] `jira-workflows.md` — statuses y transiciones por proyecto
- [x] Fase 5 — bloqueantes resueltos (link type + campos SAZ documentados)
- [x] Limpieza Jira — 17 tickets de prueba eliminados (+ ~90 subtareas)
- [x] Test e2e MCP server — 10/10 passed (`scripts/test-mcp.sh`)
- [x] Fase 4.2 — Deuda técnica: JQL injection, audit MCP, rate limiter compartido, 52 unit tests, path conda portable
- [x] Fase 4.3 — Transiciones y log work: `POST /issues/{key}/transition` + `POST /issues/{key}/worklog`
- [x] Docker — build + e2e 8/8 service + 10/10 MCP (cert DER→PEM, puertos 18000/18001, JIRA_TIMEOUT=30)
- [x] Bitácora de tests — `logs/test-results.jsonl` con campo `env` (dev/docker), `scripts/test-docker.sh`, `scripts/test-log.sh`
- [x] Limpieza Jira — 10 tickets `[MCP Claude Jira Test]` + subtareas eliminados
