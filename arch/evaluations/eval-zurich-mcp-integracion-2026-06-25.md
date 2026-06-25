# Evaluación estratégica — Integración con Zurich Global MCP Skills
# Fecha: 2026-06-25 | Estado: COMPLETA
# Fuentes:
#   - Conversación con Jose Luis Sanchez Ros (AI Business Solutions Lead, Zurich España)
#     → logs/eval-mcp-ai-business-lead.md
#   - Evaluación de Copilot sobre esa conversación
#     → arch/evaluations/eval-mcp-zurich-copilot.md
#   - Validación técnica completa
#     → arch/evaluations/TODO-zurich-mcp-jira-validacion.md
#   - Informe técnico detallado
#     → arch/evaluations/eval-integracion-mcp-global-vs-local-2026-06-25.md

---

## 1. Situación

Jose Luis Sanchez Ros (AI Business Solutions Lead, Zurich España) recomendó explorar las skills globales de Zurich antes de continuar desarrollando:

> "Antes de la UI, mira los MCPs de Jira que tenemos"
> "please antes de hacer un mcp de 0 piensa que tenemos muchos"
> "haz una skill que funcione muy bien y se comporte como quieres"

Jose compartió tokens personales JWT para pruebas y dijo "prueba los 2". La validación técnica se realizó el mismo día.

| Skill | Tipo | Estado evaluación |
|---|---|---|
| `et-ai-mcp-jira` | MCP | ✅ Evaluada completamente |
| `et-ai-mcp-devops-work-management` | A2A Agent | ⏳ Pendiente (no bloqueante) |

---

## 2. Resultados de la validación técnica

### Conectividad y acceso

| Punto | Estado | Detalle |
|---|---|---|
| Gateway alcanzable desde Ecuador | ✅ | HTTP 200; ~700ms; requiere `-k` (firewall TLS) |
| Instancia Jira | ✅ `jira.zurich.com` | Server/DC — nuestra instancia |
| Token de Jose | ✅ válido | Hasta 2026-09-23; personal — solo validación |
| PAT del equipo Ecuador | ✅ funciona | Autenticado como Carlos David Duarte, 82 proyectos |

### Operaciones validadas

| Operación | Resultado |
|---|---|
| `search-issues` (JQL directo) | ✅ |
| `create-issue` | ✅ — requiere `customfield_25832` (Línea de Servicio) explícito |
| `add-comment` | ✅ |
| `get-issue`, `get-issue-history` | ✅ |
| `update-issue` | ✅ |
| `get-transitions` | ✅ |
| **worklog (registrar horas)** | ❌ — no existe tool; intento directo rechazado por Jira |
| link / assign / priority / labels / clone | ❌ — no existen tools |

---

## 3. Comparativa funcional confirmada

| Operación | et-ai-mcp-jira | claude-mcp-jira |
|---|---|---|
| CRUD básico (create/update/get/comment/transitions) | ✅ | ✅ |
| search | ✅ JQL directo | ✅ NL→JQL |
| **worklog** | ❌ | ✅ |
| link / assign / priority / labels / clone | ❌ | ✅ |
| SAZ (solicitud despliegue) | ❌ | ✅ |
| Deployment SAZ workflow | ❌ | ✅ |
| Azure DevOps PR (tenant ZEC) | ❌ | ✅ |
| Git Intelligence (worklogs desde commits) | ❌ | ✅ |
| NL → JQL semántico | ❌ | ✅ |
| RBAC + audit log | ❌ | ✅ |
| Multi-proyecto (ZNRX/SAZ/AIPROJECTS) | ❌ verificado | ✅ |
| Releases / versiones | ✅ | ❌ |

---

## 4. Posicionamiento

La evaluación confirma la tesis de Copilot:

> **No estamos construyendo un MCP. Ya tenemos una plataforma de automatización completa equivalente a un AGENTE Zurich.**

| Zurich global | claude-mcp-jira |
|---|---|
| `et-ai-mcp-jira` (MCP base) | Service Layer + 9 MCP tools Jira |
| `et-ai-mcp-devops-work-management` (Agent) | Workflow Orchestrator + code-agent-mcp |

No se elige entre su MCP o su agente — `claude-mcp-jira` **es el agente especializado Ecuador** que operaría encima de esa capa base.

---

## 5. Decisión: Opción B — mantener sistema actual

**Razones determinantes:**

| Factor | Peso |
|---|---|
| Worklog imposible vía MCP global | Crítico — caso de uso principal de Git Intelligence |
| 6+ gaps en operaciones cotidianas (assign, priority, link, labels, SAZ) | Alto |
| SAZ y Azure DevOps Ecuador no existirán en el MCP global | Crítico |
| Gateway DEV sin SLA — no viable como dependencia productiva | Medio |
| Complejidad de integración (`session_id` + campos requeridos) sin beneficio neto | Medio |

**Componentes que se mantienen locales sin excepción:**

| Componente | Motivo |
|---|---|
| Git Intelligence + worklogs | Imposible vía MCP global |
| Workflow Orchestrator | Lógica SAZ + PAT routing específica Ecuador |
| code-agent-mcp | Tenant Azure DevOps `ZurichInsurance-EC / Oficina-Virtual-ZEC` |
| SAZ workflow | Template específico Ecuador; no existe equivalente global |
| RBAC + audit log | Requisitos corporativos Ecuador |

---

## 6. Condiciones para reevaluar

No se descarta integración futura bajo estas condiciones:

| Condición | Acción |
|---|---|
| `et-ai-mcp-jira` añade worklog y link | Reconsiderar delegación del CRUD básico |
| Gateway productivo estable (sin `-dev`) | Reevaluar como capa base |
| Tokens de equipo disponibles (no personales) | Prerequisito para cualquier integración |
| `et-ai-mcp-devops-work-management` cubre Azure DevOps EC | Evaluar si complementa o sustituye code-agent-mcp |

---

## 7. Evaluaciones relacionadas

| Documento | Descripción |
|---|---|
| `eval-mcp-zurich-copilot.md` | Análisis de Copilot sobre la conversación con Jose |
| `eval-estado-actual-2026-06-25.md` | Snapshot del sistema (19 tools, 232 tests) |
| `TODO-zurich-mcp-jira-validacion.md` | Validación técnica paso a paso con resultados |
| `eval-integracion-mcp-global-vs-local-2026-06-25.md` | Informe técnico detallado con comparativa completa |
| `eval-workflow-copilot.md` | Evaluación Fase 10 (Workflow Orchestrator) |
