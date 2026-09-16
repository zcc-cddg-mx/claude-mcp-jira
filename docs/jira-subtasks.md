# Jira Sub-tasks — Tipos y limitaciones por proyecto

## Limitación confirmada: conversión Task → Sub-task vía REST API

En **Jira Server/Data Center**, la API REST **no permite convertir** un issue existente de tipo Task a Sub-task. El campo `parent` no está expuesto en el screen de edición de ningún proyecto y Jira lo rechaza sistemáticamente.

### Intentos realizados (todos fallidos en AIPROJECTS)

```bash
# Intento 1: fields.issuetype + fields.parent en un PUT
PUT /rest/api/2/issue/AIPROJECTS-41
{"fields": {"issuetype": {"name": "Sub-task"}, "parent": {"key": "AIPROJECTS-38"}}}
→ 400: "Issue type is a sub-task but parent issue key or id not specified."

# Intento 2: solo fields.parent
PUT /rest/api/2/issue/AIPROJECTS-41
{"fields": {"parent": {"key": "AIPROJECTS-38"}}}
→ 204 (éxito aparente) pero el parent NO se persiste — verificado con GET

# Intento 3: update array con issuetype + parent
PUT /rest/api/2/issue/AIPROJECTS-41
{"update": {"issuetype": [{"set": {"name": "Sub-task"}}], "parent": [{"set": {"key": "AIPROJECTS-38"}}]}}
→ 400: "Field 'parent' cannot be set. It is not on the appropriate screen, or unknown."

# Intento 4: cambiar issuetype solo (sin parent)
PUT /rest/api/2/issue/AIPROJECTS-41
{"update": {"issuetype": [{"set": {"name": "Sub-task"}}]}}
→ 204 (éxito aparente) pero el tipo se revierte al hacer GET — Jira lo rechaza silenciosamente sin parent
```

**Conclusión**: el campo `parent` no aparece en el `editmeta` de ningún issue (Task ni Sub-task existente), lo que confirma que no está habilitado en los screens de edición de la instancia `jira.zurich.com`.

---

## Workaround recomendado

1. **Crear el Sub-task nuevo** directamente con `issuetype` correcto y `parent` desde el inicio:
   ```json
   POST /rest/api/2/issue
   {
     "fields": {
       "project": {"key": "AIPROJECTS"},
       "issuetype": {"id": "10003"},
       "parent": {"key": "AIPROJECTS-38"},
       "summary": "Sub-tarea de desarrollo"
     }
   }
   ```
2. **Marcar la Task original** como `Done` (transición id=31).
3. **Crear link** "is duplicated by" de la Task original hacia la nueva Sub-task:
   ```json
   POST /rest/api/2/issueLink
   {"type": {"id": "10002"}, "inwardIssue": {"key": "TASK-VIEJA"}, "outwardIssue": {"key": "SUBTASK-NUEVA"}}
   ```

---

## Workflows por tipo de sub-task — SCRX vs ZNRX

Los tipos de sub-task no solo difieren en nombre — **difieren radicalmente en el workflow asignado**.

### SCRX — Sub-task (id `10003`)

Hereda el mismo workflow de **19 estados** que usa Story/Epic/Task en SCRX:

```
Backlog → Backlog Refinement → To Do → Technical Analysis and Estimation
→ Architecture Approval → CR → In Progress → Blocked / Blocked by Bug
→ Approval Required → CAB REVIEW → Deployed & Ready to Test
→ Ready for QA → Ready for UAT → PROD Deployment → Hypercare/In Production
→ En BAU → Done / Canceled
```

**Implicación:** crear una sub-task en SCRX implica aceptar todo el flujo de historia enterprise. No hay tipo de sub-task con workflow simple disponible en SCRX. Si solo se quieren dos estados operativos ("en progreso" / "terminado"), este tipo no es adecuado.

### ZNRX — Subtarea Historia (id `18124`)

Workflow **minimalista de 3 estados**, diseñado para tracking operativo simple:

```
Open  →  In Progress  →  Done
```

Es el tipo de sub-task de referencia para trabajo de desarrollo en ZNRX. No existe un equivalente en SCRX.

### Comparativa rápida

| | SCRX Sub-task | ZNRX Subtarea Historia |
|---|---|---|
| Tipo id | `10003` | `18124` |
| Estados | 19 | 3 |
| Workflow | Enterprise (CAB, PROD, UAT…) | Operativo simple |
| Cross-proyecto | No (subtask must = mismo proyecto) | No |
| Verificado | 2026-09-16 | 2026-06-25 |

