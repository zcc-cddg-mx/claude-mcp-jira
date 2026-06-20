# Proyectos Jira — Zurich

Proyectos configurados para uso con `claude-mcp-jira`. Cada proyecto tiene restricciones
distintas de campos, tipos de issue y idioma recomendado.

---

## ZNRX — Zúrich Gestión de Requerimientos

| Campo | Valor |
|---|---|
| URL | https://jira.zurich.com/projects/ZNRX |
| Tipo | Software (Kanban) |
| `JIRA_PROJECT_KEY` | `ZNRX` |
| `TICKET_LANG` | `es` |

**Propósito:** gestión de requerimientos y desarrollo de software del equipo de tecnología Zurich.
Es el proyecto principal de desarrollo — aquí viven historias, tareas, bugs y épicas del sprint.

**Tipos de issue disponibles:** Task, Story, Epic, Bug, RPA, Data BI & Reporting,
Issue Pre/Post Producción, Casos de Prueba, Test (y subtipos de test).

**Restricciones conocidas (API):**
- `customfield_25832` ("Línea de Servicio") **obligatorio** en todos los issues top-level → valor `BAU` (id `44461`)
- Priority solo acepta 3 valores por ID: `Highest` (1), `High` (2), `Low` (4)
- `Bug` issuetype bloqueado por validaciones de workflow → se crea como `Task`
- Issues top-level generan automáticamente 6 subtareas de workflow (estimación, desarrollo, QA, despliegue)

---

## AIPROJECTS — Business Solutions

| Campo | Valor |
|---|---|
| URL | https://jira.zurich.com/projects/AIPROJECTS |
| Tipo | Software |
| `JIRA_PROJECT_KEY` | `AIPROJECTS` |
| `TICKET_LANG` | `en` |
| Lead | Adriana Salazar Venegas |

**Propósito:** iniciativas de IA y automatización de procesos de negocio (Business Solutions).
Proyectos de procesamiento de lenguaje natural, automatización con IA, y soluciones digitales
para áreas de negocio de Zurich LATAM.

**Tipos de issue disponibles:** Task, Story, Bug, Epic, Initiative, Sub-task.

**Notas:** proyecto de alcance internacional/regional — idioma preferido inglés.
Issues de más alto nivel (Initiative) agrupan múltiples Epics cross-equipo.

---

## SAZ — Solicitudes Release Zurich

| Campo | Valor |
|---|---|
| URL | https://jira.zurich.com/projects/SAZ |
| Tipo | Business |
| `JIRA_PROJECT_KEY` | `SAZ` |
| `TICKET_LANG` | `es` |

**Propósito:** solicitudes operativas al equipo de DevOps/Release — reinicios de servicio,
despliegues a ambientes (TEST, UAT, PROD), actualizaciones de imágenes Docker, accesos,
y pases entre ambientes.

**Tipos de issue disponibles:** Support, Incident, Nueva Iniciativa, Sub-task.

**Patrón de uso:** los tickets SAZ son autónomos pero se vinculan opcionalmente a un issue
ZNRX como justificación. Enlace vía `POST /rest/api/2/issueLink`.

**Ejemplo de solicitudes:**
- Despliegue de backend a ambiente TEST
- Actualización de imagen Docker (ej. NGINX 1.28 → 1.31)
- Paso de issue a ambiente siguiente (ej. `Paso a ambiente test SCRX-XXXXX`)

> **Pendiente (Fase 5):** inspeccionar `GET /rest/api/2/issueLinkType` y
> `GET /rest/api/2/issue/createmeta?projectKeys=SAZ` antes de implementar soporte SAZ en el service layer.

---

## SCRX — EC · SCRX · Agile

| Campo | Valor |
|---|---|
| URL | https://jira.zurich.com/projects/SCRX |
| Tipo | Software (Agile) |
| `JIRA_PROJECT_KEY` | `SCRX` |
| `TICKET_LANG` | `es` |
| Lead | Israel Onofre |

**Propósito:** desarrollo ágil de productos digitales Zurich Ecuador/LATAM — seguros de vida,
renovaciones, canales digitales (web/app). Incluye ciclo completo: desarrollo, testing
(funcional + regresión) y change control.

**Tipos de issue disponibles:** Task, Story, Bug, Epic, Feature, Technical Story,
Change Control Story, Issue/Bug Post Producción, Test (y subtipos de test).

**Notas:** proyecto con mayor variedad de tipos — incluye flujos de change control y
tipos específicos post-producción. Los issues de validación de canales digitales
(banners, validaciones de producto) son frecuentes.

---

## Referencia rápida

| Proyecto | `JIRA_PROJECT_KEY` | `TICKET_LANG` | Tipo Jira | Uso principal |
|---|---|---|---|---|
| ZNRX | `ZNRX` | `es` | Software | Requerimientos y desarrollo |
| AIPROJECTS | `AIPROJECTS` | `en` | Software | IA y automatización de negocio |
| SAZ | `SAZ` | `es` | Business | Solicitudes DevOps / Release |
| SCRX | `SCRX` | `es` | Software | Desarrollo ágil Ecuador/LATAM |
