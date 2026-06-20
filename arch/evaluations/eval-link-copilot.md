**Exactamente qué opciones existen para “Link Issue” en Jira Server**, cómo se obtienen y cómo debes modelarlas.

***

# 🧠 🧩 1. Cómo funciona realmente el “Link” en Jira

Cuando en la UI ves:

```
Select a Jira issue to link this issue to
Server: [dropdown]
Link type: [dropdown]
```

👉 Ese dropdown de **Link type** NO es fijo.

✅ Es **configurable por admin**  
✅ Es **global en la instancia**  
✅ Se obtiene vía API

📌 Estructura real:

```json
{
  "name": "Blocks",
  "inward": "is blocked by",
  "outward": "blocks"
}
```

👉 Cada link tiene:

* `name` → tipo técnico
* `outward` → cómo se interpreta desde el issue origen
* `inward` → cómo se interpreta desde el destino

📌 Confirmación:

> Cada link type tiene nombre, descripción inward y outward [\[developer....assian.com\]](https://developer.atlassian.com/cloud/jira/platform/issue-linking-model/)

***

# ✅ 2. Tipos default en Jira Server

Por defecto, Jira trae:

| name      | outward    | inward           |
| --------- | ---------- | ---------------- |
| Relates   | relates to | relates to       |
| Duplicate | duplicates | is duplicated by |
| Blocks    | blocks     | is blocked by    |
| Clone     | clones     | is cloned by     |

📌 Confirmación:

> Nuevas instalaciones incluyen: relates, duplicates, blocks, clones [\[confluence...assian.com\]](https://confluence.atlassian.com/adminjiraserver/configuring-issue-linking-938847862.html)

***

# ✅ 3. Tipos adicionales comunes (dependen del admin)

Muchos Jira enterprise tienen más:

| name       | outward    | inward            |
| ---------- | ---------- | ----------------- |
| Depends    | depends on | is depended on by |
| Causes     | causes     | is caused by      |
| Implements | implements | is implemented by |
| Tests      | tests      | is tested by      |
| Reviews    | reviews    | is reviewed by    |

📌 Ejemplo real:

> Jira puede tener tipos como “is caused by”, “implements”, “reviews” [\[support.at...assian.com\]](https://support.atlassian.com/jira-software-cloud/docs/link-issues/)

***

# 🔥 4. IMPORTANTE: No hardcodear tipos

👉 Esto es crítico:

❌ NO hagas:

```python
link_type = "blocks"
```

✅ Debes obtenerlos dinámicamente:

***

## ✅ Endpoint real (Jira Server)

```http
GET /rest/api/2/issueLinkType
```

***

### ✅ Respuesta típica

```json
{
  "issueLinkTypes": [
    {
      "id": "1000",
      "name": "Duplicate",
      "inward": "Duplicated by",
      "outward": "Duplicates"
    },
    {
      "id": "1010",
      "name": "Blocks",
      "inward": "Blocked by",
      "outward": "Blocks"
    }
  ]
}
```

📌 Confirmado por API docs [\[developer....assian.com\]](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-link-types/)

***

# 🧩 5. Cómo crear un link vía API

## ✅ Endpoint

```http
POST /rest/api/2/issueLink
```

***

### ✅ Payload

```json
{
  "type": {
    "name": "Blocks"
  },
  "inwardIssue": {
    "key": "PROJ-123"
  },
  "outwardIssue": {
    "key": "PROJ-456"
  }
}
```

***

## 🧠 Interpretación

* `outwardIssue` → issue actual
* `type.name` → defines relación
* `inwardIssue` → target

***

# 🧠 6. Cómo modelarlo en tu API

## ✅ Endpoint recomendado

```http
POST /issues/{key}/link
```

***

### ✅ Request

```json
{
  "target_issue": "PROJ-456",
  "link_type": "Blocks",
  "direction": "outward"
}
```

***

## 🔧 Backend

```python
payload = {
  "type": {"name": link_type},
  "outwardIssue": {"key": source},
  "inwardIssue": {"key": target}
}
```

***

# 🧠 7. Mejor UX en tu UI (muy importante)

👉 En tu UI:

NO pongas texto libre ❌

✅ Haz:

### Paso 1

```http
GET /issue-link-types
```

***

### Paso 2 (UI dropdown)

```
Link Type:
[ Blocks ▼ ]

Preview:
"Este issue bloquea PROJ-456"
```

👉 Usa:

* outward description ✅
* human readable ✅

***

# 🤖 8. Impacto en Claude / MCP

Este punto es clave para tu arquitectura AI 👇

***

## ❌ Evita esto:

Claude inventando tipos:

```
link_type: "depends_on_something"
```

***

## ✅ Solución correcta

Cuando definas el tool:

```json
{
  "link_type": {
    "type": "string",
    "enum": ["Blocks", "Duplicate", "Relates"]
  }
}
```

👉 Pero mejor aún:

✅ pasar lista dinámica desde backend

***

## ✅ Tool MCP recomendada

```python
link_jira_issue(
  source_issue: str,
  target_issue: str,
  link_type: str
)
```

***

# 🚀 9. Recomendación avanzada (MUY IMPORTANTE)

## 🧠 Cachear link types

Porque:

* no cambian frecuentemente
* Jira puede ser lento

***

### ✅ Estrategia

```python
cache_ttl = 1h
```

***

# 🏁 Conclusión

👉 Respuesta directa:

## ✅ Tipos disponibles

* Relates
* Blocks
* Duplicate
* Clone
* * custom definidos por admin

***

## ✅ Fuentes dinámicas

```http
GET /rest/api/2/issueLinkType
```

***

## ✅ Recomendación clave

❗ **Nunca hardcodear tipos de link**

***

# 🎯 Diseño final recomendado

## Endpoint dedicado

```http
POST /issues/{key}/link
GET  /issue-link-types
```

***

## MCP tool

```python
link_jira_issue
```

***

## UI

* dropdown dinámico ✅
* preview humano ✅

***