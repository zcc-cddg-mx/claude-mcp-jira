# Campos Jira por proyecto — jira.zurich.com

Obtenido de `GET /rest/api/2/issue/{key}/editmeta`. Documenta campos requeridos, opcionales
relevantes y valores permitidos por proyecto.

> `createmeta` (`/rest/api/2/issue/createmeta`) no está disponible con el PAT actual.
> Los datos de campos requeridos en creación se derivan de errores API reales y de `editmeta`.

---

## ZNRX — Zúrich Gestión de Requerimientos

### Campos requeridos en creación

| Campo | API field | Valor requerido |
|---|---|---|
| Project | `project.key` | `ZNRX` |
| Summary | `summary` | Texto libre (máx. 100 chars) |
| Issue Type | `issuetype.name` | Ver tabla de tipos |
| Línea de Servicio | `customfield_25832.id` | `44461` (BAU) — ver valores |
| Reporter | `reporter` | Automático (usuario del PAT) |

### Tipos de issue y restricciones API

| Tipo | Disponible vía API | Notas |
|---|---|---|
| Task | ✓ | Tipo principal — usar también para bugs y mejoras |
| Story | ✓ | |
| Epic | ✓ | |
| Subtarea Historia | ✓ | Subtask — requiere `parent.key`; NO acepta `customfield_25832` ni `priority` |
| Bug | ✗ | Validaciones de workflow bloquean creación vía API → usar Task |
| RPA | ✓ (no verificado) | |
| Data BI & Reporting | ✓ (no verificado) | |
| Issue Pre/Post Producción | ✓ (no verificado) | |

> **Subtasks screen**: Los issues de tipo `Subtarea Historia` usan un screen diferente al de los
> issues de nivel superior. **`customfield_25832` (Línea de Servicio) y `priority` NO están
> disponibles en ese screen** — enviarlos resulta en 400 "Field cannot be set".

### customfield_25832 — Línea de Servicio (obligatorio)

| id | Valor |
|---|---|
| **44461** | **BAU** ← valor estándar para desarrollo |
| 44462 | DT |
| 44463 | PROCESOS |
| 44464 | DC&AI |
| 44465 | BI |
| 44466 | IT_SERV |
| 58822 | RPA/BPM |
| 58823 | OV |

### Priority (solo por ID)

ZNRX **no acepta priority por nombre** — enviar siempre `{"id": "N"}`:

| id | Nombre |
|---|---|
| 1 | Highest |
| 2 | High |
| 4 | Low |

Cualquier otro valor (Medium, Lowest, etc.) es rechazado con 400.

### Campos opcionales relevantes

| Campo | API field | Valores / notas |
|---|---|---|
| Criticidad | `customfield_25918.id` | Alto (44773), Medio (44774), Bajo (44775) |
| Task Type | `customfield_16063.id` | Cambio de Data, Error, Operativo, Permisos, Reporte, Migración BDD, Cambio Jira |
| Tipo Iniciativa | `customfield_25924.id` | Requerimiento, Proyecto, Genéricas, Gestión & Soporte, IA / Automatización |
| Departamento | `customfield_25702` | Texto libre |
| Epic Link | `customfield_10006` | Key del epic padre |
| Assignee | `assignee.name` | Username Jira |
| Due Date | `duedate` | Formato `YYYY-MM-DD` |

---

## AIPROJECTS — Business Solutions

### Campos requeridos en creación

| Campo | API field | Notas |
|---|---|---|
| Summary | `summary` | Texto libre |
| Issue Type | `issuetype.name` | Task, Story, Bug, Epic, Initiative |
| Epic Name | `customfield_10005` | Obligatorio solo si `issuetype = Epic` |

### Priority (acepta nombre y valores extendidos)

A diferencia de ZNRX, AIPROJECTS acepta el rango completo de prioridades por nombre:
`Highest`, `High`, `Medium`, `Low`, `Lowest`, `Blocker`, `Minor`, `Critical`.

### Campos opcionales relevantes

| Campo | API field | Notas |
|---|---|---|
| Components | `components` | Versiones: Accesos Claude (y otras) |
| Fix Version | `fixVersions` | Accesos Claude, y otras |
| Sprint | `customfield_10004` | ID del sprint activo |
| Epic Link | `customfield_10006` | Key del epic padre |
| Assignee | `assignee.name` | Username Jira |

---

## SAZ — Solicitudes Release Zurich

### Campos requeridos en creación

| Campo | API field | Notas |
|---|---|---|
| Reporter | `reporter` | Automático (usuario del PAT) |

### Tipos de issue

| Tipo | Uso |
|---|---|
| Support | Solicitudes operativas estándar (despliegues, reinicios, accesos) |
| Incident | Incidentes urgentes en producción |
| Nueva Iniciativa | Solicitudes de nueva infraestructura o iniciativa |

### Campos opcionales relevantes

| Campo | API field | Valores |
|---|---|---|
| Tipo de Solicitud | `customfield_25896` | Release Management, Arquitectura |
| Description | `description` | Texto plano — describir la solicitud con detalle |
| Assignee | `assignee.name` | Username del equipo Release |
| Team Name | `customfield_14003` | Nombre del equipo solicitante |

> **SAZ es el proyecto con menos restricciones de campos** — solo `reporter` es obligatorio.
> La descripción clara es el campo más importante para el equipo de Release.

---

## SCRX — EC · SCRX · Agile

### Campos requeridos en creación

| Campo | API field | Notas |
|---|---|---|
| Summary | `summary` | Texto libre |

### Priority (acepta nombre y valores extendidos)

Igual que AIPROJECTS: `Highest`, `High`, `Medium`, `Low`, `Lowest`, `Blocker`, `Minor`, `Critical`.

### Campos opcionales relevantes

| Campo | API field | Notas |
|---|---|---|
| Components | `components` | Lista extensa — ver `docs/jira-projects.md` para leads por componente |
| Fix Version | `fixVersions` | Sprint13, Sprint14, versiones por fecha (24.11.0, etc.) |
| Canal | `customfield_37900` | Canal digital afectado |
| Producto | `customfield_37901` | Producto afectado |
| Module | `customfield_37603` | Módulo del sistema |
| Functionality | `customfield_37604` | Funcionalidad específica |
| Environment | `environment` | Ambiente (TEST, UAT, PROD) |

> SCRX incluye campos específicos para testing con Xray (`customfield_12616`–`12625`).
> No son relevantes para uso con `claude-mcp-jira`.

---

## Resumen — restricciones por proyecto

| Proyecto | Campo obligatorio extra | Priority format | Bug via API |
|---|---|---|---|
| ZNRX | `customfield_25832` (Línea de Servicio = BAU) | Solo ID (1/2/4) | ✗ → usar Task |
| AIPROJECTS | `customfield_10005` (Epic Name) si Epic | Nombre completo | ✓ |
| SAZ | ninguno extra | Nombre completo | n/a (Support/Incident) |
| SCRX | ninguno extra | Nombre completo | ✓ |
