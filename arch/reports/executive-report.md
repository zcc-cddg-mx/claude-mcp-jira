# Reporte Ejecutivo: claude-mcp-jira
# Agente de Automatización de Desarrollo — Zurich Insurance Ecuador

**Fecha**: Agosto 2026  
**Equipo**: Desarrollo Digital — Zurich Insurance Ecuador  
**Contacto**: carlos.duarte2@mx.zurich.com

---

## ¿Qué es?

`claude-mcp-jira` es una **plataforma de automatización del ciclo de desarrollo** construida sobre la red corporativa Zurich. Integra Jira, Git y Azure DevOps en un flujo único controlado por lenguaje natural, eliminando tareas manuales repetitivas del equipo de desarrollo.

Opera como un **servicio siempre disponible** (systemd, reinicio automático con WSL) accesible desde tres superficies:

- **Claude Code** — herramientas MCP en el IDE, invocadas en lenguaje natural
- **CLI `da`** — script interactivo para flujos frecuentes sin abrir el IDE
- **REST API** — integración directa desde scripts o pipelines CI

---

## Problema que resuelve

| Tarea | Antes | Ahora |
|---|---|---|
| Crear y actualizar tickets Jira | Formulario web manual | Texto libre desde IDE o CLI: _"crea bug en ZNRX, prioridad alta, login en producción"_ |
| Solicitar despliegue (SAZ) | Ticket SAZ manual en Jira | Un comando: repo + rama + ambiente → PR Azure + SAZ creados automáticamente |
| Registrar horas trabajadas | Entrada manual (frecuentemente no hecha) | Automático desde historial de commits: detecta sesiones, infiere ticket desde la rama, registra en Jira |
| Coordinar PR en Azure DevOps | Flujo manual en portal Azure | Orquestado desde Claude Code: commit → rama → PR → esperar CI → comentar en Jira |

---

## Estado actual (agosto 2026)

- **20 herramientas MCP** operativas: Jira · Git Intelligence · Azure DevOps · Workflow Orchestrator
- **240 tests** automatizados — end-to-end validado con PRs y SAZs reales en producción
- **100% red interna Zurich** — sin dependencias a servicios cloud externos
- **Servicio systemd** — arranca automáticamente con WSL, se reinicia solo si cae
- **CLI `developer-assistant`** — 9 comandos; auto-detecta repo y rama desde git; historial local

Proyectos Jira activos: ZNRX · AIPROJECTS · SAZ · SCRX · auto-discovery para cualquier otro proyecto.

---

## Capacidades diferenciales

### Git Intelligence — worklogs automáticos

El sistema analiza el historial de commits de un repositorio y genera worklogs en Jira de forma automática:

1. **Detecta sesiones de trabajo** a partir de los gaps temporales entre commits
2. **Infiere el ticket Jira** desde el nombre de la rama (`feature/ZNRX-68488_descripcion`) o el mensaje de commit
3. **Estima el tiempo** por tipo de cambio y complejidad
4. **Claude humaniza la estimación** — ajusta por contexto: debugging (+50%), trabajo nocturno (+15min), alta complejidad (+30%)
5. **Registra el worklog** en Jira con un solo comando, en modo previsualización por defecto

```
da worklog
→ ZNRX-68488   4.5h   "Implementación deducibles vidrios — frontend"
→ ZNRX-68580   2.0h   "Pruebas funcionales editPlan"
TOTAL: 6.5h  — ¿confirmar? [S/n]
```

### Deployment SAZ workflow — despliegue en un comando

```
da deploy
Repo   : ov-arizona-backend-ecuador
Branch : feature/ZNRX-67108_vidrios
Target : test
Ticket : ZNRX-67108

→ PR #2835 creado en Azure DevOps
→ SAZ-7591 creado y vinculado a ZNRX-67108
```

---

## Evaluación del ecosistema global Zurich (junio 2026)

A sugerencia de Jose Luis Sanchez Ros (AI Business Solutions Lead, Zurich España), se evaluó `et-ai-mcp-jira` (`skills.ai.zurich.com`) como posible base o reemplazo.

| Capacidad | MCP Global Zurich | claude-mcp-jira |
|---|---|---|
| CRUD básico Jira | ✅ | ✅ |
| Registrar horas (worklog) | ❌ | ✅ |
| Asignar, prioridad, labels, link | ❌ | ✅ |
| Solicitud de despliegue SAZ | ❌ | ✅ |
| Azure DevOps — tenant Ecuador | ❌ | ✅ |
| Git Intelligence | ❌ | ✅ |
| RBAC + audit log corporativo | ❌ | ✅ |

**Decisión:** mantener `claude-mcp-jira` como sistema principal. El MCP global cubre ~40% de las operaciones cotidianas; los casos de uso diferenciadores del equipo Ecuador no están disponibles ni en el roadmap global.

---

## Posicionamiento en el ecosistema Zurich

`claude-mcp-jira` no compite con el MCP global — es un **AGENTE especializado Ecuador** que opera encima del ecosistema Zurich:

```
Zurich Global AI Platform
    └── et-ai-mcp-jira              (CRUD Jira genérico)
    └── et-ai-mcp-devops            (Azure DevOps global)

claude-mcp-jira  ←── AGENTE Ecuador
    ├── Git Intelligence            worklogs automáticos desde commits
    ├── Deployment SAZ workflow     PR Azure + SAZ en un comando
    ├── Azure DevOps ZEC            tenant ZurichInsurance-EC
    ├── Workflow Orchestrator       6 pasos orquestados
    └── CLI developer-assistant     sin IDE, sin curl
```

---

## Próximos pasos

| Iniciativa | Estado |
|---|---|
| Evaluar `et-ai-mcp-devops-work-management` (agente A2A global) | Pendiente — cuando haya tokens de equipo |
| Integración con MCP global | Condicional — si gateway pasa a productivo y añade worklog/link |
| UI web para usuarios no técnicos | Futura — tras validar demanda |

---

## Documentación complementaria

| Documento | Descripción |
|---|---|
| `arch/reports/mcp-technical-report.md` | Arquitectura, 20 tools y seguridad en detalle (v2.2) |
| `docs/onboarding-developer-assistant.md` | Guía de instalación desde cero (5 pasos) |
| `arch/design/systemd-services.md` | Patrón de servicios persistentes |
| `arch/evaluations/` | Análisis estratégico vs MCP global (junio 2026) |
| Ticket referencia | ZNRX-68298 — validación `et-ai-mcp-jira` desde Ecuador |
