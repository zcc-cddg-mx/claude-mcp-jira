# Reporte Ejecutivo: claude-mcp-jira
# Agente de Automatización de Desarrollo — Zurich Insurance Ecuador

**Fecha**: Junio 2026  
**Equipo**: Desarrollo Digital — Zurich Insurance Ecuador  
**Contacto**: carlos.duarte2@mx.zurich.com

---

## ¿Qué es?

`claude-mcp-jira` es un **agente de IA integrado al flujo de desarrollo** del equipo Ecuador que automatiza tareas repetitivas de gestión de proyectos: creación y actualización de tickets Jira, solicitudes de despliegue (SAZ), registro de horas trabajadas y gestión de Pull Requests en Azure DevOps, todo desde el IDE (Claude Code) o la línea de comandos, usando lenguaje natural.

---

## Problema que resuelve

El equipo de desarrollo dedicaba tiempo manual a:

| Tarea | Antes | Ahora |
|---|---|---|
| Crear y actualizar tickets Jira | Formulario web manual | Texto libre desde el IDE: _"crea un bug en ZNRX, prioridad alta, login en producción"_ |
| Solicitar despliegue al equipo DevOps | Ticket SAZ manual en Jira | Un comando: repo + rama + ambiente → PR Azure + SAZ creados automáticamente |
| Registrar horas trabajadas | Entrada manual en Jira (frecuentemente no hecha) | Automático desde el historial de commits de Git |
| Coordinar PR en Azure DevOps | Flujo manual en portal Azure | Orquestado desde Claude Code: commit → rama → PR → esperar CI → comentar en Jira |

---

## Estado actual

- **19 herramientas MCP** operativas (Jira, Git, Azure DevOps, Workflows)
- **232 tests** automatizados — end-to-end validado con PRs y SAZs reales
- **100% red interna Zurich** — sin dependencias a servicios cloud externos
- Funcionando en producción con los proyectos ZNRX, AIPROJECTS, SAZ, SCRX

---

## Evaluación del ecosistema global Zurich (junio 2026)

A sugerencia de Jose Luis Sanchez Ros (AI Business Solutions Lead, Zurich España), se evaluó el MCP global de Zurich (`et-ai-mcp-jira` en `skills.ai.zurich.com`) como posible base o reemplazo.

### Resultado de la evaluación

| Capacidad | MCP Global Zurich | claude-mcp-jira |
|---|---|---|
| CRUD básico Jira (crear, actualizar, buscar, comentar) | ✅ | ✅ |
| Registrar horas trabajadas (worklog) | ❌ No disponible | ✅ |
| Asignar, cambiar prioridad, gestionar labels | ❌ No disponible | ✅ |
| Solicitud de despliegue (SAZ) | ❌ No disponible | ✅ |
| Azure DevOps — tenant Ecuador | ❌ No disponible | ✅ |
| Git Intelligence (worklogs desde commits) | ❌ No disponible | ✅ |
| RBAC + audit log corporativo | ❌ No disponible | ✅ |

El MCP global cubre el CRUD básico (~40% de las operaciones cotidianas). Los casos de uso diferenciadores del equipo Ecuador — worklog automático, despliegues SAZ, Azure DevOps del tenant ecuatoriano — no están disponibles ni están en el roadmap del servicio global.

### Decisión

**Mantener `claude-mcp-jira` como sistema principal.** El MCP global es un punto de referencia valioso y una futura oportunidad de integración, pero no reemplaza las capacidades especializadas desarrolladas para Ecuador.

---

## Posicionamiento en el ecosistema Zurich

`claude-mcp-jira` no compite con el MCP global — es complementario:

```
Zurich Global AI Platform
    └── et-ai-mcp-jira  (CRUD Jira genérico)
    └── et-ai-mcp-devops-work-management  (Azure DevOps global)

claude-mcp-jira  ←── AGENTE especializado Ecuador
    ├── Worklogs automáticos desde Git
    ├── Solicitudes SAZ con plantillas Ecuador
    ├── Azure DevOps tenant ZEC (ZurichInsurance-EC / Oficina-Virtual-ZEC)
    └── Workflow orquestado: commit → PR → CI → Jira
```

En términos del modelo AGENTE que maneja Zurich Global AI, `claude-mcp-jira` equivale a un **AGENTE de dominio** — no un MCP plano, sino un orquestador especializado con inteligencia de negocio para el contexto Ecuador.

---

## Próximos pasos

| Iniciativa | Estado | Descripción |
|---|---|---|
| Evaluar `et-ai-mcp-devops-work-management` | Pendiente | Agente A2A de DevOps global; evaluar cuando haya tokens de equipo y gateway productivo |
| Releases / versiones Jira | Futura | `et-ai-mcp-jira` tiene herramientas de releases que no tenemos; candidato para integración |
| UI web | Futura | Panel para usuarios no técnicos (project managers, analistas); tras validar demanda |
| Integración con MCP global | Condicional | Si `et-ai-mcp-jira` añade worklog y link, y el gateway pasa a productivo sin `-dev` |

---

## Documentación complementaria

| Documento | Descripción |
|---|---|
| `arch/reports/mcp-technical-report.md` | Arquitectura, herramientas y seguridad en detalle |
| `arch/evaluations/eval-integracion-mcp-global-vs-local-2026-06-25.md` | Informe técnico de integración vs MCP global |
| `arch/evaluations/eval-zurich-mcp-integracion-2026-06-25.md` | Análisis estratégico y decisión documentada |
| Ticket referencia evaluación | ZNRX-68298 — `[MCP Claude Jira Test] Validación et-ai-mcp-jira desde Ecuador` |
