# Plan de Remediación: Lagunas Multi-proyecto

**Fecha**: Junio 2026  
**Contexto**: identificadas tras implementar Fases 7 y 7b — el service layer soporta multi-proyecto en `create` y `search`, pero varios endpoints y funciones aún asumen un único proyecto.

---

## Resumen de lagunas

| # | Laguna | Archivo | Impacto | Estado |
|---|---|---|---|---|
| 1 | `clone_issue()` usa constantes hardcodeadas pre-Fase 7 | `jira_client.py` | Bug funcional — clone de ticket no-ZNRX crea en ZNRX con constraints incorrectas | ✅ Resuelto |
| 2 | Endpoints de acción no llaman `_project_from_key()` | `jira_client.py` | Solo relevante si el proyecto tiene constraints distintas al default | ✅ No requiere fix |
| 3 | MCP `update_jira_issue` no expone `project` en inputSchema | `jira_mcp/server.py` | `_project_from_key()` ya lo infiere del key; sin impacto funcional real | ✅ No requiere fix |

---

## Laguna 1 — `clone_issue()` hardcodeado (CRÍTICA)

### Síntoma

`clone_issue()` referencia constantes que ya no existen como variables globales:

```python
# service/clients/jira_client.py — líneas 130, 141, 143
"project": {"key": _JIRA_PROJECT_KEY},      # → siempre ZNRX
fields["customfield_25832"] = _LINEA_SERVICIO_BAU  # → ZNRX-only
priority_id = _PRIORITY_IDS.get(priority_name)     # → ZNRX IDs
issuetype = _ISSUETYPE_FALLBACK.get(...)            # → ZNRX fallback
```

Estas constantes fueron eliminadas en Fase 7 del resto del código pero permanecen en `clone_issue()` implícitamente — si se ejecuta, fallará en runtime con `NameError` o usará valores incorrectos.

### Fix

Reemplazar las referencias hardcodeadas por `get_config(_project_from_key(source_key))`:

```python
def clone_issue(source_key: str, source: dict, payload) -> str:
    cfg = get_config(_project_from_key(source_key))   # ← config dinámica
    f = source["fields"]

    issuetype_name = f["issuetype"]["name"]
    issuetype = cfg["issuetype_fallback"].get(issuetype_name, issuetype_name)
    parent = f.get("parent")

    summary = (payload.summary or f.get("summary", ""))[:100]
    description = payload.description or f.get("description", "") or ""

    fields: dict = {
        "project": {"key": _project_from_key(source_key)},   # ← dinámico
        "summary": summary,
        "description": description,
        "issuetype": {"name": issuetype},
    }

    if parent:
        fields["parent"] = {"key": parent["key"]}
    else:
        # Campos requeridos según config del proyecto (e.g. customfield_25832 en ZNRX)
        for field_key, field_val in cfg["required_custom"].items():
            fields[field_key] = field_val

        # Priority: formato según proyecto (id en ZNRX, name en otros)
        priority_name = (f.get("priority") or {}).get("name", "Low")
        if cfg["priority_format"] == "id":
            priority_id = cfg["priority_ids"].get(priority_name)
            if priority_id:
                fields["priority"] = {"id": priority_id}
        else:
            fields["priority"] = {"name": priority_name}

    new_key = _post("/rest/api/2/issue", {"fields": fields})["key"]

    if not parent:
        _post_noret("/rest/api/2/issueLink", {
            "type": {"name": "Cloners"},
            "outwardIssue": {"key": source_key},
            "inwardIssue": {"key": new_key},
        })

    return new_key
```

### Archivos afectados
- `service/clients/jira_client.py` — solo `clone_issue()`; el resto ya usa `_project_from_key()`

### Verificación
```bash
# Clonar un ticket ZNRX — debe seguir funcionando (constraints curadas)
curl -s -X POST http://localhost:18000/issues/ZNRX-68171/clone \
  -H "Content-Type: application/json" -H "x-user: carlos.duarte2" \
  -d '{"text": "[MCP Claude Jira Test] clone multi-project fix — puede eliminarse"}'

# Clonar un ticket AIPROJECTS — debe crear en AIPROJECTS (no en ZNRX)
curl -s -X POST http://localhost:18000/issues/AIPROJECTS-38/clone \
  -H "Content-Type: application/json" -H "x-user: carlos.duarte2" \
  -d '{"text": ""}'
```

---

## Laguna 2 — Endpoints de acción sin `_project_from_key()` (BAJA)

### Síntoma

Los siguientes endpoints operan sobre un `{key}` existente pero no consultan la config del proyecto:

| Función | Usa `_project_from_key` | Config relevante |
|---|---|---|
| `update_issue()` | ✅ | priority_format |
| `set_priority()` | ✅ | priority_format |
| `assign_issue()` | ❌ | ninguna — usa `name` directo |
| `add_comment()` | ❌ | ninguna |
| `log_work()` | ❌ | ninguna |
| `transition_issue()` | ❌ | ninguna |
| `update_labels()` / `get_labels()` | ❌ | ninguna |
| `link_issue()` | ❌ | ninguna |

### Análisis

La mayoría de estas funciones **no necesitan la config del proyecto** porque no construyen payloads de creación — simplemente envían el valor que Claude ya procesó. Jira valida en destino si el campo es válido para ese proyecto.

La única excepción potencial es `set_priority()` — ya usa `_project_from_key()` correctamente.

### Conclusión

No requieren fix inmediato. Si en el futuro un proyecto tiene restricciones específicas sobre comentarios, worklogs o labels, se añade `get_config(_project_from_key(key))` en ese punto.

---

## Laguna 3 — MCP `update_jira_issue` sin campo `project` (MUY BAJA)

### Síntoma

El inputSchema de `update_jira_issue` en `jira_mcp/server.py` no incluye `project` como campo opcional.

### Análisis

`update_issue()` en `jira_client.py` ya infiere el proyecto desde el prefijo del key (`_project_from_key()`). Claude no necesita especificarlo — el key `AIPROJECTS-38` ya determina el proyecto unívocamente.

### Conclusión

No requiere fix. El campo sería redundante.

---

## Orden de implementación

```
1. Fix Laguna 1 — clone_issue()      ← único cambio de código necesario
2. Test con ZNRX y AIPROJECTS        ← verificar que ZNRX sigue funcionando
3. Actualizar TODO y CLAUDE.md
```

El fix es quirúrgico: **un solo archivo, una sola función**, sin impacto en el resto del sistema.
