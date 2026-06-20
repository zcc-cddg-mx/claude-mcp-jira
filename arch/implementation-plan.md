# Plan de Implementación: claude-mcp-jira

Implementación incremental en 4 fases para red empresarial (Jira Server/Data Center en `jira.zurich.com`).
Claude API accedida vía proxy LiteLLM interno de Zurich.

> **Decisión de arquitectura**: se descartó el MCP oficial de Atlassian (solo funciona con Jira Cloud y viola políticas de red) y plataformas No-Code (N8N/Zapier). Se implementa integración propia con MCP server interno desplegable en Docker.

---

## Fase 1 — Prototipo mínimo (CLI → Claude → Jira) ✅

**Objetivo**: demostrar el flujo end-to-end básico con autenticación correcta para Jira Server.

### Entregables
- `cli/main.py` con Typer — comando único `create`
- `requirements.txt` y `environment.yml` (conda)
- `.env.example` con variables para entorno Zurich

### Ajustes para Jira Server/DC
- Auth: `Authorization: Bearer <PAT>` (no Basic Auth)
- API: `/rest/api/2/` (no v3)
- Descripción: texto plano (no ADF/JSON doc)
- SSL: `REQUESTS_CA_BUNDLE` apunta a `firewall_root.pem`

### Criterio de éxito
```bash
python cli/main.py create "bug login en producción prioridad alta"
# → PROJ-001 creado en jira.zurich.com
```

---

## Fase 2 — Service Layer (FastAPI) + Seguridad

**Objetivo**: desacoplar CLI de las APIs externas. Introducir sanitización de prompts, validación y auditoría (recomendación Copilot).

### Entregables
- Servicio FastAPI en `service/`
- CLI actualizada — llama solo al service layer
- Schemas Pydantic para request/response
- `sanitize_prompt()` antes de cada llamada a Claude
- Audit log: quién ejecutó qué, qué respondió Claude, qué se ejecutó en Jira

### Tareas
1. Crear estructura `service/main.py`, `service/routes/`, `service/schemas/`, `service/clients/`
2. Implementar `POST /issues` — recibe texto libre, sanitiza, llama a Claude, llama a Jira
3. Implementar `clients/claude.py` con prompt templates en `service/prompts/`
4. Implementar `clients/jira.py` con auth PAT Bearer y certificado corporativo
5. Definir schemas Pydantic: `CreateIssueRequest`, `JiraIssuePayload`, `CreateIssueResponse`
6. Implementar `sanitize_prompt()`: elimina patrones de secrets (tokens, passwords, IPs internas) antes de enviar a Claude
7. Agregar audit log estructurado (JSON lines): `timestamp`, `user`, `input`, `claude_response`, `jira_key`, `status`
8. Actualizar CLI: solo hace HTTP a `http://localhost:8000`
9. Dockerizar (`Dockerfile` + `docker-compose.yml`)

### Criterio de éxito
```bash
docker compose up
python cli/main.py create "bug login en producción"
# → CLI → FastAPI → sanitize → Claude → Jira → PROJ-002
# → audit.log registra la operación completa
```

---

## Fase 3 — Comandos completos + clasificación de intención

**Objetivo**: soporte para los 4 comandos CLI con clasificación automática de intención.

### Entregables
- Dispatcher de intención en el service layer
- 4 comandos: `create`, `update`, `summarize`, `list`
- Endpoints adicionales en FastAPI

### Tareas
1. Implementar clasificador de intención: texto → `{intent, params}`
2. Agregar `PATCH /issues/{key}` — actualiza summary/description/status vía transiciones Jira v2
3. Agregar `GET /issues/{key}/summary` — Claude genera resumen legible
4. Agregar `GET /issues?query=<texto>` — traduce texto a JQL y llama `/rest/api/2/search`
5. Prompt templates separados por operación en `service/prompts/`
6. Validar output de Claude con Pydantic antes de llamar a Jira
7. Rate limiting en FastAPI

### Criterio de éxito
```bash
python cli/main.py update PROJ-002 "cambiar prioridad a crítica"
python cli/main.py summarize PROJ-002
python cli/main.py list "mis bugs abiertos de esta semana"
```

---

## Fase 4 — MCP Server (servicio deployable interno)

**Objetivo**: exponer la integración como MCP server desplegable en red interna — no como script local del usuario (recomendación Copilot: el MCP server debe vivir dentro de la red corporativa).

### Entregables
- MCP server en `mcp/server.py` usando SDK `mcp`
- Herramientas: `create_jira_issue`, `update_jira_issue`, `search_jira_issues`, `get_jira_issue`
- Dockerfile propio para `mcp/` — desplegable como servicio independiente
- Configuración lista para `.claude/settings.json` apuntando al servicio interno

### Tareas
1. Instalar SDK MCP (`pip install mcp`)
2. Crear `mcp/server.py` con las 4 herramientas como `@tool` handlers
3. Cada herramienta MCP delega al service layer FastAPI (no duplicar lógica)
4. Schemas de input claros para que Claude pueda invocarlas sin ambigüedad
5. `mcp/Dockerfile` — imagen deployable en red interna
6. Documentar en `mcp/README.md` la configuración SSE interna:
   ```json
   {
     "mcpServers": {
       "jira": {
         "type": "sse",
         "url": "http://mcp-jira.internal/sse"
       }
     }
   }
   ```
7. Prueba de integración: Claude Code invoca `create_jira_issue` desde una conversación

### Criterio de éxito
```
Claude Code: "crea un ticket para el bug que encontramos en auth"
→ Claude invoca create_jira_issue (MCP interno) → PROJ-003 creado en jira.zurich.com
```

---

## Estructura de directorios final

```
claude-mcp-jira/
├── cli/
│   └── main.py                  # Typer CLI
├── service/
│   ├── main.py                  # FastAPI app
│   ├── routes/
│   ├── schemas/
│   ├── clients/
│   │   ├── claude.py
│   │   └── jira.py              # Auth PAT Bearer + cert corporativo
│   └── prompts/                 # Prompt templates por operación
├── mcp/
│   ├── server.py                # MCP server (delega a service layer)
│   ├── Dockerfile
│   └── README.md
├── arch/
│   ├── general.md
│   ├── recomendations.gemini.md
│   ├── recomendations.copilot.md
│   └── implementation-plan.md
├── docker-compose.yml
├── environment.yml
├── .env.example
└── CLAUDE.md
```

---

## Dependencias Python

```
anthropic
mcp
fastapi
uvicorn
httpx
requests
typer
pydantic
python-dotenv
```

---

## Decisiones de arquitectura

| Decisión | Opción elegida | Motivo |
|---|---|---|
| MCP oficial Atlassian | ❌ Descartado | Solo Jira Cloud; viola políticas de red Zurich |
| N8N / Zapier | ❌ Descartado | Servicios cloud; bloqueados por firewall corporativo |
| Auth Jira | PAT Bearer token | Jira Server/DC no usa Basic Auth con email+token |
| Jira REST API | v2 | v3 es exclusiva de Jira Cloud |
| Descripción tickets | Texto plano | Jira Server no acepta ADF (Atlassian Document Format) |
| SSL | `REQUESTS_CA_BUNDLE` | Certificado raíz corporativo del firewall de Zurich |
| MCP deployment | Servicio Docker interno | Debe vivir en red corporativa para acceder a `jira.zurich.com` |
| Sanitización | Antes de llamar a Claude | Prevenir fuga de datos sensibles hacia la API de Claude |
