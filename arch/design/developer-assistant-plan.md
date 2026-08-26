# Plan de Implementación — developer-assistant
**Fecha:** 2026-08-25  
**Estado:** Propuesta  
**Contexto:** `claude-mcp-jira` como Developer Automation API Gateway

---

## Visión

`developer-assistant` es el cliente oficial de la plataforma `claude-mcp-jira`.  
Un script interactivo que expone todas las capacidades del sistema desde la terminal, sin necesidad de Claude Code ni de escribir `curl` manualmente.

```
developer-assistant (CLI)
        │
        ▼
localhost:18000  ←  claude-mcp-jira (API Gateway)
        │
        ├──► localhost:8101  (simple-jira-agent — SAZ)
        └──► localhost:8102  (simple-pr-agent   — PRs / Azure DevOps)
```

---

## Estado del ecosistema (2026-08-25)

| Servicio | Puerto | Estado |
|----------|--------|--------|
| `claude-mcp-jira` — service layer | `:18000` | ✅ Operativo |
| `claude-mcp-jira` — MCP server | `:18001` | ✅ Operativo |
| `simple-jira-agent` | `:8101` | ✅ Operativo |
| `simple-pr-agent` | `:8102` | ✅ Operativo |

---

## Endpoints consumidos (sin cambios de paths)

El script consume los endpoints existentes en `:18000`. No se renombra nada.

| Función | Endpoint actual | Agente delegado |
|---------|----------------|-----------------|
| Crear ticket Jira | `POST /issues` | — (directo) |
| Buscar tickets | `POST /issues/search` | — (directo) |
| Crear SAZ | `POST /issues/saz` | → `simple-jira-agent:8101` |
| Crear SAZ despliegue | `POST /issues/saz/deployment` | → `simple-jira-agent:8101` |
| Workflow deploy completo | `POST /deployments/saz-workflow` | → `simple-pr-agent:8102` + `simple-jira-agent:8101` |
| Registrar worklogs git | `POST /git/sync` | — (directo) |
| Estado de workflow | `GET /workflows/{id}` | — (directo) |
| Health check | `GET /health` | — |

---

## Configuración por usuario

Archivo: `~/.developer-assistant/config.json`

```json
{
  "api_url": "http://localhost:18000",
  "api_key": "<MCP_API_KEY>",
  "default_project": "ZNRX",
  "default_repo": "ov-arizona-backend-ecuador",
  "default_team": "Soporte Oficina Virtual",
  "default_assignee": "SEBASTIAN.MAYORGA"
}
```

El script carga la config en cada ejecución. Si no existe, ofrece `--init` para crearla interactivamente.

---

## Interfaz de usuario (CLI)

### Comandos principales

```bash
developer-assistant saz        # Crear SAZ de despliegue (interactivo)
developer-assistant pr         # Crear Pull Request
developer-assistant deploy     # Workflow completo: PR + SAZ en un paso
developer-assistant worklog    # Registrar horas desde git
developer-assistant ticket     # Crear/buscar ticket Jira
developer-assistant status     # Estado del último workflow
developer-assistant health     # Health check del stack
developer-assistant --init     # Configuración inicial interactiva
```

### Ejemplo de flujo `saz`

```
$ developer-assistant saz

Proyecto   : [ov-arizona-backend-ecuador]
PR ID      : 2834
Rama origen: feature/ZNRX-67108_vidrios_test_aux
Rama destino: [test]
Descripción: Textos cobertura vidrios
Ticket ZNRX: ZNRX-68881 (opcional)

Creando SAZ... → SAZ-7590
Asignado a: SEBASTIAN.MAYORGA
```

### Ejemplo de flujo `deploy` (workflow completo)

```
$ developer-assistant deploy

Repo   : [ov-arizona-backend-ecuador]
Branch : feature/ZNRX-67108_vidrios_test_aux
Target : test
Ticket : ZNRX-68881
Tarea  : Textos cobertura vidrios

[1/2] Creando PR en Azure DevOps...   → PR #2835
[2/2] Creando SAZ de despliegue...    → SAZ-7591 (vinculado a ZNRX-68881)

Listo.
```

