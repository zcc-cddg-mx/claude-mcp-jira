# Informe Técnico: claude-mcp-jira
# Agente de Automatización de Desarrollo — Zurich Insurance Ecuador

**Versión**: 2.2  
**Fecha**: Agosto 2026  
**Equipo**: Desarrollo Zurich Insurance Ecuador  
**Contacto**: carlos.duarte2@mx.zurich.com

---

## Resumen ejecutivo

`claude-mcp-jira` es una **plataforma de automatización del ciclo de desarrollo** construida sobre la red corporativa Zurich. Integra Jira, Git y Azure DevOps en un flujo único controlado por lenguaje natural desde el IDE (Claude Code), eliminando tareas manuales repetitivas del equipo de desarrollo.

El sistema opera como un **Agente especializado Ecuador** — equivalente al concepto AGENTE de Zurich Global AI — con capacidades que van más allá del CRUD básico de Jira:

| Capacidad | Descripción | ¿Disponible en et-ai-mcp-jira global? |
|---|---|---|
| Gestión Jira completa | 9 tools: crear, actualizar, buscar, comentar, linkear, asignar, prioridad, SAZ | Parcial (CRUD básico) |
| **Git Intelligence** | Detecta sesiones de trabajo desde commits y registra worklogs en Jira automáticamente | ❌ No |
| **Deployment SAZ workflow** | PR Azure DevOps → SAZ de despliegue en un solo comando | ❌ No |
| **Workflow Orchestrator** | 6 pasos orquestados: commit → rama → PR → CI → Jira | ❌ No |
| **Azure DevOps EC** | Integración con tenant `ZurichInsurance-EC / Oficina-Virtual-ZEC` | ❌ No |

**Estado actual:** 20 MCP tools operativos · 240 tests · validación end-to-end con PRs y SAZs reales · red 100% interna Zurich · CLI `developer-assistant` para uso directo sin Claude Code.

---

## 1. Contexto y motivación

### Problema original

El equipo de desarrollo gestionaba manualmente:
- Creación y actualización de tickets Jira (ZNRX, SAZ, AIPROJECTS, SCRX)
- Solicitudes de despliegue al equipo DevOps (tickets SAZ manuales)
- Registro de horas trabajadas (worklogs inconsistentes o no registrados)
- Coordinación de ramas, commits y PRs en Azure DevOps

### Solución adoptada

Un agente de IA orquestador que ejecuta estos flujos desde el CLI o desde Claude Code (IDE), manteniendo siempre control humano para validación y ajustes.

### Restricciones de red Zurich

El sistema respeta todas las restricciones corporativas:
- **Jira Server / Data Center** — `jira.zurich.com`; REST API v2; PAT Bearer; sin Jira Cloud
- **Claude API** — vía LiteLLM proxy interno; sin tráfico a `api.anthropic.com` directo
- **Azure DevOps** — tenant ecuatoriano `ZurichInsurance-EC / Oficina-Virtual-ZEC`
- **Certificados corporativos** — `certs/` con CA Zurich para todas las llamadas TLS
- **Sin servicios cloud externos** — sin Atlassian MCP Cloud, N8N, Zapier

---

## 2. Arquitectura

### 2.1 Diagrama de capas

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INTERFAZ DE USUARIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [Claude Code (IDE)]     [CLI (Typer)]    [developer-assistant `da`]
         │ SSE/MCP              │ HTTP              │ HTTP
         ▼                      │                   │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  MCP SERVER  :18001  (jira_mcp/)
  Auth: X-API-Key + IP allowlist + RBAC + rate limit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         │ HTTP (todos los clientes convergen aquí)
         ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SERVICE LAYER  :18000  (service/)
  Sanitización · Audit log · JQL builder · Project registry
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         │                           │                    │
         ▼                           ▼                    ▼
  [LiteLLM proxy]          [jira.zurich.com]    [code-agent-mcp :5001]
  [→ Claude API]           [REST API v2]        [Git + Azure DevOps EC]
