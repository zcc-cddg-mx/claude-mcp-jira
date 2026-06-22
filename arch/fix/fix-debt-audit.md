# Auditoría de Deuda Técnica — Fases 4.3 a 7b

**Fecha**: Junio 2026  
**Alcance**: Fases 5 (SAZ), 4.3 (transitions/worklog), 4.4 (mejoras API), 4.5 (link dinámico), 7/7b (multi-proyecto), bitácora de tests.  
**Metodología**: revisión de código fuente + cruce contra tests existentes.

---

## Resumen ejecutivo

| # | Área | Hallazgo | Severidad | Estado |
|---|---|---|---|---|
| 1 | Tests | 9 endpoints sin cobertura e2e | Alta | Pendiente |
| 2 | Link (4.5) | No valida source != target (auto-link) | Media | Pendiente |
| 3 | Endpoints GET públicos | `/issue-link-types`, `/projects`, `/projects/{key}` sin rate limit ni auth | Media | Pendiente |
| 4 | Multi-proyecto (7b) | `resolve_project` llama `get_or_discover` antes de verificar allowlist | Media | Pendiente |
| 5 | SAZ (5) | `znrx_key` sin validación de formato ni existencia previa | Baja | Pendiente |
| 6 | Labels (4.4) | Usa `ActionsRequest/ActionsResponse` en lugar de schemas dedicados | Baja | Pendiente |
| 7 | Assign (4.4) | `assignee` acepta string vacío → Jira recibe `{"name": ""}` | Baja | Pendiente |
| 8 | Worklog (4.3) | `time_spent_seconds` sin mínimo — permite registrar 0 segundos | Baja | Pendiente |
| 9 | SQLite (7b) | `PROJECT_DB_PATH` relativo — ambiguo si el cwd cambia fuera de Docker | Baja | Pendiente |

---

## Hallazgo 1 — 9 endpoints sin cobertura e2e (ALTA)

### Síntoma

Los tres scripts de test actuales (`test-dev.sh`, `test-mcp.sh`, `test-multi.sh`) no ejercitan los siguientes endpoints:

| Endpoint | Fase | Test existente |
|---|---|---|
| `POST /issues/{key}/transition` | 4.3 | ❌ |
| `POST /issues/{key}/worklog` | 4.3 | ❌ |
| `POST /issues/{key}/comments` | 4.4 | ❌ |
| `POST /issues/{key}/assign` | 4.4 | ❌ |
| `POST /issues/{key}/priority` | 4.4 | ❌ |
| `POST /issues/{key}/labels` | 4.4 | ❌ |
| `POST /issues/{key}/clone` | 4.4 | ❌ (fix laguna 1 validado ad-hoc) |
| `POST /issues/{key}/link` | 4.5 | ❌ |
| `POST /issues/saz` | 5 | ❌ |

### Fix propuesto

Crear `scripts/test-actions.sh` que cubra estos 9 endpoints sobre un ticket de prueba ZNRX.  
Flujo sugerido:
1. Crear ticket base `[MCP Claude Jira Test]`
2. Ejercitar cada endpoint en orden lógico (comments → assign → priority → labels → worklog → transition → clone → link → saz)
3. Limpiar tickets creados al finalizar

---

## Hallazgo 2 — Link: no valida source != target (MEDIA)

### Síntoma

`POST /issues/{key}/link` no verifica que `key` != `payload.target_key`. Claude podría resolver el texto libre de forma que `target_key == source_key`, creando un auto-link.

```python
# service/routes/link.py — no existe este check
link_issue(key, payload.target_key, ...)   # key podría == target_key
```

Jira Server acepta auto-links en algunos tipos (resultado: ticket se enlaza consigo mismo, confuso en la UI).

### Fix propuesto

En `service/routes/link.py`, antes de llamar a `link_issue`:

```python
if payload.target_key.upper() == key.upper():
    raise HTTPException(status_code=422, detail="No se puede enlazar un ticket consigo mismo.")
```

### Archivos afectados
- `service/routes/link.py` — 1 línea

---

## Hallazgo 3 — Endpoints GET públicos sin rate limit ni auth (MEDIA)

### Síntoma

Tres endpoints de lectura no tienen `x_user` header ni `rate_limit_check`:

| Endpoint | Archivo |
|---|---|
| `GET /issue-link-types` | `service/routes/link.py` → `meta_router` |
| `GET /projects` | `service/routes/projects.py` |
| `GET /projects/{key}` | `service/routes/projects.py` |

`GET /projects/{key}` es especialmente sensible: puede disparar llamadas a la API de Jira en cada request (si el proyecto no está en DB), sin ningún freno.

### Fix propuesto

Añadir `x_user: str = Header(default="anonymous")` + `rate_limit_check(x_user)` en los tres endpoints. Patrón idéntico al resto de routes.

Para `GET /projects/{key}` específicamente: la discovery call a Jira ocurre solo en cache miss (primer acceso al proyecto) — el rate limit previene scanning masivo.

### Archivos afectados
- `service/routes/link.py` — `list_link_types()`
- `service/routes/projects.py` — `list_projects_endpoint()` y `get_project_endpoint()`

---

## Hallazgo 4 — `resolve_project` llama `get_or_discover` antes del allowlist check (MEDIA)

### Síntoma

En `service/clients/project_config.py`:

```python
def resolve_project(requested: Optional[str]) -> str:
    key = (requested or _DEFAULT_PROJECT).upper()
    if ALLOWED_PROJECTS and key not in ALLOWED_PROJECTS:
        raise ValueError(...)          # ← rechaza aquí
    get_or_discover(key)               # ← pero esto ya ocurrió antes del check
    return key
```

