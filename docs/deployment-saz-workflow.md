# Despliegues — POST /deployments/saz-workflow

Endpoint que crea el PR en Azure DevOps y el ticket SAZ de solicitud de despliegue en una sola llamada.

**URL local:** `http://localhost:18000/deployments/saz-workflow`  
**Método:** `POST`  
**Content-Type:** `application/json`

---

## Campos

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `repo` | string | ✅ | Nombre del repo en el registry de code-agent-mcp |
| `branch` | string | ✅ | Rama feature con los cambios (ej: `feature/REQ2298577_limite_autos`) |
| `target` | string | ✅ | Ambiente destino: `developer`, `test` o `prod` |
| `ticket` | string | ✅ | Jira key (`ZNRX-67926`) o ID de requerimiento (`REQ2298577`). Usar `NA` si no aplica |
| `task` | string | ✅ | Descripción corta que aparece en el título del SAZ (ej: `Limite Autos - Backend`) |
| `project_label` | string | ✗ | Etiqueta de proyecto en el título SAZ. Default: `OV` |
| `znrx_key` | string | ✗ | Si se provee, vincula el SAZ al ticket ZNRX (`Relates to`). Formato: `ZNRX-12345` |

### Mapping `target` → rama destino del PR

| `target` | Rama destino | Etiqueta SAZ |
|---|---|---|
| `developer` | `developer` | DEVELOPER |
| `test` | `test` | TEST |
| `prod` | `develop` | PROD |

> DevOps promueve `develop → main` manualmente en producción.

---

## Respuesta exitosa (201)

```json
{
    "pr_id": 2608,
    "pr_url": "https://dev.azure.com/ZurichInsurance-EC/Oficina-Virtual-ZEC/_git/ov-arizona-backend-ecuador/pullrequest/2608",
    "aux_branch": "feature/documentacion_test_auxiliar",
    "saz_key": "SAZ-7479",
    "summary": "Despliegue ambiente TEST - OV - Documentacion",
    "status": "created"
}
```

| Campo | Descripción |
|---|---|
| `pr_id` | ID del PR en Azure DevOps |
| `pr_url` | URL directa al PR |
| `aux_branch` | Rama auxiliar creada (nombre: `{feature}_{target}_auxiliar`) |
| `saz_key` | Key del ticket SAZ creado |
| `summary` | Título del SAZ: `Despliegue ambiente {ENV} - {project_label} - {task}` |
| `status` | `created` (SAZ independiente) o `linked` (SAZ vinculado a `znrx_key`) |

> El PR es **idempotente**: si ya existe un PR para esa rama auxiliar, devuelve el existente sin crear uno nuevo.

---

## Errores

| HTTP | Causa |
|---|---|
| `422` | Campo requerido faltante o vacío |
| `429` | Rate limit excedido (30 req/60s por usuario) |
| `502` | PR creation failed — code-agent-mcp no disponible o timeout |
| `502` | PR created (#N) but SAZ failed — el PR se creó pero Jira no respondió |

---

## Ejemplos

### Despliegue a TEST

```bash
curl -X POST http://localhost:18000/deployments/saz-workflow \
  -H "Content-Type: application/json" \
  -H "X-User: carlos.duarte2" \
  -d '{
    "repo": "ov-arizona-backend-ecuador",
    "branch": "feature/REQ2298577_limite_autos",
    "target": "test",
    "ticket": "REQ2298577",
    "task": "Limite Autos - Backend Ecuador",
    "project_label": "OV"
  }'
```

### Despliegue a PROD vinculado a ZNRX

```bash
curl -X POST http://localhost:18000/deployments/saz-workflow \
  -H "Content-Type: application/json" \
  -H "X-User: carlos.duarte2" \
  -d '{
    "repo": "ov-arizona-backend-ecuador",
    "branch": "feature/REQ2298577_limite_autos",
    "target": "prod",
    "ticket": "REQ2298577",
    "task": "Limite Autos - Backend Ecuador",
    "project_label": "OV",
    "znrx_key": "ZNRX-67926"
  }'
```

### Los tres ambientes de un mismo feature

```bash
for TARGET in developer test prod; do
  curl -s -X POST http://localhost:18000/deployments/saz-workflow \
    -H "Content-Type: application/json" \
    -H "X-User: carlos.duarte2" \
    -d "{
      \"repo\": \"ov-arizona-backend-ecuador\",
      \"branch\": \"feature/REQ2298577_limite_autos\",
      \"target\": \"$TARGET\",
      \"ticket\": \"REQ2298577\",
      \"task\": \"Limite Autos - Backend Ecuador\",
      \"project_label\": \"OV\"
    }" | python3 -m json.tool
  echo "---"
done
```

> Ejecutar secuencialmente (no en paralelo) — dos llamadas simultáneas a code-agent-mcp pueden generar timeouts.

---

## Prerrequisitos

### 1. Stack local corriendo

```bash
bash run_local.sh        # levanta code-agent-mcp :5001 + service :18000 + MCP :18001
bash run_local.sh status # verificar los tres servicios
```

`run_local.sh` inicia automáticamente code-agent-mcp antes del service layer. Si solo necesitas code-agent-mcp de forma independiente:

```bash
bash /home/idavid/dev/claude/code-agent-mcp/run_local.sh
curl http://localhost:5001/health   # → {"status":"ok"}
```

### 2. Repo registrado en code-agent-mcp

El registro se pierde al reiniciar code-agent-mcp (DB efímera en `/tmp`). Registrar de nuevo si es necesario:

```bash
TOKEN=$(grep "^TOKEN_AZURE=" .env | cut -d= -f2)

curl -X POST http://localhost:5001/repos \
  -H "X-Agent-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://dev.azure.com/ZurichInsurance-EC/Oficina-Virtual-ZEC/_git/ov-arizona-backend-ecuador",
    "local_path": "/home/idavid/dev/ov/ov-arizona-backend-ecuador"
  }'
```

Si `POST /repos` falla (PAT sin permisos de inspección), usar el endpoint de path directo:

```bash
curl -X PATCH http://localhost:5001/repos/ov-arizona-backend-ecuador/local-path \
  -H "X-Agent-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"local_path": "/home/idavid/dev/ov/ov-arizona-backend-ecuador"}'
```

---

## Repos disponibles

| Alias | Proyecto |
|---|---|
| `ov-arizona-backend-ecuador` | OV Backend Ecuador |
| `ov-arizona-frontend-ecuador` | OV Frontend Ecuador |
| `ov-arizona-core` | OV Core |

---

## Vía MCP tool (Claude Code)

El mismo flujo está disponible como MCP tool para usuarios con rol `lead`:

```
create_deployment_saz_workflow(
  repo="ov-arizona-backend-ecuador",
  branch="feature/REQ2298577_limite_autos",
  target="test",
  ticket="REQ2298577",
  task="Limite Autos - Backend Ecuador"
)
```
