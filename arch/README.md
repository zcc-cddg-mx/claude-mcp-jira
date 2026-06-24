# Documentación de Arquitectura — claude-mcp-jira

Estado: Fases 1–5, 7, 8a, 9.1–9.4, 9.5a, 11 completas. Fase 10 (Workflow Orchestrator) pendiente.

## Estructura

```
arch/
├── design/                     # Diseño vivo del sistema
│   ├── architecture-overview.md    Arquitectura general (capas, flujos, RBAC, estructura)
│   └── implementation-plan.md      Fases completadas + pendientes; decisiones y criterios de éxito
│
├── workflows/                  # Diseño del Workflow Orchestrator (Fase 10)
│   └── workflow-orchestrator.md    Especificación completa: SQLite, endpoints, 6 steps, 2 MCP tools
│
├── bd/                         # Schema de la base de datos SQLite
│   └── README.md                   Tablas projects, git_repos, workflow_executions; columnas y repos actuales
│
├── code-agent/                 # Integración con code-agent-mcp (Fase 11)
│   └── integration-plan.md         API surface (22 endpoints), módulos, endpoints no expuestos como MCP tools
│
├── fix/                        # Resolución de deuda técnica específica
│   ├── fix-debt-audit.md           H1–H9 resueltos (2026-06-22)
│   └── fix-multi-project-gaps.md   Lagunas multi-proyecto L1–L3 (2026-06-22)
│
├── evaluations/                # Evaluaciones externas (ver detalle abajo)
│
└── reports/                    # Informes técnicos de referencia
    └── mcp-technical-report.md     Model Context Protocol — referencia técnica
```

---

## Evaluaciones externas (`evaluations/`)

### Referencia activa — fases pendientes

| Archivo | Fase | Tema |
|---|---|---|
| `eval-workflow-copilot.md` | **10** | Diagnóstico del workflow engine oculto; recomendación de formalizar Orchestrator |
| `eval-orchestrator-copilot.md` | **10** | Diseño del Orchestrator; evolución hacia Internal Developer Copilot Platform |
| `eval-ui-copilot.md` | **8** | Plan de UI — stack, auth JWT, alcance MVP vs. avanzado |
| `eval-human-sensity-copilot.md` | **9.5b** | Human-aware estimation layer; multiplier factors + learning layer |

### Históricas — fases ya cerradas

| Archivo | Fase | Tema |
|---|---|---|
| `eval-workflow-copilot.md` → ya en activas | — | — |
| `eval-git-copilot.md` | 9 | Git Intelligence — scanner, mapper, estimación de tiempo |
| `eval-multiproject-copilot.md` | 7 | Multi-proyecto + SQLite auto-discovery |
| `eval-apis-copilot.md` | 4.4 | Diseño de endpoints explícitos (commands vs. CRUD) |
| `eval-link-copilot.md` | 4.5 | Link types dinámicos — tipos reales de Jira, cache TTL |
| `eval-swagger-copilot.md` | 4.4 | Swagger en producción — deshabilitado en `APP_ENV=prod` |
| `eval-arquitecture-copilot.md` | 4 | Validación de arquitectura en capas (pre-Fase 5) |
| `eval-plan-copilot.md` | 2–3 | Review técnico del plan inicial |
| `eval-plan-copilot-2.md` | 4–5 | Segunda ronda — mejoras y Fase 5 SAZ |
| `eval-copilot.md` | 1 | Decisión inicial: MCP oficial Atlassian descartado |
| `eval-gemini.md` | 1 | Plan inicial de Gemini (referencia comparativa) |

---

## Documentos clave por caso de uso

| Necesito saber… | Documento |
|---|---|
| Cómo funciona el sistema completo | `design/architecture-overview.md` |
| Estado de cada fase y qué viene | `design/implementation-plan.md` |
| Qué va a hacer la Fase 10 | `workflows/workflow-orchestrator.md` |
| Qué hace code-agent-mcp y cómo se integra | `code-agent/integration-plan.md` |
| Tablas SQLite y sus columnas | `bd/README.md` |
| Proyectos Jira, campos, permisos | `../docs/jira-projects.md`, `../docs/jira-fields.md`, `../docs/jira-roles.md` |
| Tools MCP, RBAC, variables de entorno | `../jira_mcp/README.md` |