Espera — el orden real es: primero check allowlist, luego `get_or_discover`. Pero si `ALLOWED_PROJECTS` está vacío (self-service), cualquier proyecto llega a `get_or_discover` sin freno. Combinado con hallazgo 3 (endpoints GET sin rate limit), un actor puede forzar discovery masiva contra la API de Jira.

### Fix propuesto

Sin cambios de código por ahora — el hallazgo 3 (rate limit en endpoints GET) mitiga el riesgo. Documentar como deuda a revisar si se vacía la allowlist.

---

## Hallazgo 5 — SAZ: `znrx_key` sin validación de formato (BAJA)

### Síntoma

```python
class CreateSAZRequest(BaseModel):
    text: str
    znrx_key: Optional[str] = Field(None, example="ZNRX-68126")
```

`znrx_key` acepta cualquier string. Si el usuario pasa un key mal formado (ej. `"znrx68126"`, `"PROJ-"`, `""`), la llamada a `POST /rest/api/2/issueLink` fallará en Jira con un error 400 que se devuelve como 502.

### Fix propuesto

Añadir `pattern` al Field:

```python
znrx_key: Optional[str] = Field(
    None,
    pattern=r'^[A-Z][A-Z0-9]+-\d+$',
    example="ZNRX-68126",
)
```

Devuelve 422 con mensaje claro antes de llegar a Jira.

### Archivos afectados
- `service/schemas/issue.py` — `CreateSAZRequest.znrx_key`

---

## Hallazgo 6 — Labels usa schemas genéricos de `/actions` (BAJA)

### Síntoma

`service/routes/labels.py` importa y devuelve `ActionsRequest` / `ActionsResponse` — los mismos schemas del endpoint genérico `/actions`. No tiene schemas propios.

```python
from ..schemas import ActionsRequest, ActionsResponse   # compartidos con /actions
```

Consecuencia: el Swagger de `/issues/{key}/labels` muestra campos de `/actions` (incluyendo `action` en el body request, que labels no usa directamente). Confuso para consumidores de la API.

### Fix propuesto

Crear `LabelsRequest(text: str)` y `LabelsResponse(key, operation, labels)` en `schemas/issue.py`. Bajo impacto funcional, mejora claridad del contrato.

### Archivos afectados
- `service/schemas/issue.py` — añadir 2 schemas
- `service/routes/labels.py` — cambiar imports y tipos

---

## Hallazgo 7 — Assign acepta string vacío como assignee (BAJA)

### Síntoma

```python
class AssignIssuePayload(BaseModel):
    assignee: Optional[str] = None
```

Si Claude resuelve el texto como `assignee=""` (string vacío), `assign_issue(key, "")` envía `{"name": ""}` a Jira. Jira Server interpreta `name: ""` de forma inconsistente según la versión (puede asignar a usuario vacío o devolver 400).

### Fix propuesto

En `parse_assign_issue()` o en `AssignIssuePayload`:

```python
assignee: Optional[str] = Field(None, min_length=1)
```

String vacío se normaliza a `None` (desasignar) o se rechaza con 422.

### Archivos afectados
- `service/schemas/issue.py` — `AssignIssuePayload.assignee`

---

## Hallazgo 8 — Worklog sin mínimo en `time_spent_seconds` (BAJA)

### Síntoma

```python
class LogWorkPayload(BaseModel):
    time_spent_seconds: int
    comment: Optional[str] = None
    started: Optional[str] = None
```

No hay validación `ge=1`. Claude podría extraer `time_spent_seconds=0` de inputs ambiguos. Jira Server rechaza 0 segundos con 400, que llega al usuario como 502.

### Fix propuesto

```python
time_spent_seconds: int = Field(..., ge=60)   # mínimo 1 minuto — Jira ignora fracciones de minuto
```

### Archivos afectados
- `service/schemas/issue.py` — `LogWorkPayload.time_spent_seconds`

---

## Hallazgo 9 — `PROJECT_DB_PATH` relativo (BAJA)

### Síntoma

```python
PROJECT_DB_PATH = os.environ.get("PROJECT_DB_PATH", "projects.db")
```

En Docker el `cwd` es `/app`, por lo que resuelve a `/app/projects.db` (correcto con el volumen). Fuera de Docker, si el proceso se lanza desde un directorio distinto al repo, el archivo se crea en el directorio de trabajo en lugar del repo.

### Fix propuesto

Resolver relativo al archivo del módulo como fallback:

```python
_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "..", "projects.db")
PROJECT_DB_PATH = os.environ.get("PROJECT_DB_PATH", _DEFAULT_DB)
```

O simplemente documentar que `PROJECT_DB_PATH` debe ser absoluto en entornos no-Docker.

### Archivos afectados
- `service/clients/project_db.py` — 1 línea

---

## Orden de implementación recomendado

```
Prioridad alta:
  1. scripts/test-actions.sh — cobertura e2e de los 9 endpoints sin test

Prioridad media:
  2. Hallazgo 2 — auto-link check en link.py (1 línea)
  3. Hallazgo 3 — rate limit en endpoints GET públicos (3 endpoints)

Prioridad baja (agrupar en un solo commit):
  4. Hallazgo 5 — znrx_key pattern validation
  5. Hallazgo 7 — assignee min_length
  6. Hallazgo 8 — time_spent_seconds ge=60
  7. Hallazgo 6 — schemas dedicados para labels
  8. Hallazgo 9 — PROJECT_DB_PATH absoluto
```

El hallazgo 4 (discovery antes de allowlist) queda como nota técnica — se mitiga con el hallazgo 3 y no requiere cambios por sí solo.