```

**Principio:** el MCP server nunca llama a Jira ni a Claude directamente — todo pasa por el service layer. El CLI `developer-assistant` accede directamente al service layer (:18000), sin pasar por el MCP server.

### 2.2 ¿Qué es MCP?

El **Model Context Protocol (MCP)** es un protocolo abierto de Anthropic que estandariza la conexión entre LLMs y servicios externos. Es la "interfaz universal" que permite a Claude invocar herramientas reales de forma segura y auditable.

```
[Claude Code]  ←──MCP/SSE──►  [MCP Server]  ──HTTP──►  [Service Layer]  ──►  [Jira / Azure / Git]
```

El transporte SSE (Server-Sent Events) permite que el servidor MCP viva en la red interna, nunca en la máquina del usuario ni en servicios cloud.

---

## 3. Capacidades del sistema (20 MCP tools)

### 3.1 Gestión Jira (9 tools)

| Tool | Rol | Descripción |
|---|---|---|
| `create_jira_issue` | dev | Crea ticket desde texto libre; NL → campos Jira |
| `update_jira_issue` | lead | Actualiza cualquier campo desde texto |
| `get_jira_issue` | dev | Resumen Claude del ticket |
| `search_jira_issues` | dev | Búsqueda NL → JQL controlado (max 50 resultados) |
| `add_comment_jira_issue` | dev | Añade comentario desde texto libre |
| `link_jira_issues` | dev | Relaciona dos tickets (depends on, blocks, relates to...) |
| `assign_jira_issue` | lead | Asigna responsable desde texto |
| `set_priority_jira_issue` | lead | Cambia prioridad desde texto |
| `create_saz_request` | lead | Crea ticket SAZ; `znrx_key` opcional para vincular a requerimiento |

### 3.2 Git Intelligence (4 tools)

Funcionalidad diferencial — no existe equivalente en el ecosistema global Zurich.

| Tool | Descripción |
|---|---|
| `register_git_repo` | Registra alias de repo local → path + proyecto Jira |
| `list_git_repos` | Lista repos registrados |
| `sync_git_worklogs` | Escanea commits por autor/período → detecta sesiones de trabajo → registra worklogs en Jira; `dry_run=true` por defecto; Claude humanizer ajusta estimaciones semánticamente |
| `report_git_worklogs` | Solo lectura: ejecuta `sync_git_worklogs(dry_run=True)` y retorna tabla agrupada por ticket (`Ticket · Horas · Commits · Confianza`); `since_days` default 7 |

**Inferencia de ticket por sesión de trabajo:**

Cada sesión detectada es asignada al ticket Jira correspondiente mediante este orden de prioridad:

```
1. Nombre de rama   feature/ZNRX-68488_vidrios  →  ZNRX-68488
                    fix/SCRX-13654_referrals     →  SCRX-13654

2. Mensaje de commit  "ZNRX-68488: actualizar diccionario"  →  ZNRX-68488