### Alternativas cuando se necesita tracking simple en SCRX

1. **Solicitar a Jira Admin** — crear un nuevo tipo de sub-task en SCRX con workflow propio de 3 estados. Requiere rol Jira Admin; no es configurable vía API ni desde el proyecto.
2. **Issue link cross-proyecto** — crear las sub-tareas como `Subtarea Historia` en ZNRX y vincularlas al story SCRX con link tipo `Child of / Parent of` (id `11101`). Traza la relación; los estados son los deseados; no aparece en la tabla de sub-tasks de SCRX pero sí en la sección de links.
3. **Aceptar el tipo existente** — usar `Sub-task` en SCRX ignorando los estados intermedios enterprise (solo usar `In Progress` y `Done`).

---

## Tipos de sub-task disponibles por proyecto

| Proyecto | id | Nombre | Notas |
|---|---|---|---|
| **AIPROJECTS** | `10003` | Sub-task | Único tipo de sub-task disponible |
| **SCRX** | `10003` | Sub-task | Igual que AIPROJECTS |
| **SCRX** | `11501` | Sub Test Execution | Sub-task de testing |
| **SCRX** | `18122` | Issue Post Producción | Sub-task de incidencia post-prod |
| **ZNRX** | `18124` | Subtarea Historia | Sub-task principal de desarrollo |
| **ZNRX** | `18121` | Casos de Prueba | Sub-task de QA |
| **ZNRX** | `18122` | Issue Post Producción | Sub-task de incidencia |
| **ZNRX** | `18125` | Issue Pre Producción | Sub-task de incidencia pre-prod |
| **ZNRX** | `11501` | Sub Test Execution | Sub-task de ejecución de tests |
| **SAZ** | `10003` | Sub-task | Único tipo disponible |

> ZNRX **no tiene** un tipo genérico "Sub-task". El equivalente más cercano para desarrollo es `Subtarea Historia` (id=18124). Para issues de desarrollo usar ese tipo; para QA usar `Casos de Prueba` (id=18121).

---

## Implicaciones para el service layer

Al crear sub-tasks programáticamente, el `issuetype.id` varía por proyecto. La lógica actual de `service/clients/jira_client.py` no soporta creación de sub-tasks — si se implementa en el futuro, debe consultar el proyecto en `project_db` para obtener el `subtask_issuetype_id` correcto.

Campos requeridos para crear una sub-task vía REST:
- `project.key`
- `issuetype.id` (id correcto según tabla arriba)
- `parent.key` — clave del issue padre (obligatorio en la creación, no editable después)
- `summary`

---

## Verificación por proyecto

| Proyecto | Conversión Task→Sub-task vía API | Creación directa sub-task | Estado verificación |
|---|---|---|---|
| AIPROJECTS | ❌ No posible | ✅ `issuetype.id=10003` + `parent.key` | Verificado 2026-06-22 |
| ZNRX | ❌ No posible | ✅ `issuetype.id=18124` + `parent.key` (sin `customfield_25832`) | Verificado 2026-06-25 |
| SCRX | ❌ No posible (instancia DC, igual que AIPROJECTS/ZNRX) | ✅ `issuetype.id=10003` + `parent.key` | Verificado 2026-09-16 |
| SAZ | ❌ No posible (instancia DC, igual que AIPROJECTS/ZNRX) | ✅ `issuetype.id=10003` + `parent.key` | Inferido por instancia |

La limitación es a nivel de instancia Jira Server/DC — confirmada empíricamente en AIPROJECTS (2026-06-22) y ZNRX (2026-06-25).

### Hallazgos adicionales ZNRX (2026-06-25)

Verificado sobre `ZNRX-68248` (Task con 6 sub-tasks de tipo `Subtarea Historia`):

1. `issuetype: {"name": "Sub-task"}` → `400` — tipo inválido en ZNRX (no existe ese nombre)
2. `issuetype: {"id": "18124"}` + `customfield_25832` → `400` — el campo no está en la pantalla de sub-tasks
3. `issuetype: {"id": "18124"}` **sin** `customfield_25832` → `201` ✅ — crea `Subtarea Historia` correctamente
4. `PUT issuetype: {"name": "Task"}` sobre una `Subtarea Historia` existente → `204` pero **ignorado silenciosamente** — el tipo no cambia

**Regla definitiva para ZNRX**: crear sub-tasks siempre con `issuetype.id=18124` + `parent.key`, sin incluir `customfield_25832`.
