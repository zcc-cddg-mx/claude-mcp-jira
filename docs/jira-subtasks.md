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

| Proyecto | Conversión Task→Sub-task vía API | Estado verificación |
|---|---|---|
| AIPROJECTS | ❌ No posible | Verificado en pruebas 2026-06-22 |
| ZNRX | ❌ No posible (comportamiento igual en toda la instancia DC) | Pendiente verificación empírica |
| SCRX | ❌ No posible (comportamiento igual en toda la instancia DC) | Pendiente verificación empírica |
| SAZ | ❌ No posible (comportamiento igual en toda la instancia DC) | Pendiente verificación empírica |

La limitación es a nivel de instancia Jira Server/DC, no de configuración de proyecto — se espera el mismo comportamiento en todos los proyectos de `jira.zurich.com`.
