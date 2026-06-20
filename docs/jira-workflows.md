# Workflows y transiciones Jira por proyecto

Obtenido de `GET /rest/api/2/project/{key}/statuses` y
`GET /rest/api/2/issue/{key}/transitions`.

Relevante para una futura extensión de `claude-mcp-jira` que soporte cambio de estado
(`transition_jira_issue`). Los IDs de transición son específicos de cada issue/workflow.

---

## ZNRX — Zúrich Gestión de Requerimientos

Workflow complejo con aprobaciones formales. Los tickets top-level (Task, Story) siguen
un flujo de release con múltiples gates de aprobación.

### Statuses por tipo de issue

**Task / Story / Epic:**

| Status | Categoría | Descripción |
|---|---|---|
| To Do | To Do | Estado inicial |
| Sprint Backlog | To Do | En backlog de sprint |
| ANÁLISIS DE NEGOCIO | To Do | Pendiente análisis |
| Under Analysis | In Progress | En análisis |
| APROBAR ALCANCE FD | In Progress | Esperando aprobación de alcance |
| Aprobación de TI | In Progress | Aprobación interna TI |
| Architecture Approval | In Progress | Aprobación de arquitectura |
| In Progress | In Progress | En desarrollo |
| Parar Progreso | To Do | Desarrollo pausado |
| Desplegar a Test | In Progress | Pendiente despliegue a Test |
| Aprobar paso a Test | In Progress | Esperando aprobación para Test |
| In Test | In Progress | En pruebas |
| UAT Testing | In Progress | En pruebas UAT |
| APROBAR PASO A PRODUCCIÓN | In Progress | Aprobación final para producción |
| Release Producción | In Progress | Pendiente release a producción |
| Deploy to Prod | In Progress | Desplegando a producción |
| Aprobación Producción | In Progress | Aprobación post-deploy |
| Done | Done | Completado |
| Cancelled | Done | Cancelado |

**Subtarea Historia:**

| Status | Categoría |
|---|---|
| Open | To Do |
| In Progress | In Progress |
| Done | Done |

**Issue Post Producción:**
Incluye estados adicionales: REABIERTA, APROBAR CHANGE, Release in Prod.

### Transiciones disponibles (desde "To Do")

| id | Transición | Estado destino |
|---|---|---|
| 861 | Cancelar requerimiento | Cancelled |
| 881 | Parar progreso | Parar Progreso |
| 11 | Solicitar análisis negocio | ANÁLISIS DE NEGOCIO |

> Las transiciones disponibles dependen del estado actual del ticket. Los IDs varían.

---

## AIPROJECTS — Business Solutions

Workflow ágil estándar con extensiones para demo y deploy. Mismo workflow para todos los tipos.

### Statuses (todos los tipos)

| Status | Categoría | Descripción |
|---|---|---|
| To Do | To Do | Estado inicial |
| In Progress | In Progress | En desarrollo |
| Validation - QA | In Progress | En validación QA |
| Ready for Demo | In Progress | Listo para demo |
| Deploy | In Progress | En despliegue |
| Monitoring | In Progress | En monitoreo post-deploy |
| Done | Done | Completado |

### Transiciones disponibles

| id | Transición | Estado destino |
|---|---|---|
| 11 | To Do | To Do |
| 21 | In Progress | In Progress |
| 31 | Done | Done |
| 41 | Validation - QA | Validation - QA |
| 51 | Ready for Demo | Ready for Demo |
| 61 | Deploy | Deploy |
| 71 | Monitoring | Monitoring |

> AIPROJECTS tiene los IDs de transición más simples y predecibles (11/21/31/41/51/61/71).
> Son los más fáciles de usar programáticamente.

---

## SAZ — Solicitudes Release Zurich

Workflow de service desk con aprobación y reunión de entendimiento.

### Statuses por tipo de issue

**Support / Nueva Iniciativa:**

| Status | Categoría | Descripción |
|---|---|---|
| Pending | To Do | Solicitud recibida, pendiente de asignación |
| Reunion Entendimiento | In Progress | Reunión de clarificación con el solicitante |
| In Progress | In Progress | En ejecución |
| REABIERTA | In Progress | Reabierta tras cierre (solo Support) |
| Finalizado | Done | Completado |
| Cancelar | Done | Cancelado |

**Incident:**

| Status | Categoría |
|---|---|
| Open | To Do |
| In Progress | In Progress |
| Resolved | Done |
| Reopened | In Progress |
| Closed | Done |

### Transiciones disponibles (desde "Pending")

| id | Transición | Estado destino |
|---|---|---|
| 11 | En Progreso | In Progress |
| 41 | Reunión Entendimiento | Reunion Entendimiento |
| 101 | Cancelar | Cancelar |

---

## SCRX — EC · SCRX · Agile

Workflow complejo con change control, bloqueos y ciclo completo de QA/UAT/producción.

### Statuses (Task, Story, Sub-task)

| Status | Categoría | Descripción |
|---|---|---|
| To Do | To Do | Estado inicial |
| Backlog | In Progress | En backlog activo |
| Backlog Refinement | In Progress | En refinamiento |
| Technical Analysis and Estimation | In Progress | Análisis técnico |
| Architecture Approval | In Progress | Aprobación arquitectura |
| In Progress | In Progress | En desarrollo |
| Blocked | To Do | Bloqueado |
| Blocked by Bug | To Do | Bloqueado por bug |
| Deployed & Ready to Test | In Progress | Desplegado, esperando QA |
| Ready for QA | In Progress | Listo para QA |
| Ready for UAT | In Progress | Listo para UAT |
| Approval Required | In Progress | Requiere aprobación |
| CAB REVIEW | In Progress | Revisión CAB (Change Advisory Board) |
| CR | In Progress | Change Request en proceso |
| PROD Deployment | In Progress | Desplegando a producción |
| Hypercare/In Production | In Progress | En producción bajo monitoreo |
| En BAU | Done | Entregado a operación estándar |
| Done | Done | Completado |
| Canceled | Done | Cancelado |

**Bug (SCRX):**

| Status | Categoría |
|---|---|
| To Do | To Do |
| In Analysis | In Progress |
| In Progress | In Progress |
| In Test | In Progress |
| Blocked | To Do |
| Closed | Done |

### Transiciones disponibles (desde estado actual)

| id | Transición | Estado destino |
|---|---|---|
| 271 | Refinement | Backlog Refinement |
| 471 | Canceled | Canceled |
| 481 | CR | CR |
| 571 | Blocked by Bug | Blocked by Bug |
| 581 | Backlog | Backlog |

---

## Uso desde la API

Para hacer una transición programáticamente:

```bash
POST /rest/api/2/issue/{key}/transitions
{
  "transition": { "id": "21" }
}
```

Con campos adicionales (ej. comentario al cerrar):

```bash
POST /rest/api/2/issue/{key}/transitions
{
  "transition": { "id": "31" },
  "update": {
    "comment": [{ "add": { "body": "Completado tras validación en UAT" } }]
  }
}
```

> Los IDs de transición son relativos al estado actual del ticket —
> consultar `GET /rest/api/2/issue/{key}/transitions` antes de ejecutar.

---

## Resumen comparativo

| Proyecto | Complejidad | Estados únicos | Requiere aprobaciones |
|---|---|---|---|
| ZNRX | Alta | 19 (Task) | Sí — múltiples gates formales |
| AIPROJECTS | Baja | 7 | No |
| SAZ | Media | 6 (Support) | No (Reunión Entendimiento es opcional) |
| SCRX | Alta | 19 (Task) | Sí — CAB Review, Architecture Approval |