3. default_issue_key  configurado en el registro del repo (fallback)
```

El patrón regex reconoce cualquier proyecto de formato `[A-Z]+-\d+` (ZNRX, SCRX, SAZ, AIPROJECTS, etc.). Si ninguna fuente entrega un ticket, la sesión queda sin asignar y se muestra como `sin-ticket` en el reporte.

**Flujo completo:**
```
git log → detectar sesiones (gap temporal) → inferir ticket (rama→commit→default)
→ estimar tiempo por LOC/tipo → Claude ajusta 
(debugging = ×1.5, alta complejidad = ×1.3, trabajo nocturno = +15min)
→ POST /worklog en Jira
```

### 3.3 Azure DevOps / PR lifecycle (4 tools)

Integración con el tenant ecuatoriano `ZurichInsurance-EC / Oficina-Virtual-ZEC`.

| Tool | Rol | Descripción |
|---|---|---|
| `run_code_agent` | lead | Encola tarea git asíncrona: crear rama + commit + push + rama auxiliar |
| `get_code_agent_status` | dev | Estado de la tarea (queued/running/done/error + steps) |
| `create_azure_pull_request` | lead | Idempotente: ensure aux branch → crear o retornar PR existente |
| `get_pull_request_status` | dev | Estado del PR + build CI |

### 3.4 Deployment SAZ workflow (3 tools)

Flujo de despliegue completo en un solo comando.

| Tool | Rol | Descripción |
|---|---|---|
| `create_deployment_saz_workflow` | lead | Sincrónico: lookup repo → PR Azure → SAZ Jira; `ticket` acepta Jira key o ID de requerimiento |
| `update_pull_request_status` | lead | Cambia estado PR: `abandoned / completed / active` |
| `set_repo_branch_map` | lead | Configura mapping `developer→developer`, `test→test`, `prod→develop` por repo |

**Flujo típico:**
```
create_deployment_saz_workflow(repo="ov-arizona-backend-ecuador", branch="feature/REQ2298577", target="test", ticket="REQ2298577")
→ PR #2575 creado en Azure DevOps (branch feature/REQ2298577 → test)
→ SAZ-7442 creado: "Despliegue ambiente TEST - OV - Limite Autos - Backend Ecuador"
```

También disponible como REST endpoint directo: `POST /deployments/saz-workflow` (service layer :18000).

### 3.5 Workflow Orchestrator (2 tools)

| Tool | Rol | Descripción |
|---|---|---|
| `run_create_feature_pr_workflow` | lead | 6 pasos: preview → commit → push → PR → esperar CI → comentar en Jira |
| `get_workflow_status` | dev | Estado de ejecución (steps, result, error) |

### 3.6 Configuración (1 tool)

| Tool | Rol | Descripción |
|---|---|---|
| `set_repo_branch_map` | lead | Configura mapping ambiente→rama en code-agent-mcp |

---

## 4. Seguridad

| Capa | Mecanismo |
|---|---|
| Auth MCP | `X-API-Key` header + IP allowlist por CIDR |
| RBAC | Roles `dev / lead / system` por API key; principio de menor privilegio |
| Rate limiting | 30 req/60s (service) + 10 calls/60s (MCP) por usuario/key |
| Sanitización | Elimina tokens, IPs RFC1918, hostnames internos, stack traces antes de enviar a Claude |
| Audit log | JSON-lines con `request_id` UUID; rotación 10 MB × 5 backups |
| JQL seguro | Claude → struct → builder controlado; `_jql_escape` en todos los campos; MAX 50 |
| Pre-validación | Rechaza inputs vacíos o > 2000 chars antes de llamar al backend |
| Output normalizado | LLM recibe solo `{key, status}` o `{key, summary}` — sin datos internos |
| code-agent token | `X-Agent-Token` separado del `JIRA_PAT`; valor en `TOKEN_AZURE` (variable única consolidada) |
| SSE timeout | `asyncio.wait_for` con `MCP_SSE_TIMEOUT=300s` |

---

## 5. Proyectos Jira integrados

| Proyecto | Key | Idioma | Tipo |
|---|---|---|---|
| Gestión requerimientos | `ZNRX` | es | seed (constraints curados) |
| IA y automatización | `AIPROJECTS` | en | seed |
| Desarrollo LATAM | `SCRX` | es | seed |
| Solicitudes Release / DevOps | `SAZ` | es | auto-discovery |
| Cualquier otro proyecto Jira | `*` | configurable | auto-discovery en primer acceso |

**Auto-discovery:** al primer acceso a un proyecto desconocido, el sistema consulta `GET /rest/api/2/project/{key}` y lo registra automáticamente en SQLite — sin configuración manual.

---

## 6. Cobertura de tests

| Suite | Tests | Qué cubre |
|---|---|---|
| `test-dev.sh` | 8 e2e | CLI → FastAPI → Jira |
| `test-mcp.sh` | 10 e2e | MCP tools + RBAC + pre-validación |
| `test-multi.sh` | 19 e2e | Multi-proyecto + auto-discovery |
| `test-actions.sh` | 24 e2e | comments, assign, priority, labels, worklog, transition, clone, link, SAZ |
| `test-git.sh` | 26 e2e | Git registry CRUD + sync dry_run |
| `test-code-agent.sh` | 57 schema+live | Fases 10/11/12 + endpoint `/deployments/saz-workflow`: tools, dispatch, RBAC, funciones, token consolidado |
| `pytest tests/` | 96 unit | sanitizer, jql_builder, auth, rbac, git_analyzer, git_mapper, jira_pat_routing |
| **Total** | **240** | |

Flujos reales validados: PRs #2574/#2575 en Azure DevOps · SAZ-7441/7442 en Jira · ZNRX-68298 vía MCP global.

---

## 7. Posicionamiento frente al ecosistema Zurich Global

### 7.1 Evaluación de et-ai-mcp-jira (skills.ai.zurich.com)

En junio 2026, se evaluó `et-ai-mcp-jira` (Zurich Global AI, recomendado por Jose Sanchez Ros) contra el sistema local. Resultados:

| Operación | et-ai-mcp-jira | claude-mcp-jira |
|---|---|---|
| CRUD básico (create/update/get/comment/transitions) | ✅ | ✅ |
| Búsqueda | ✅ JQL directo | ✅ NL→JQL semántico |
| **Worklog / registro de horas** | ❌ | ✅ |
| link / assign / priority / labels / clone | ❌ | ✅ |
| SAZ (solicitud despliegue) | ❌ | ✅ |
| Deployment SAZ workflow | ❌ | ✅ |
| Azure DevOps EC | ❌ | ✅ |
| Git Intelligence | ❌ | ✅ |
| RBAC + audit log corporativo | ❌ | ✅ |
| Releases / versiones Jira | ✅ | ❌ |

**Conectividad confirmada:** `gateway-dev.mcp.zurich.com` alcanzable desde Ecuador · instancia Jira = `jira.zurich.com` (Server/DC) ✅.

### 7.2 Decisión y posicionamiento

`claude-mcp-jira` **no compite** con `et-ai-mcp-jira` — es un **AGENTE especializado Ecuador** que opera encima del ecosistema global:

```
Claude Code
    ↓
