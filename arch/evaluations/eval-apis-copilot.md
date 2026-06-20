# 🧠 🎯 1. Principio de diseño (muy importante)

En Jira:

> Un issue no es solo un recurso → es un **aggregate con commands**

Por eso:

* `PATCH /issue` (genérico) ❌ poco expresivo
* endpoints por acción ✅ mejor control + auditoría + AI

***

# ✅ 🧩 2. Acciones PRINCIPALES (top tier → endpoints dedicados)

Estas son las que **sí o sí debes modelar como endpoints explícitos**:

***

## 🔹 2.1 Actualización básica

### ✅ Endpoint

```http
PATCH /issues/{key}
```

### ✅ Acciones

* summary
* description

***

## 🔹 2.2 Cambio de estado (workflow)

👉 Esta es **la más importante en Jira**

### ✅ Endpoint

```http
POST /issues/{key}/transition
```

### ✅ Payload

```json
{
  "transition": "Done"
}
```

***

## 🔹 2.3 Asignación

### ✅ Endpoint

```http
POST /issues/{key}/assign
```

```json
{
  "assignee": "carlos.duarte"
}
```

***

## 🔹 2.4 Prioridad

### ✅ Endpoint

```http
POST /issues/{key}/priority
```

```json
{
  "priority": "High"
}
```

***

## 🔹 2.5 Comentarios

👉 Muy frecuente y crítico

### ✅ Endpoint

```http
POST /issues/{key}/comments
```

```json
{
  "comment": "Se agrega información adicional..."
}
```

***

## 🔹 2.6 Labels

### ✅ Endpoint

```http
POST /issues/{key}/labels
```

```json
{
  "action": "add",
  "labels": ["backend", "login"]
}
```

***

## 🔹 2.7 Worklogs (registro de tiempo)

👉 importante en enterprise

### ✅ Endpoint

```http
POST /issues/{key}/worklogs
```

```json
{
  "time_spent": "2h",
  "comment": "Fix login bug"
}
```

***

# 🟡 🧩 3. Acciones SECUNDARIAS (van a `/actions`)

Estas son menos frecuentes → perfecto usar tu idea:

```http
POST /issues/{key}/actions
```

***

## ✅ Ejemplos ideales para `/actions`

### 🔸 3.1 Watchers

```json
{
  "action": "add_watcher",
  "user": "maria"
}
```

***

### 🔸 3.2 Votes

```json
{
  "action": "vote"
}
```

***

### 🔸 3.3 Links entre issues

```json
{
  "action": "link_issue",
  "target": "PROJ-100",
  "type": "blocks"
}
```

***

### 🔸 3.4 Attachments

```json
{
  "action": "add_attachment",
  "file_id": "123"
}
```

***

### 🔸 3.5 Fix versions / versions

```json
{
  "action": "set_fix_version",
  "version": "1.2.0"
}
```

***

### 🔸 3.6 Components

```json
{
  "action": "set_component",
  "component": "auth-module"
}
```

***

### 🔸 3.7 Custom fields

```json
{
  "action": "update_custom_field",
  "field": "severity",
  "value": "critical"
}
```

***

# 🧠 🔥 4. Diseño recomendado de `/actions`

Muy importante: hacerlo **tipado, no libre**

***

## ✅ Schema recomendado

```json
{
  "type": "object",
  "properties": {
    "action": {
      "type": "string",
      "enum": [
        "add_watcher",
        "vote",
        "link_issue",
        "add_attachment",
        "set_fix_version",
        "set_component",
        "update_custom_field"
      ]
    }
  },
  "required": ["action"]
}
```

***

## ✅ Dispatcher backend

```python
def handle_action(action):
    match action["action"]:
        case "add_watcher":
            ...
        case "link_issue":
            ...
        case "update_custom_field":
            ...
```

***

# 🧠 🤖 5. Importante para Claude / MCP

Esto impacta directamente tu diseño AI 👇

***

## ✅ Usa endpoints explícitos para acciones frecuentes

Porque Claude:

* entiende mejor commands claros
* reduce errores
* genera mejores decisiones

👉 Ejemplo:

❌

```
update issue with assignment
```

✅

```
assign_jira_issue
```

***

## ✅ Tools MCP sugeridas

```python
create_jira_issue
update_jira_issue
transition_jira_issue
assign_jira_issue
add_comment_jira_issue
add_worklog_jira_issue
```

👉 1 tool por endpoint crítico

***

## ✅ Tool genérica para `/actions`

```python
perform_jira_issue_action
```

***

# ⚖️ 6. Balance correcto (clave)

Tu diseño debe quedar así:

***

## 🔝 Core (explícitos)

* transition ✅
* assign ✅
* comment ✅
* worklog ✅
* priority ✅
* labels ✅

***

## 🟡 Flexible (genérico)

* watchers
* linking
* custom fields
* attachments
* versions

***

👉 Esto es exactamente el balance usado en sistemas enterprise.

***

# 🧠 7. Mejora PRO (muy recomendada)

Agrega:

```json
{
  "dry_run": true
}
```

👉 permite:

* preview sin ejecutar
* UI con confirmación
* validación AI

***

# 🏁 Conclusión

👉 Tu idea es **correcta y madura**:

✅ Endpoints específicos para acciones core  
✅ Endpoint genérico para long-tail

***

# 🎯 Lista final recomendada

## ✅ Endpoints principales

```http
PATCH /issues/{key}
POST  /issues/{key}/transition
POST  /issues/{key}/assign
POST  /issues/{key}/priority
POST  /issues/{key}/comments
POST  /issues/{key}/labels
POST  /issues/{key}/worklogs
```

***

## ✅ Endpoint genérico

```http
POST /issues/{key}/actions
```

***