# Evaluación externa — Estado del sistema (2026-06-25)

**Contexto para el evaluador:**
Sistema de automatización de desarrollo construido sobre la red corporativa Zurich Insurance Ecuador.
Sin dependencias de servicios cloud externos (sin Atlassian MCP, sin N8N, sin Zapier).
Solicito una evaluación honesta de: madurez del sistema, riesgos, y próximos pasos recomendados.

---

## 1. Qué se ha construido

### Arquitectura en capas

```
Claude Code (IDE / CLI)
    ↓  SSE / stdio
claude-mcp-jira  [19 MCP tools]
    ├── Service Layer (FastAPI :18000)
    │     ├── LiteLLM proxy interno → Claude API
    │     └── Jira REST API v2 (jira.zurich.com — Server/DC, PAT Bearer)
    └── code-agent-mcp (Flask :5001)
          ├── Git (subprocess: branch, commit, push, aux branch)
          └── Azure DevOps REST API v7.1
```

**Restricciones de red respetadas:**
- Jira Server/Data Center — sin Jira Cloud
- LiteLLM proxy interno — sin `api.anthropic.com` directo
- Certificados corporativos Zurich en todas las llamadas TLS
- `REQUESTS_CA_BUNDLE` configurable por endpoint

---

## 2. Capacidades operativas (19 MCP tools)

### Gestión Jira (9 tools — roles dev/lead)
- Crear, actualizar, obtener resumen, buscar (NL→JQL controlado, MAX 50)
- Añadir comentario, linkear tickets, asignar, cambiar prioridad
- Crear SAZ (Solicitud Release DevOps), con o sin link a ticket ZNRX

### Git Intelligence (3 tools — rol dev)
- Registrar repos locales (alias → path + proyecto Jira)
- Escanear commits por autor/período → detectar sesiones de trabajo → worklogs en Jira
- Claude humanizer: ajuste semántico de estimaciones (debugging, alta complejidad, trabajo nocturno)

### Azure DevOps / PR (4 tools — roles dev/lead)
- Crear PR aux idempotente (`prepare-and-pr`: ensure aux branch → find-or-create PR)
- Consultar estado PR + build CI
- Encolar tarea git asíncrona (branch + commit + push + aux branch → 202 + polling)
- Consultar estado tarea git (steps: create_branch / commit_push / create_aux_branch)

### Deployment SAZ workflow (3 tools — rol lead)
- `create_deployment_saz_workflow` — workflow sincrónico: resolve repo → PR Azure → SAZ Jira en un paso
- `update_pull_request_status` — cambiar estado PR: abandoned / completed / active
- `set_repo_branch_map` — configurar mapping environment→branch por repo

### Workflow Orchestrator (2 tools — roles dev/lead)
- `run_create_feature_pr_workflow` — 6 pasos orquestados: preview → commit → push → PR → CI → Jira comment
- `get_workflow_status` — consultar progreso de ejecución

---

## 3. Seguridad implementada

| Capa | Mecanismo |
|---|---|
| Sanitización | Elimina tokens, IPs RFC1918, hostnames internos, stack traces antes de enviar a Claude |
| Audit log | JSON-lines con `request_id` UUID; rotación 10 MB × 5 backups |
| JQL seguro | Claude → struct → builder controlado; `_jql_escape` en todos los campos |
| Rate limiting | 30 req/60s por usuario (service layer) + 10 calls/60s por API key (MCP) |
| RBAC | Roles dev / lead / system por API key; principio de menor privilegio |
| Auth MCP | API key + IP allowlist (CIDRs corporativos) |
| Auth code-agent | `X-Agent-Token` separado del `JIRA_PAT` |
| Pre-validación | Rechaza inputs vacíos o >2000 chars antes de llamar al backend |
| Output normalizado | LLM recibe solo `{key, status}` o `{key, summary}` — sin datos internos |
| Repo allowlist | code-agent-mcp rechaza 403 repos no registrados |

---

## 4. Cobertura de tests

| Suite | Tests | Qué cubre |
|---|---|---|
| `test-dev.sh` | 8 e2e | CLI → FastAPI → Jira (create, update, summarize, search, seguridad) |
| `test-mcp.sh` | 10 e2e | MCP tools vía service_client + RBAC + pre-validación |
| `test-multi.sh` | 19 e2e | Multi-proyecto: ZNRX / AIPROJECTS / SAZ + auto-discovery |
| `test-actions.sh` | 24 e2e | comments, assign, priority, labels, worklog, transition, clone, link, SAZ |
| `test-git.sh` | 26 e2e | Git registry CRUD + sync dry_run |
| `test-code-agent.sh` | 49 schema+live | Fases 10/11/12: tools, dispatch, RBAC, funciones, live health + PR status |
| `pytest tests/` | 96 unit | sanitizer, jql_builder, auth, rbac, git_analyzer, git_mapper, jira_pat_routing |
| **Total** | **232** | |

Todos los tests pasaron en el run de hoy (2026-06-25). Flujos reales validados:
- PRs #2574 (DEVELOPER) y #2575 (TEST) creados en Azure DevOps
- SAZ-7441 y SAZ-7442 creados en Jira para despliegue real (en manos del equipo DevOps)

---

## 5. Lo que NO está implementado (decisiones conscientes)

| Pendiente | Decisión |
|---|---|
| Fase 6 — Observabilidad (Prometheus, OpenTelemetry) | Sin fecha — activar cuando el volumen lo justifique |
| Fase 8 — UI (Streamlit / Next.js) | Condicional — requiere validar adopción no-técnica |
| Fase 9.5b — Learning layer (multiplier factors por usuario) | Bloqueada por UI |
| 16 endpoints code-agent no expuestos como MCP tools | Bajo demanda — los 19 tools actuales cubren los flujos operativos |

---

## 6. Preguntas abiertas para la evaluación

1. **Madurez:** ¿el sistema está en condiciones de adopción por parte de otros desarrolladores del equipo? ¿qué falta?
2. **UI:** ¿tiene sentido invertir en una UI ahora, o el valor real está en el uso desde Claude Code?
3. **Riesgos:** ¿hay riesgos arquitecturales no resueltos en la capa de seguridad, escalabilidad o mantenibilidad?
4. **Siguiente fase:** dado el estado actual, ¿cuál debería ser la siguiente prioridad?
5. **code-agent-mcp:** ¿la separación de responsabilidades entre `claude-mcp-jira` y `code-agent-mcp` es correcta? ¿hay algo que debería moverse?

---

## 7. Documentación disponible

| Documento | Ruta |
|---|---|
| Arquitectura general | `arch/design/architecture-overview.md` |
| Plan de implementación (todas las fases) | `arch/design/implementation-plan.md` |
| Contrato completo code-agent-mcp (23 endpoints) | `arch/code-agent/integration-plan.md` |
| Workflow Orchestrator | `arch/workflows/workflow-orchestrator.md` |
| Informe técnico MCP | `arch/reports/mcp-technical-report.md` |
| Base de datos SQLite | `arch/bd/README.md` |
| Evaluaciones anteriores | `arch/evaluations/` |
