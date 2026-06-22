# Base de datos — claude-mcp-jira

SQLite single-file en `projects.db` (ruta configurable con `PROJECT_DB_PATH`). Contiene dos tablas independientes: configuración de proyectos Jira y registro de repositorios Git.

---

## Archivo

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `PROJECT_DB_PATH` | `<raíz del proyecto>/projects.db` | Ruta al archivo SQLite. Resolver relativo al módulo `service/clients/project_db.py` si no está definida. |

---

## Tabla `projects`

Configuración de proyectos Jira. Combina proyectos con seed manual (restricciones conocidas) y proyectos descubiertos automáticamente (auto-discovery lazy desde Jira).

### Schema

```sql
CREATE TABLE projects (
    project_key             TEXT PRIMARY KEY,
    priority_format         TEXT NOT NULL DEFAULT 'name',
    priority_ids_json       TEXT NOT NULL DEFAULT '{}',
    required_custom_json    TEXT NOT NULL DEFAULT '{}',
    issuetype_fallback_json TEXT NOT NULL DEFAULT '{}',
    ticket_lang             TEXT NOT NULL DEFAULT 'es',
    discovered_at           TEXT NOT NULL,
    discovery_source        TEXT NOT NULL DEFAULT 'seed'
)
```

### Columnas

| Columna | Tipo | Descripción |
|---|---|---|
| `project_key` | TEXT PK | Clave del proyecto Jira (ej. `ZNRX`, `AIPROJECTS`) |
| `priority_format` | TEXT | `"id"` o `"name"` — cómo enviar la prioridad al crear issues |
| `priority_ids_json` | TEXT (JSON) | Mapa `{nombre: id}` para proyectos con `priority_format=id` (ej. `{"High": "2"}`) |
| `required_custom_json` | TEXT (JSON) | Campos custom obligatorios con su valor por defecto (ej. `{"customfield_25832": {"id": "44461"}}`) |
| `issuetype_fallback_json` | TEXT (JSON) | Fallback de tipo de issue (ej. `{"Bug": "Task"}`) cuando el tipo no existe en el proyecto |
| `ticket_lang` | TEXT | Idioma para prompts Claude: `"es"` o `"en"` |
| `discovered_at` | TEXT (ISO 8601) | Timestamp UTC de cuándo se registró el proyecto |
| `discovery_source` | TEXT | `"seed"` (manual al arrancar) o `"jira_auto"` (auto-discovery desde Jira) |

### Proyectos registrados actualmente

| project_key | priority_format | ticket_lang | discovery_source |
|---|---|---|---|
| `ZNRX` | `id` | `es` | `seed` |
| `AIPROJECTS` | `name` | `en` | `seed` |
| `SCRX` | `name` | `es` | `seed` |
| `SAZ` | `name` | `es` | `jira_auto` |
| `ARQX` | `name` | `es` | `jira_auto` |

### Auto-discovery

Cuando se recibe una solicitud para un proyecto no registrado (ej. `POST /issues?project=NEWPROJ`), el service layer:
1. Verifica que el proyecto exista en Jira (`GET /rest/api/2/project/{key}`)
2. Intenta obtener `createmeta` para detectar `priority_format` e `issuetypes`
3. Persiste el proyecto con `discovery_source=jira_auto`
4. Devuelve config con valores por defecto si `createmeta` falla

Módulo: `service/clients/project_db.py` — funciones `init_db()`, `seed()`, `get_config()`, `discover_and_save()`.

---

## Tabla `git_repos`

Registro de repositorios Git locales. Asocia un alias corto con la ruta local, el origen remoto, y el proyecto/ticket Jira por defecto para el registro de worklogs.

### Schema

```sql
CREATE TABLE git_repos (
    name               TEXT PRIMARY KEY,
    repo_path          TEXT NOT NULL,
    origin             TEXT,
    jira_project       TEXT,
    default_issue_key  TEXT,
    is_default         INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL
)
```

### Columnas

| Columna | Tipo | Descripción |
|---|---|---|
| `name` | TEXT PK | Alias corto del repo (ej. `claude-mcp-jira`, `ov-suscripcion`) |
| `repo_path` | TEXT | Ruta absoluta al clon local (ej. `/home/idavid/dev/claude/claude-mcp-jira`) |
| `origin` | TEXT | URL del remoto `origin` (auto-detectada con `git remote get-url origin`) |
| `jira_project` | TEXT | Proyecto Jira por defecto para este repo (ej. `AIPROJECTS`) |
| `default_issue_key` | TEXT | Ticket por defecto para registrar worklogs cuando no se detecta ninguna clave en los commits (ej. `AIPROJECTS-47`) |
| `is_default` | INTEGER (bool) | Solo un repo puede ser default a la vez. Se usa cuando `POST /git/sync` se llama sin `repo_path` ni `repo_name`. |
| `created_at` | TEXT (ISO 8601) | Timestamp UTC de registro |

### Repos registrados actualmente

| name | repo_path | jira_project | default_issue_key | is_default |
|---|---|---|---|---|
| `claude-mcp-jira` | `/home/idavid/dev/claude/claude-mcp-jira` | `AIPROJECTS` | `AIPROJECTS-47` | ✓ |
| `mcp-server-claude` | `/home/idavid/dev/claude/mcp-server-claude` | `AIPROJECTS` | `AIPROJECTS-50` | — |
| `ov-suscripcion` | `/home/idavid/dev/ov/ov-suscripcion-automation` | `AIPROJECTS` | `AIPROJECTS-52` | — |
| `ov-qa` | `/home/idavid/dev/ov/ov-qa-automation` | `AIPROJECTS` | `AIPROJECTS-52` | — |

### Resolución de repo en `POST /git/sync`

```
repo_name  →  busca por name en git_repos
repo_path  →  busca por repo_path en git_repos (o usa directamente)
(ninguno)  →  usa el repo con is_default=1
```

El `default_issue_key` actúa como último fallback para sesiones sin clave detectada (después del regex en mensajes/branch y del fallback Claude NLP). Las sesiones asignadas por este fallback tienen `confidence=low`.

Módulo: `service/git/repo_registry.py` — funciones `init_repo_registry()`, `register_repo()`, `get_repo()`, `list_repos()`, `delete_repo()`, `resolve_repo()`.

---

## Endpoints REST

### Proyectos

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/projects` | Lista proyectos registrados |
| `GET` | `/projects/{key}` | Config de un proyecto; dispara auto-discovery si no existe |

### Repos Git

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/git/repos` | Registrar o actualizar un repo (origin auto-detectado) |
| `GET` | `/git/repos` | Listar todos los repos |
| `GET` | `/git/repos/{name}` | Obtener repo por alias |
| `DELETE` | `/git/repos/{name}` | Eliminar repo del registro |

---

## Inicialización

Ambas tablas se crean al arrancar el service layer (lifespan FastAPI):

```python
# service/main.py
init_db()           # crea tabla projects + seed ZNRX/AIPROJECTS/SCRX
init_repo_registry()  # crea tabla git_repos
```

La inicialización es idempotente (`CREATE TABLE IF NOT EXISTS`).