claude-mcp-jira  [AGENTE Ecuador — orquestación + especialización]
    ├── Git Intelligence     → worklogs, commits, sesiones de trabajo
    ├── SAZ workflow         → solicitudes de despliegue Ecuador
    ├── code-agent-mcp       → Azure DevOps EC (tenant ZEC)
    └── Jira CRUD            → compatible con et-ai-mcp-jira para CRUD base
                                (integración futura cuando el gateway sea productivo)
```

**Condiciones para integración futura con MCP global:**
- `et-ai-mcp-jira` añade worklog y link
- Gateway productivo estable (sin `-dev`)
- Tokens de equipo disponibles (no personales)

---

## 8. Fases de implementación

| Fase | Estado | Descripción |
|---|---|---|
| 1 — Prototipo CLI | ✅ | `cli/main.py` — comando `create` directo |
| 2 — Service Layer | ✅ | FastAPI + sanitización + audit log + timeouts |
| 3 — Comandos completos | ✅ | `update`, `summarize`, `list` + JQL + rate limiter |
| 4 — MCP Server | ✅ | SSE Docker + auth + RBAC + rate limit + output normalizado |
| 4.1–4.5 — Ajustes, deuda, mejoras API | ✅ | Comments, assign, priority, labels, clone, link dinámico |
| 5 — Soporte SAZ | ✅ | `create_saz_request` + `POST /issues/saz/deployment` |
| 6 — Observabilidad | Futura | Prometheus + OpenTelemetry — activar cuando el volumen lo justifique |
| 7 — Multi-proyecto | ✅ | SQLite + auto-discovery lazy desde Jira |
| 8a — PAT dinámico | ✅ | `X-Jira-Token` header opcional; autoría correcta por usuario |
| 8 — UI | Futura | Streamlit/Next.js — tras validar demanda no-técnica |
| 9.1–9.4 — Git Intelligence | ✅ | Scanner + analyzer + mapper + worklog automático |
| 9.5a — Claude humanizer | ✅ | Ajuste semántico de estimaciones git |
| 9.5b — Learning layer | Futura | Multiplier factors por usuario — requiere UI |
| 10 — Workflow Orchestrator | ✅ | 6-step polling engine + 4 REST endpoints + 2 MCP tools |
| 11 — Integración code-agent-mcp | ✅ | 4 MCP tools: git ops + Azure PR |
| 12 — Deployment SAZ workflow | ✅ | 3 MCP tools: deployment SAZ + PR lifecycle |
| Eval — Zurich Global MCP | ✅ | `et-ai-mcp-jira` evaluado; decisión: mantener sistema local |

---

## 9. Instalación y configuración

```bash
# Requisitos: miniconda3, WSL2 con systemd habilitado
conda env create -f environment.yml
conda activate claude-mcp-jira
cp .env.example .env
# Completar: JIRA_PAT, MCP_API_KEY, TOKEN_AZURE, ANTHROPIC_AUTH_TOKEN
```

**Servicio persistente (recomendado) — arranca con WSL, restart automático:**

```bash
# Crear unit systemd
mkdir -p ~/.config/systemd/user
sed "s/<tu-usuario>/$USER/g" > ~/.config/systemd/user/claude-mcp-jira.service << 'EOF'
[Unit]
Description=claude-mcp-jira — service layer (:18000) + MCP server (:18001)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/<tu-usuario>/dev/claude/claude-mcp-jira
ExecStart=/bin/bash /home/<tu-usuario>/dev/claude/claude-mcp-jira/scripts/start_service.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user enable --now claude-mcp-jira
loginctl enable-linger $USER   # corre aunque no haya sesión activa
```

**Modo Docker (alternativa):**
```bash
docker compose up
```

**Modo desarrollo:**
```bash
bash scripts/dev.sh both    # service :18000 + MCP :18001
```

**Conectar Claude Code:**
```json
{
  "mcpServers": {
    "jira": {
      "type": "sse",
      "url": "http://localhost:18001/sse",
      "headers": { "X-API-Key": "<MCP_API_KEY>" }
    }
  }
}
```

Ver guía completa de instalación paso a paso: `docs/onboarding-developer-assistant.md`.

---

## 11. developer-assistant — CLI cliente

`developer-assistant` (`da`) es la herramienta de línea de comandos que expone todas las capacidades del service layer (:18000) sin necesidad de Claude Code ni de escribir `curl` manualmente.

### Comandos

```bash
da health           # estado de los 4 servicios del ecosistema
da init             # configuración inicial interactiva

