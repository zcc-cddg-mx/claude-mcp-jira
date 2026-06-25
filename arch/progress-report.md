# Reporte de avances — claude-mcp-jira

**Fecha:** 2026-06-25  
**Versión del sistema:** 0.5.0  
**Tests:** 8 + 10 + 19 + 24 + 26 + 32 e2e · 96 unit

---

## Progreso global: ~80% del scope total

| Scope | Progreso |
|---|---|
| Equipo técnico usando MCP (CLI + tools) | ~95% |
| Cualquier usuario Zurich (requiere UI) | ~80% |

---

## Fases completadas

| Fase | Descripción | Tests |
|---|---|---|
| 1 — Prototipo CLI | `cli/main.py` — comando `create` directo | — |
| 2 — Service Layer | FastAPI + sanitización + audit log + timeouts | — |
| 3 — Comandos completos | `update`, `summarize`, `list` + JQL controlado + rate limiter | — |
| 4 — MCP Server | SSE Docker + auth API key + RBAC + rate limit + output normalizado | 10 e2e |
| 4.1 — Ajustes e2e + TICKET_LANG | Campos ZNRX, priority IDs, prompts ES, idioma configurable | — |
| 4.2 — Deuda técnica | JQL injection fix, audit MCP, rate limiter compartido, 52 unit tests | 96 unit |
| 4.3 — Transiciones y Log Work | `POST /transition` + `POST /worklog` | — |
| 4.4 — Mejoras API | comments, assign, priority, labels, clone; Swagger prod off | 24 e2e |
| 4.5 — Link dinámico | `POST /link` + `GET /issue-link-types`; tipos reales de Jira, cache TTL 1h | — |
| 5 — Soporte SAZ | `POST /issues/saz` + MCP `create_saz_request` (lead); `znrx_key` opcional | 8 e2e |
| 7 — Multi-proyecto | `project` opcional en create/search; SQLite + auto-discovery lazy; `GET /projects` | 19 e2e |
| 8a — PAT dinámico | `X-Jira-Token` header opcional; `ContextVar` + `JiraAuthMiddleware`; `pat_source` en audit log | — |
| 9.1–9.4 — Git Intelligence | Scanner subprocess, analyzer sesiones+tiempo, mapper regex+NLP, repo registry SQLite | 26 e2e |
| 9.5a — Claude humanizer | Ajuste semántico de estimaciones git con Claude (debugging, complejidad, trabajo nocturno) | — |
| 10 — Workflow Orchestrator | `workflow_store.py` + `routes/workflows.py` + 2 MCP tools; 6-step polling engine | 32 e2e |
| 11 — Integración code-agent-mcp | `code_agent_client.py` + 4 MCP tools; delega git ops y Azure PR al agente externo | 32 schema |
| Deuda H1-H9 | test-actions.sh, auto-link check, rate limit GETs, schemas labels, validaciones | — |

---

## Arquitectura implementada

```
[CLI (Typer)]    ──HTTP──►
                           [Service Layer (FastAPI :18000)]
[MCP Server SSE] ──HTTP──►   ├─ POST /issues                → Jira REST API v2
  15 tools MCP              ├─ GET  /issues/{key}/summary   → Claude (LiteLLM proxy)
                            ├─ POST /workflows/*             → SQLite workflow_executions
                            ├─ POST /git/sync               → Scanner subprocess
                            └─ POST /azure/*, POST /run     → code-agent-mcp (:5001)
                                                                 └─ Azure DevOps PRs
```

**BD SQLite `projects.db` — 3 tablas:**
- `projects` — config por proyecto Jira (seed: ZNRX/AIPROJECTS/SCRX; auto-discovery: SAZ/ARQX)
- `git_repos` — registro de repos locales con alias, origin, is_default
- `workflow_executions` — ejecuciones con steps_json, result_json, status

---

## MCP tools activos (15 total)

| Grupo | Tools | Rol mínimo |
|---|---|---|
| Jira core (9) | create, update, get, search, add_comment, link, assign, set_priority, create_saz | dev / lead |
| Git (3) | sync_git_worklogs, register_git_repo, list_git_repos | dev |
| Azure / code-agent (4) | run_code_agent, get_code_agent_status, create_azure_pull_request, get_pull_request_status | dev / lead |
| Workflow (2) | run_create_feature_pr_workflow, get_workflow_status | dev / lead |

---

## Workflow CreateFeaturePR — flujo completo

```
run_create_feature_pr_workflow(issue_key, repo, repo_path, commit_message)
  → preview       detecta base_branch + files (dry-run, sin side effects)
  → run_agent     encola tarea git en code-agent-mcp → task_id
  → wait_agent    polling /status/{task_id} hasta done  (max 5 min, 60×5s)
  → create_pr     POST /azure/prepare-and-pr (idempotente)  → pr_id, pr_url
  → wait_ci       polling /azure/pull-requests/{pr_id}      (max 30 min, 120×15s)
  → update_jira   añade comentario con link PR en el ticket Jira
  → {execution_id, branch, pr_id, pr_url, build_status, status: "completed"}
```

Estado persistido en SQLite en cada paso — `get_workflow_status` permite diagnóstico y retry manual.

---

## Pendientes

| Item | Prioridad | Dependencia |
|---|---|---|
| Tests live Fase 11 (`--live`) | Baja | `code-agent-mcp` corriendo en `:5001` |
| Decisión `JIRA_ALLOWED_PROJECTS` vaciar o no | Administrativo | Equipo |
| Fase 6 — Observabilidad (Prometheus + OTel) | Media | Volumen de uso justificado |
| Fase 8 — UI (Streamlit MVP → Next.js) | Alta (si hay adopción) | Demanda no-técnica validada |
| Fase 9.5b — Learning layer + multiplier factors | Media | Fase 8 (UI) |

---

## Desglose por peso estimado

| Categoría | Peso | Estado |
|---|---|---|
| Core Jira NL (Fases 1–5, 7, 8a) | 35% | ✅ Completo |
| Seguridad + deuda técnica | 10% | ✅ Completo |
| Git Intelligence (9.1–9.4, 9.5a) | 15% | ✅ Completo |
| Workflow Orchestrator (Fase 10) | 10% | ✅ Completo |
| code-agent-mcp (Fase 11) | 10% | ✅ Completo (~85% sin tests live) |
| Observabilidad (Fase 6) | 5% | ⏳ 0% — condicional |
| UI (Fase 8) | 10% | ⏳ 0% — condicional |
| Learning layer (Fase 9.5b) | 5% | ⏳ 0% — bloqueado por UI |

**Total: ~80% del scope planificado completado.**
