# Roles y permisos Jira — Zurich

Referencia de permisos del usuario `CARLOS.DUARTE2` (Carlos David Duarte) en cada proyecto,
obtenida de `GET /rest/api/2/mypermissions?projectKey={KEY}`.

> Los roles de proyecto (administrador, desarrollador, etc.) no son visibles vía API sin
> permisos de administración. Este documento documenta los permisos efectivos reales.

---

## Permisos efectivos por proyecto

Las operaciones de `claude-mcp-jira` requieren estos permisos en Jira. El usuario actual
los tiene en todos los proyectos activos.

| Permiso Jira | ZNRX | AIPROJECTS | SAZ | SCRX | Usado por |
|---|:---:|:---:|:---:|:---:|---|
| `CREATE_ISSUES` | ✓ | ✓ | ✓ | ✓ | `POST /issues` — crear ticket |
| `EDIT_ISSUES` | ✓ | ✓ | ✓ | ✓ | `PATCH /issues/{key}` — actualizar ticket |
| `ADD_COMMENTS` | ✓ | ✓ | ✓ | ✓ | `PATCH /issues/{key}` con `comment` |
| `BROWSE_PROJECTS` | ✓ | ✓ | ✓ | ✓ | `GET /issues/{key}` — leer ticket y buscar |
| `LINK_ISSUES` | ✓ | ✓ | ✓ | ✓ | Fase 5 — vincular SAZ → ZNRX |
| `ASSIGN_ISSUES` | ✓ | ✓ | ✓ | ✓ | Asignación en updates |
| `TRANSITION_ISSUES` | ✓ | ✓ | ✓ | ✓ | Cambio de estado en updates |
| `DELETE_ISSUES` | ✓ | ✗ | ✓ | ✗ | No usado actualmente |
| `MODIFY_REPORTER` | ✓ | ✗ | ✓ | ✗ | No usado actualmente |
| `START_STOP_SPRINTS` | ✗ | ✓ | ✗ | ✓ | No usado actualmente |
| `ADMINISTER_PROJECTS` | ✗ | ✗ | ✗ | ✗ | No requerido |

---

## Diferencias entre proyectos

### ZNRX
- Tiene `DELETE_ISSUES` y `MODIFY_REPORTER` — permisos más amplios que AIPROJECTS/SCRX.
- Sin `START_STOP_SPRINTS` — proyecto Kanban, no Scrum.

### AIPROJECTS
- Sin `DELETE_ISSUES` ni `MODIFY_REPORTER`.
- Tiene `START_STOP_SPRINTS` — proyecto Scrum con sprints.
- Sin `Delete Own Worklogs` — restricción de auditoría.

### SAZ
- Tiene `DELETE_ISSUES` y `MODIFY_REPORTER` — proyecto operativo, permisos amplios.
- Sin `START_STOP_SPRINTS` — proyecto business, sin sprints.
- Tipo de proyecto `business` (no `software`) — flujos de aprobación diferentes.

### SCRX
- Sin `DELETE_ISSUES` ni `MODIFY_REPORTER`.
- Tiene `START_STOP_SPRINTS` — proyecto Scrum activo.
- Componentes con leads asignados (Michelle Ochoa, Juan Carlos León, Henry Bautista, otros).

---

## Roles MCP (`claude-mcp-jira`)

Los roles internos del MCP server son independientes de los roles Jira. Se asignan por API key en `.env`.

| Rol MCP | Herramientas | Equivalencia orientativa en Jira |
|---|---|---|
| `dev` | `create`, `get`, `search` | Developer — puede crear y leer |
| `lead` | `create`, `update`, `get`, `search` | Tech Lead — puede editar además de crear |
| `system` | todas | Service account — acceso completo |

Configuración en `.env`:
```
MCP_KEY_ROLES=key-dev-1:dev,key-lead-1:lead,key-system:system
MCP_DEFAULT_ROLE=dev
```

---

## Notas de acceso API

- **Auth**: PAT Bearer — `Authorization: Bearer <JIRA_PAT>`. Generado en `jira.zurich.com` → Perfil → Personal Access Tokens.
- **Roles del proyecto**: no accesibles via `GET /rest/api/2/project/{key}/role` sin permisos de administración.
- **Grupos del usuario**: no visibles en `GET /rest/api/2/myself` con el PAT actual — requiere permisos de administración global.
- **SSL**: `jira.zurich.com` usa DigiCert EV RSA CA G2 (no la CA interna Zurich). En dev/WSL usar `/etc/ssl/certs/ca-certificates.crt`.