---

## Fases de implementación

### Fase 1 — CLI funcional (v1.0)

**Entregables:**
- `developer-assistant.py` (o `.sh`) con comandos `saz`, `deploy`, `worklog`, `health`
- `~/.developer-assistant/config.json` con `--init`
- Consumo de endpoints existentes en `:18000`

**Criterio de aceptación:**
- Ejecutar `developer-assistant deploy` sin abrir Claude Code
- Sin parámetros hardcodeados — todo desde config o prompt interactivo

**Implementación sugerida:** Python (argparse + requests) — más fácil de mantener que bash puro para flujos interactivos.

---

### Fase 2 — systemd para claude-mcp-jira ✅ Completa

**Entregables:**
- `~/.config/systemd/user/claude-mcp-jira.service` — unit instalado y habilitado
- `scripts/start_service.sh` — carga `.env`, fija overrides WSL, arranca service (:18000) + MCP (:18001); usa `wait -n` para reinicio automático si un proceso muere
- Linger habilitado (compartido con `simple-jira-agent` y `simple-pr-agent`)
- `developer-assistant health` verifica los 4 servicios (`:18000`, `:18001`, `:8101`, `:8102`)
- Documentación del patrón: `arch/design/systemd-services.md`

**Criterio de aceptación:**
- Servicios activos tras reinicio de WSL sin intervención manual

---

### Fase 3 — Delegación interna (opcional)

**Entregables:**
- `claude-mcp-jira` delega `POST /issues/saz` → `simple-jira-agent:8101`
- `claude-mcp-jira` delega PR operations → `simple-pr-agent:8102`
- Los paths de `:18000` no cambian — la delegación es transparente

**Criterio de aceptación:**
- Mismo contrato de API, mismos tests — solo cambia el destino interno de las llamadas

**Nota:** Esta fase es opcional si los agentes especializados ya tienen carga operativa directa (ej. pipelines CI que llaman a `:8101` o `:8102` directamente). Solo implementar si hay beneficio concreto en centralizar el routing.

---

### Fase 4 — Configuración por proyecto (v2.0)

**Entregables:**
- Soporte multi-repo en config: `repos: { ov-arizona-backend-ecuador: { default_target: "test", ... } }`
- `developer-assistant` detecta el repo actual desde `git remote` y aplica defaults automáticamente
- Historial local de SAZs y PRs creados (`~/.developer-assistant/history.json`)

---

### Fase 5 — UI Web (futuro)

Cuando haya demanda no-técnica validada. Misma API `:18000`.

---

## Decisiones de diseño

| Decisión | Opción elegida | Alternativa descartada |
|----------|---------------|------------------------|
| Paths de API | Conservar existentes | Renombrar a `/jira/`, `/saz/`, `/prs/` — breaking change innecesario |
| Lenguaje script | Python (argparse + requests) | Bash — difícil de mantener para flujos interactivos |
| Config | `~/.developer-assistant/config.json` | Variables de entorno — menos ergonómico |
| Modo interactivo | Prompts con defaults entre `[]` | Flags CLI — más verboso para uso frecuente |

---

## Archivos a crear

```
claude-mcp-jira/
└── scripts/
    └── developer-assistant.py    # CLI principal

~/.developer-assistant/
├── config.json                   # Config por usuario
└── history.json                  # Historial local (Fase 4)
```

---

## Referencias

- Recomendaciones origen: `arch/recomendations/RECOMENDACIONES_EVOLUCION_CLAUDE_MCP_JIRA_V2.md`
- Endpoints actuales: `CLAUDE.md` sección "Service layer — endpoints"
- `simple-jira-agent`: `/home/idavid/dev/claude/simple-jira-agent` (`:8101`)
- `simple-pr-agent`: `/home/idavid/dev/claude/simple-pr-agent` (`:8102`)