da ticket           # crear o buscar ticket Jira (lenguaje natural)
da saz              # crear SAZ de despliegue desde un PR existente
da deploy           # workflow completo: PR Azure DevOps + SAZ en un paso
da worklog          # registrar horas desde git (dry_run por defecto)

da repos            # listar repos configurados; marca el repo activo
da history          # últimas 20 operaciones (SAZs y PRs)
da status <id>      # estado de un workflow en ejecución
```

### Configuración

`~/.developer-assistant/config.json` — generado por `da init`:

```json
{
  "api_url": "http://localhost:18000",
  "api_key": "<MCP_API_KEY>",
  "default_project": "ZNRX",
  "default_assignee": "SEBASTIAN.MAYORGA",
  "repos": {
    "ov-arizona-backend-ecuador": {
      "default_target": "test",
      "default_branch_prefix": "feature/",
      "jira_project": "ZNRX"
    }
  }
}
```

### Auto-detección de contexto git

Al ejecutar `da saz` o `da deploy` desde dentro de un repositorio git, el CLI detecta automáticamente el repo y la rama actual:

```
git remote get-url origin  →  nombre del repo
git branch --show-current  →  rama activa
```

Si el repo está en la sección `repos` de la config, los campos `repo`, `target` y `branch` se prerellenan sin preguntar.

### Historial

Cada operación exitosa se guarda en `~/.developer-assistant/history.json` (últimas 100 entradas):

```
da history
→  2026-08-25 19:30  DEPLOY  PR #2835  SAZ SAZ-7591  ZNRX-68881
→  2026-08-25 18:15  SAZ     SAZ-7590  ov-arizona-backend-ecuador  feature/ZNRX-67108 → test
```

### Dependencias

`stdlib` Python únicamente — `urllib`, `argparse`, `json`, `pathlib`, `subprocess`. Sin `pip install`.

---

## 10. Referencias

| Recurso | Ubicación |
|---|---|
| Arquitectura detallada | `arch/design/architecture-overview.md` |
| Plan de implementación (todas las fases) | `arch/design/implementation-plan.md` |
| Contrato code-agent-mcp (23 endpoints) | `arch/code-agent/integration-plan.md` |
| Workflow Orchestrator | `arch/workflows/workflow-orchestrator.md` |
| Evaluación Zurich Global MCP | `arch/evaluations/eval-zurich-mcp-integracion-2026-06-25.md` |
| Informe técnico integración vs MCP global | `arch/evaluations/eval-integracion-mcp-global-vs-local-2026-06-25.md` |
| Base de datos SQLite | `arch/bd/README.md` |
| Proyectos Jira (restricciones, TICKET_LANG) | `docs/jira-projects.md` |
| Patrón systemd (3 servicios del ecosistema) | `arch/design/systemd-services.md` |
| Plan developer-assistant | `arch/design/developer-assistant-plan.md` |
| Guía de instalación desde cero | `docs/onboarding-developer-assistant.md` |
| MCP Specification | https://spec.modelcontextprotocol.io |
| MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk |
